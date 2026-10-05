# plugins/preprocessing/prepare/artifact_remove/artifact_logic.py
"""Lectura y escritura de los trials que modifica artifact_remove.

La modificación se hace en tres pasos para que los datos compartidos solo se
toquen desde el hilo de la interfaz (regla de escritura única del orquestador):

  1. preparar_modificacion  -> hilo de la interfaz: lee y copia los trials activos.
  2. calcular_modificacion  -> orquestador (compute.py): función pura, sin Kernel.
  3. escribir_modificacion  -> hilo de la interfaz, en el slot de `finished`.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from plugins.preprocessing.prepare.artifact_remove.compute import calcular_modificacion, receta

LOGL = "[ArtifactLogic]"

# ----------------- Helpers -----------------

def _last_trial_dataset(sd):
    """Último TrialDataset generado, por la API pública de SignalDataset (o None).

    Antes se leía `sd.trials_dataset`, un atributo que SignalDataset no tiene: el
    error se tragaba y siempre se usaba el primer canal de la señal.
    """
    try:
        tds = sd.get_all_trials_datasets()
        return tds[-1] if tds else None
    except Exception:
        return None

def _get_active_signal_and_name(kernel):
    store = kernel.get_service("DataStore")
    if not store:
        raise RuntimeError("No está disponible el DataStore.")
    sd = store.get_active_signal()
    if sd is None:
        raise RuntimeError("No hay una señal activa.")
    # SignalDataset uses file_name (Path(source).name) as key.
    # Try to take it from the last TrialDataset if available; otherwise from source_path.
    file_name = None
    last_td = _last_trial_dataset(sd)
    if last_td is not None and getattr(last_td, "source", None):
        file_name = Path(last_td.source).name
    if not file_name:
        file_name = Path(getattr(sd, "source_path", "")).name or getattr(sd, "name", None)
    if not file_name:
        raise RuntimeError("La señal activa no tiene nombre de archivo.")
    return sd, file_name

def _get_current_channel_name(sd) -> str:
    """
    Current channel resolution order:
      1) channel_name from the last TrialDataset
      2) first name in sd.channel_names
      3) 'ch-1' if there are signals loaded
    """
    ch = getattr(_last_trial_dataset(sd), "channel_name", None)
    if ch:
        return str(ch)
    try:
        names = getattr(sd, "channel_names", None)
        if names and len(names) > 0:
            return str(names[0])
    except Exception:
        pass
    sig = getattr(sd, "signals", None)
    if sig is not None and getattr(sig, "shape", None) and sig.shape[0] > 0:
        return "ch-1"
    raise RuntimeError("No se encontró el canal. Genera los trials primero o selecciona un canal.")

def _discarded_for(sd, file_name: str, channel_name: str) -> frozenset:
    """Descartes de (archivo, canal); si no hay, prueba con el nombre del archivo sin extensión."""
    discarded_dict = getattr(sd, "_SignalDataset__discarded_trials", {})
    discarded = discarded_dict.get((file_name, channel_name), set()) or set()
    if not discarded and isinstance(discarded_dict, dict):
        # Try alternate keys by filename stem
        stem = Path(file_name).stem
        for (k_file, k_ch), disc in discarded_dict.items():
            try:
                if k_ch == channel_name and Path(k_file).stem == stem:
                    discarded = disc or set()
                    break
            except Exception:
                continue
    return frozenset(discarded)

# ----------------- Public logic -----------------

@dataclass
class ModificacionPreparada:
    """Lo que se lee en el hilo de la interfaz antes de calcular."""
    sd: object
    td_base: object
    file_name: str
    channel_name: str
    t: np.ndarray             # copia del eje de tiempo (Ns,)
    trials: np.ndarray        # copia de los trials activos (Ns, T_act)
    orig_indices: list        # columna activa -> columna del TrialDataset base
    discarded: frozenset      # descartes vigentes al leer
    base_shape: tuple         # forma del TrialDataset base al leer


def preparar_modificacion(kernel):
    """
    Paso 1, en el hilo de la interfaz: ubica los trials activos y el TrialDataset
    base, arma el mapa de columnas y COPIA los datos que va a usar el cálculo.
    Devuelve None si no hay trials activos.
    """
    sd, file_name = _get_active_signal_and_name(kernel)
    channel_name = _get_current_channel_name(sd)

    # 1) Read ACTIVE trials (filtered by discards) from the dataset
    td_active = sd.get_active_trials(file_name, channel_name)
    if td_active is None:
        raise RuntimeError(f"No hay trials activos para ({file_name}, {channel_name}).")

    t = np.array(td_active.time_rel, copy=True)          # (Ns,)
    trials_active = np.array(td_active.trials, copy=True)  # (Ns, T_act)
    if t.ndim != 1 or trials_active.ndim != 2:
        raise RuntimeError("Los trials activos no tienen eje de tiempo o datos válidos.")
    Ns, T_act = trials_active.shape
    if T_act == 0:
        return None

    # 1.5) Prefer file_name from the active trials metadata/source if available
    try:
        active_src = getattr(td_active, "source", None)
        if active_src is None:
            active_src = getattr(getattr(td_active, "metadata", {}), "get", lambda *_: None)("source")
        if active_src:
            file_name = Path(active_src).name
    except Exception:
        pass

    # 2) Find BASE TrialDataset (unfiltered) for this file+channel
    td_list = getattr(sd, "_SignalDataset__trials_dataset", [])
    td_base = next(
        (tdb for tdb in td_list
         if Path(getattr(tdb, "source", "")).name == file_name and getattr(tdb, "channel_name", None) == channel_name),
        None
    )
    # Fallbacks: by channel and sample count, or by channel only (last occurrence)
    if td_base is None:
        try:
            ns = trials_active.shape[0]
            candidates = [tdb for tdb in td_list
                          if getattr(tdb, "channel_name", None) == channel_name]
            td_base = next((tdb for tdb in candidates if getattr(tdb.trials, "shape", (0,))[0] == ns),
                           candidates[-1] if candidates else None)
        except Exception:
            td_base = None
    if td_base is None:
        raise RuntimeError(f"No se encontró el conjunto de trials original para ({file_name}, {channel_name}).")
    if td_base.trials.shape[0] != Ns:
        raise RuntimeError(f"Los trials activos tienen {Ns} muestras y los originales "
                           f"{td_base.trials.shape[0]}; no coinciden.")

    # 3) Build ACTIVE → ORIGINAL index mapping using discarded_trials if present
    discarded = _discarded_for(sd, file_name, channel_name)
    T_total = td_base.trials.shape[1]
    orig_indices = [i for i in range(T_total) if i not in discarded]
    # If mapping length still mismatched, assume no discards
    if len(orig_indices) != T_act:
        # Safety: adjust to shorter length (e.g., if discards changed live)
        T_act = min(T_act, len(orig_indices))
        trials_active = trials_active[:, :T_act]
        orig_indices = orig_indices[:T_act]

    return ModificacionPreparada(sd=sd, td_base=td_base, file_name=file_name, channel_name=channel_name,
                                 t=t, trials=trials_active, orig_indices=orig_indices,
                                 discarded=discarded, base_shape=td_base.trials.shape)


def escribir_modificacion(kernel, prep: ModificacionPreparada, out_active: np.ndarray, mode: str,
                          point_a: float = 0.0, point_b: float = 0.0):
    """
    Paso 3, en el hilo de la interfaz: escribe las columnas modificadas en el
    TrialDataset base, invalida la caché de trials activos y avisa a los plugins.
    Antes comprueba que los trials no hayan cambiado desde que se leyeron.

    `point_a` y `point_b` no se usan para calcular —eso ya se hizo— sino para
    guardar la receta de la modificación, que es lo que el proyecto persiste
    para poder reconstruirla al abrirlo (problema nº 21).
    """
    store = kernel.get_service("DataStore")
    sd = store.get_active_signal() if store else None
    vigente = (
        sd is prep.sd
        and any(td is prep.td_base for td in getattr(sd, "_SignalDataset__trials_dataset", []))
        and prep.td_base.trials.shape == prep.base_shape
        and _discarded_for(sd, prep.file_name, prep.channel_name) == prep.discarded
    )
    if not vigente:
        raise RuntimeError("Los trials cambiaron mientras se calculaba la modificación; "
                           "no se aplicó ningún cambio. Vuelve a aplicarla.")

    td_base = prep.td_base
    orig_indices = prep.orig_indices

    # 5) Write changes into the BASE TrialDataset (by mapped columns)
    for k, orig_col in enumerate(orig_indices):
        if 0 <= orig_col < td_base.trials.shape[1]:
            td_base.trials[:, orig_col] = out_active[:, k]

    # 5.5) Invalidate filtered cache so get_active_trials recomputes arrays after edits
    key = (prep.file_name, prep.channel_name)
    try:
        cache = getattr(sd, "_SignalDataset__filtered_cache", None)
        if isinstance(cache, dict):
            cache.pop(key, None)
        versions = getattr(sd, "_SignalDataset__discard_versions", None)
        if isinstance(versions, dict):
            versions.pop(key, None)
    except Exception:
        pass

    # 6) Mark metadata of modified trials (optional)
    try:
        mods = td_base.metadata.get("modified_trials", set())
        mods = set(mods)
        mods.update(orig_indices)
        td_base.metadata["modified_trials"] = mods
    except Exception:
        td_base.metadata = getattr(td_base, "metadata", {}) or {}
        td_base.metadata["modified_trials"] = set(orig_indices)

    # 6.5) Guardar la receta, en orden, para que el proyecto pueda reconstruirla.
    # Sin esto las modificaciones se pierden al reabrir: el proyecto guarda cómo
    # se generaron los trials, no sus valores (problema nº 21).
    try:
        td_base.metadata.setdefault("modificaciones", []).append(
            receta(mode, point_a, point_b, prep.discarded))
    except Exception as e:
        print(f"{LOGL} No se pudo guardar la receta de la modificación: {e}")

    # 7) Notify the UI (if the pipeline uses it)
    if hasattr(kernel, "event"):
        try:
            kernel.event.emit("trials_generated", {"signal": prep.file_name, "channel": prep.channel_name})
        except Exception:
            pass

    print(f"{LOGL} Modo '{mode}' aplicado a {len(orig_indices)} trials activos de "
          f"({prep.file_name}, {prep.channel_name}).")


def apply_modification_to_all_valid(kernel, *, mode: str, point_a: float, point_b: float = 0.0):
    """
    Los tres pasos seguidos, en el hilo que llama (sin orquestador).
    Devuelve True si modificó los trials y None si no había nada que modificar.
    """
    prep = preparar_modificacion(kernel)
    if prep is None:
        return None
    out_active = calcular_modificacion(prep.t, prep.trials, mode=mode, point_a=point_a, point_b=point_b)
    if out_active is None:
        return None
    escribir_modificacion(kernel, prep, out_active, mode, point_a, point_b)
    return True

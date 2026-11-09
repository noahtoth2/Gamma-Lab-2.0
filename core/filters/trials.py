from typing import List, Optional, Literal, Tuple
import math
import numpy as np
from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset

EndMode = Literal["fixed", "until_next_onset"]

# ============ Threshold units ============
# The threshold is compared against the raw stimulus channel, in that channel's
# own unit. The UI shows it in mV, so it is converted here before detecting.
_MV_TO_UNIT = {"v": 1e-3, "mv": 1.0, "uv": 1e3, "µv": 1e3, "μv": 1e3, "nv": 1e6}


def mv_to_unit(value_mv: float, unit: str) -> Optional[float]:
    """Convert a value in mV to `unit` (V, mV, uV/µV, nV).
    Returns None if `unit` is not a voltage (e.g. "a.u.", "pA")."""
    factor = _MV_TO_UNIT.get((unit or "").strip().lower())
    return None if factor is None else float(value_mv) * factor

# ============ Onsets ============
def _detect_onsets_abs(
    signal: np.ndarray,
    threshold: float,
    *,
    debug: bool = False,
) -> np.ndarray:
    """
    Detect rising edges where |signal| crosses from <= threshold to > threshold.
    NO debouncing. Returns np.ndarray[int64] with sample indices.
    """
    x = np.abs(signal.astype(np.float64, copy=False))
    thr = float(threshold)

    if x.size < 2:
        if debug: print("[Onsets] Short signal.")
        return np.empty((0,), dtype=np.int64)

    above = x > thr
    rising = (np.flatnonzero((~above[:-1]) & (above[1:])) + 1).astype(np.int64)
    if debug:
        print(f"[Onsets] K={rising.size} (no debounce). First: {rising[:10].tolist() if rising.size else []}")
    return rising


# ============ General assemble ============
def _assemble_trials_general(
    trials: np.ndarray,
    stim_per_trial: int,
    tis: float,
    fs: float,
    *,
    pad_value: float = 0.0,
    debug: bool = False
) -> np.ndarray:
    Ns_in, T_raw = trials.shape
    if stim_per_trial <= 1 or T_raw == 0:
        if debug: print("[ASSEMBLE] nothing to do")
        return trials

    head_len = int(np.floor(tis * fs))
    head_len = max(0, min(head_len, Ns_in))
    G = T_raw // stim_per_trial
    if G == 0:
        if debug: print("[ASSEMBLE] no complete groups")
        return trials

    Ns_out = head_len + (stim_per_trial - 1) * Ns_in
    out = np.full((Ns_out, G), pad_value, dtype=np.float64)

    for g in range(G):
        c0 = g * stim_per_trial
        if head_len > 0:
            out[:head_len, g] = trials[:head_len, c0]
        write = head_len
        for k in range(1, stim_per_trial):
            ck = c0 + k
            out[write:write + Ns_in, g] = trials[:, ck]
            write += Ns_in

    if debug: print(f"[ASSEMBLE] out={out.shape}")
    return out

def _group_onsets_indices(K: int, stim_per_trial_for_cut: int) -> list:
    """
    Return 'group_starts': indices (in the onsets list) of the first onset of each group.
    """
    T = int(math.ceil(K / stim_per_trial_for_cut)) if K > 0 else 0
    return [i * stim_per_trial_for_cut for i in range(T)]

def _compute_windows(
    onsets_all: np.ndarray, N: int, fs: float,
    t0: float, t1: float, end_mode: EndMode,
    group_starts: list, stim_per_trial_for_cut: int
) -> Tuple[list, int]:
    """
    Compute windows [a,b) in sample indices for each trial to extract,
    also returning Ns (matrix height) = max(b-a) for padding.
    For 'fixed', b = a_onset + n1. For 'until_next_onset', b = onset of the next group.
    """
    n0 = int(round(t0 * fs))
    if end_mode == "fixed":
        n1 = int(round(t1 * fs))
        Ns = max(1, n1 - n0)
        windows = []
        for start_idx in group_starts:
            a_on = onsets_all[start_idx]
            a = a_on + n0
            b = a_on + n1
            a_clip = max(a, 0); b_clip = min(b, N)
            windows.append((a_clip, b_clip, a))  
        return windows, Ns
    else:
        windows = []
        max_len = 1
        for start_idx in group_starts:
            a_on = onsets_all[start_idx]
            next_group_start = start_idx + stim_per_trial_for_cut
            b_on = onsets_all[next_group_start] if next_group_start < len(onsets_all) else N
            a = a_on + n0
            b = b_on
            a_clip = max(a, 0); b_clip = min(b, N)
            max_len = max(max_len, max(0, b_clip - a_clip))
            windows.append((a_clip, b_clip, a))
        return windows, max_len

def _extract_trials_matrix(
    y_tgt: np.ndarray,
    windows: list,
    Ns: int,
    pad_value: float
) -> np.ndarray:
    """
    Extract each window [a_clip, b_clip) from y_tgt and place it in a padded column.
    'a_orig' (third value in window tuple) is used to align to start when clipping.
    """
    T = len(windows)
    trials = np.full((Ns, T), pad_value, dtype=np.float64)
    for col, (a_clip, b_clip, a_orig) in enumerate(windows):
        if b_clip > a_clip:
            seg = y_tgt[a_clip:b_clip]
            start = a_clip - a_orig 
            end = min(start + seg.shape[0], Ns)
            trials[start:end, col] = seg[:(end - start)]
    return trials

def cut_trials_single_channel(
    ds: SignalDataset,
    channel: int,
    threshold: float,
    t0: float,
    t1: float,
    stim_expected: Optional[int] = None,
    inter_stim_time: Optional[float] = None,
    end_mode: EndMode = "fixed",
    *,
    stim_channel: Optional[int] = None,
    pad_value: float = 0.0,
    debug: bool = True,
) -> TrialDataset:

    fs = float(ds.sampling_rate)
    C, N = ds.signals.shape
    if not (0 <= channel < C): raise ValueError(f"channel out of range (C={C})")
    trig_ch = stim_channel if stim_channel is not None else channel
    if not (0 <= trig_ch < C): raise ValueError(f"stim_channel out of range (C={C})")

    y_trig = ds.signals[trig_ch].astype(np.float64, copy=False)  # detect onsets
    y_tgt  = ds.signals[channel].astype(np.float64, copy=False)  # cut

    if debug:
        trig_name = ds.channel_names[trig_ch] if trig_ch < len(ds.channel_names) else f"ch{trig_ch}"
        tgt_name  = ds.channel_names[channel] if channel < len(ds.channel_names) else f"ch{channel}"
        #print(f"\n[TRIALS] fs={fs} N={N} target='{tgt_name}' stim='{trig_name}' "
        #     f"thr={threshold} t0={t0} t1={t1} mode={end_mode} S={stim_expected} isi={inter_stim_time}")

    if stim_expected is not None and int(stim_expected) <= 0:
        print(f"[TRIALS] No expected stimuli (S={stim_expected})")
        trials = y_tgt.reshape(-1, 1)
        time_rel = np.arange(y_tgt.shape[0], dtype=np.float64) / fs
        dur = time_rel[-1] if time_rel.size else 0.0
        return TrialDataset(
            source=ds.source_path, sampling_rate=fs, channel_index=channel,
            channel_name=(ds.channel_names[channel] if channel < len(ds.channel_names) else f"ch{channel}"),
            unit=(ds.units[channel] if channel < len(ds.units) else ""),
            t0=0.0, t1=dur, time_rel=time_rel,
            trials=trials, onsets_s=[], isi_s=[],
            metadata={
                "end_mode": end_mode,
                "stim_per_trial": 0,          # <- important to keep a trace
                "stim_detected": 0,
                "trials_built": 1,
                "stim_channel_index": int(trig_ch),
                "stim_channel_name": (ds.channel_names[trig_ch] if trig_ch < len(ds.channel_names) else f"ch{trig_ch}"),
                "pad_value": float(pad_value),
                "note": "forced_no_stim",     # <- clear mark of the forced flow
            },
        )
        
    onsets_all = _detect_onsets_abs(y_trig, threshold, debug=debug)
    K = int(onsets_all.size)

    if K == 0:
        trials = y_tgt.reshape(-1, 1)
        time_rel = np.arange(y_tgt.shape[0], dtype=np.float64) / fs
        dur = time_rel[-1] if time_rel.size else 0.0
        return TrialDataset(
            source=ds.source_path, sampling_rate=fs, channel_index=channel,
            channel_name=(ds.channel_names[channel] if channel < len(ds.channel_names) else f"ch{channel}"),
            unit=(ds.units[channel] if channel < len(ds.units) else ""),
            t0=0.0, t1=dur, time_rel=time_rel,
            trials=trials, onsets_s=[], isi_s=[],
            metadata={
                "end_mode": end_mode, "stim_per_trial": int(stim_expected or 1),
                "stim_detected": 0, "trials_built": 1,
                "stim_channel_index": int(trig_ch),
                "stim_channel_name": (ds.channel_names[trig_ch] if trig_ch < len(ds.channel_names) else f"ch{trig_ch}"),
                "pad_value": float(pad_value),
                "note": "no_stimuli",
            },
        )

    # 2) Grouping for cutting
    # El ensamblado del paso 7 agrupa de a S columnas, así que necesita una
    # columna por estímulo. Antes solo se cortaba por estímulo en
    # 'until_next_onset'; en 'fixed' se cortaba ya agrupado y el paso 7 volvía a
    # agrupar: 40 estímulos con S=2 daban 10 trials en vez de 20, y los onsets se
    # vaciaban por no cuadrar con el número de trials. Venía de Gamma Lab 1.0.
    force_per_onset_for_assemble = bool(
        (inter_stim_time and inter_stim_time > 0)
        and (stim_expected and stim_expected > 1)
    )
    stim_per_trial_for_cut = 1 if force_per_onset_for_assemble else (
        1 if not (stim_expected and stim_expected > 0) else int(stim_expected)
    )

    # 3) Groups and windows
    group_starts = _group_onsets_indices(K, stim_per_trial_for_cut)
    windows, Ns = _compute_windows(onsets_all, N, fs, t0, t1, end_mode, group_starts, stim_per_trial_for_cut)

    # 4) Extract matrix
    trials = _extract_trials_matrix(y_tgt, windows, Ns, pad_value)

    # 5) Relative time axis
    time_rel = (np.arange(Ns, dtype=np.int64) / fs).astype(np.float64) + t0
    t1_report = float(time_rel[-1]) if time_rel.size else 0.0

    # 6) Onsets/ISI per group
    first_onsets = [onsets_all[s] for s in group_starts]
    onsets_s_sel = [float(i) / fs for i in first_onsets]

    isi_detail_s, isi_mean_s = [], []
    for s in group_starts:
        a = s; b = min(s + stim_per_trial_for_cut, K)
        grp = onsets_all[a:b]
        if len(grp) >= 2:
            dts = np.diff(grp.astype(np.float64)) / fs
            isi_detail_s.append(dts.tolist())
            isi_mean_s.append(float(np.mean(dts)))
        else:
            isi_detail_s.append([])
            isi_mean_s.append(0.0)

    # 7) Optional assemble
    if (stim_expected and stim_expected >= 2) and (inter_stim_time and inter_stim_time > 0):
        trials = _assemble_trials_general(
            trials, stim_per_trial=int(stim_expected), tis=float(inter_stim_time), fs=fs,
            pad_value=pad_value, debug=debug
        )
        G = (K // int(stim_expected))
        first_onsets = [onsets_all[g * int(stim_expected)] for g in range(G)]
        onsets_s_sel = [float(i) / fs for i in first_onsets]

        isi_detail_s, isi_mean_s = [], []
        for g in range(G):
            a = g * int(stim_expected); b = min(a + int(stim_expected), K)
            grp = onsets_all[a:b]
            if len(grp) >= 2:
                dts = np.diff(grp.astype(np.float64)) / fs
                isi_detail_s.append(dts.tolist())
                isi_mean_s.append(float(np.mean(dts)))
            else:
                isi_detail_s.append([])
                isi_mean_s.append(0.0)

        Ns_new = trials.shape[0]
        time_rel = (np.arange(Ns_new, dtype=np.int64) / fs).astype(np.float64) + t0
        t1_report = float(time_rel[-1]) if time_rel.size else 0.0

    # 8) Sanity check: onsets_s vs T
    if len(onsets_s_sel) not in (0, trials.shape[1]):
        if debug: print(f"[WARN] onsets_s len={len(onsets_s_sel)} != T={trials.shape[1]}. Emptied.")
        onsets_s_sel = []

    return TrialDataset(
        source=ds.source_path, sampling_rate=fs,
        channel_index=channel,
        channel_name=(ds.channel_names[channel] if channel < len(ds.channel_names) else f"ch{channel}"),
        unit=(ds.units[channel] if channel < len(ds.units) else ""),
        t0=float(t0), t1=t1_report,
        time_rel=time_rel, trials=trials,
        onsets_s=onsets_s_sel, isi_s=isi_mean_s,
        metadata={
            "end_mode": end_mode,
            "stim_per_trial": int(stim_expected or stim_per_trial_for_cut),
            "stim_detected": int(K),
            "trials_built": int(trials.shape[1]),
            "stim_channel_index": int(trig_ch),
            "stim_channel_name": (ds.channel_names[trig_ch] if trig_ch < len(ds.channel_names) else f"ch{trig_ch}"),
            "pad_value": float(pad_value),
            "isi_detail_s": isi_detail_s,
            "isi_expected_s": (float(inter_stim_time) if inter_stim_time is not None else None),
            "target_channel_index": int(channel),
            "target_channel_name": (ds.channel_names[channel] if channel < len(ds.channel_names) else f"ch{channel}"),
            "note": "assemble applied" if ((stim_expected or 1) >= 2 and inter_stim_time and inter_stim_time > 0)
                    else "no assemble",
        },
    )


# ============ Revisión de un corte ============
def revisar_corte(td, estimulo=None, unidad: str = "", umbral=None) -> list:
    """Avisos sobre un corte recién hecho. No cambia nada; devuelve frases en español.

    - **Estímulos irregulares.** La detección no tiene antirrebote: cada cruce del
      umbral cuenta. Con el umbral en el ruido del canal de estímulo —el caso
      típico es un canal en V con el umbral por defecto de 0,7 mV, o sea
      0,0007 V— salen «estímulos» a intervalos absurdos, a veces separados por
      menos de un milisegundo, y nada lo decía.
    - **Trials que se solapan** en modo `fixed`: si dos estímulos están más cerca
      que la duración del trial, cada trial incluye el principio del siguiente.

    `estimulo`, `unidad` y `umbral` (en la unidad del canal) son opcionales; con
    ellos el aviso de irregularidad sugiere un umbral.
    """
    avisos = []
    on = np.asarray(td.onsets_s if td.onsets_s is not None else [], dtype=float)
    if on.size < 2:
        return avisos
    isi = np.diff(on)
    minimo = float(isi.min())
    mediana = float(np.median(isi))

    if on.size >= 3 and mediana > 0 and minimo < 0.5 * mediana:
        texto = (f"Los {on.size} estímulos detectados no son regulares: entre uno y el "
                 f"siguiente pasan de {minimo:.3g} a {float(isi.max()):.3g} s (mediana "
                 f"{mediana:.3g} s). Suele pasar cuando el umbral cae en el ruido del canal "
                 f"de estímulo.")
        if estimulo is not None and umbral is not None and np.size(estimulo):
            pico = float(np.nanmax(np.abs(np.asarray(estimulo, dtype=np.float64))))
            if pico > 0 and abs(float(umbral)) < 0.1 * pico:
                factor = mv_to_unit(1.0, unidad)
                if factor:
                    actual = f"{float(umbral) / factor:.4g} mV ({float(umbral):.4g} {unidad})"
                    sugerido = f"{pico / 2 / factor:.4g} mV"
                else:
                    actual = f"{float(umbral):.4g} {unidad}"
                    sugerido = f"{pico / 2:.4g} {unidad}"
                texto += (f" El umbral es {actual} y el canal de estímulo llega a "
                          f"{pico:.4g} {unidad}: prueba con la mitad del pulso, unos {sugerido}.")
        avisos.append(texto)
        return avisos           # un solapamiento aquí sería consecuencia de lo mismo

    if (td.metadata or {}).get("end_mode", "fixed") == "fixed":
        fs = float(td.sampling_rate)
        duracion = td.trials.shape[0] / fs
        if minimo < duracion - 1.5 / fs:
            avisos.append(
                f"Los trials se solapan: hay estímulos separados por {minimo:.3g} s y cada "
                f"trial dura {duracion:.3g} s, así que cada uno incluye el principio del "
                f"siguiente. Baja el tiempo final a {minimo + float(td.t0):.3g} s o menos, o "
                f"usa «Cut to the next stim».")
    return avisos


PASOS_MINIMOS_CONVERSOR = 3
"""Por debajo de esto un canal solo trae el ruido del conversor. Medido en los
registros de test/data: los canales desconectados varían entre 0,6 y 0,8 pasos
y el canal vivo más tranquilo, 8."""


def canal_sin_senal(td):
    """Si el canal parece no tener señal, la frase que lo dice; si no, None.

    Un electrodo desconectado no es plano: el conversor sigue dando un paso
    arriba o abajo. Por eso «desviación cero» —lo único que miraba PPC— no lo
    detecta, y PPC o PAC calculaban sobre ruido del equipo sin decir nada. Se
    mide la dispersión en pasos del conversor (la menor distancia entre dos
    valores distintos) y se toma la menor de la desviación típica y la mediana de
    las desviaciones absolutas, para que unos pocos artefactos de estímulo no
    escondan un canal muerto. Con datos ya filtrados o promediados no hay pasos
    que medir y no se avisa: puede quedar un canal sin detectar, pero nunca se
    marca uno vivo.
    """
    x = np.asarray(td.trials, dtype=np.float64).ravel()
    x = x[np.isfinite(x)]
    if x.size < 2:
        return None
    unidad = getattr(td, "unit", "") or ""
    desviacion = float(x.std())
    if desviacion == 0.0:
        motivo = "es constante"
    else:
        muestra = x[:200_000]
        niveles = np.unique(muestra)
        if niveles.size < 2:
            return None
        paso = float(np.min(np.diff(niveles)))
        robusta = 1.4826 * float(np.median(np.abs(muestra - np.median(muestra))))
        if paso <= 0 or min(desviacion, robusta) >= PASOS_MINIMOS_CONVERSOR * paso:
            return None
        motivo = (f"su desviación típica es de {desviacion:.3g} {unidad}, menos de "
                  f"{PASOS_MINIMOS_CONVERSOR} pasos del conversor ({paso:.3g} {unidad})")
    return (f"El canal '{td.channel_name}' parece no tener señal: {motivo}. Suele ser un "
            f"electrodo desconectado o un canal sin usar; lo que se calcule sobre él mide "
            f"el ruido del equipo, no actividad.")


# ============ Alineación entre dos canales ============
def validar_alineacion(td1, td2):
    """Los dos canales tienen que venir del **mismo corte** y tener los **mismos trials**.

    La usan los análisis entre canales: PPC y PAC Psel entre canales. El plugin
    *Trials* corta un canal por vez y los descartes se marcan en cada canal por
    separado. Si el usuario no usó los mismos parámetros, o descartó trials
    distintos en cada canal, el trial i de uno no es el trial i del otro:
    emparejarlos mezcla estímulos distintos y el resultado sale igual de bonito
    sin medir nada.

    Se comprueba lo que de verdad puede diferir, en el orden en que importa.
    No se recorta al mínimo común en silencio: se dice qué no cuadra.

    Vivía en el `compute.py` de PPC. Está aquí porque PAC Psel entre canales
    necesita la misma comprobación y un plugin no importa a otro; antes PAC solo
    comparaba la forma de las matrices, y con un descarte distinto en cada canal
    las formas coinciden.
    """
    t1, t2 = np.asarray(td1.trials), np.asarray(td2.trials)
    if t1.shape != t2.shape:
        pista = ""
        if t1.ndim == t2.ndim == 2 and t1.shape[0] == t2.shape[0]:
            pista = (" Si los dos se cortaron con la misma receta, lo que cambia son los "
                     "descartes: descarta los mismos trials en los dos canales.")
        raise ValueError(
            f"Los dos canales no tienen la misma forma: '{td1.channel_name}' da "
            f"{t1.shape[0]} muestras × {t1.shape[1]} trial(s) y '{td2.channel_name}' da "
            f"{t2.shape[0]} × {t2.shape[1]}. Vuelve a generarlos con los mismos "
            f"parámetros, cambiando solo el canal." + pista)

    o1, o2 = np.asarray(td1.onsets_s, dtype=float), np.asarray(td2.onsets_s, dtype=float)
    if o1.shape != o2.shape or not np.allclose(o1, o2):
        raise ValueError(
            f"Los trials de '{td1.channel_name}' y '{td2.channel_name}' empiezan en "
            f"instantes distintos, así que no están alineados. O se generaron con "
            f"distinto canal de estímulo o umbral —genéralos con los mismos, cambiando "
            f"solo el canal— o se descartaron trials distintos en cada canal: descarta "
            f"los mismos en los dos.")

    if td1.sampling_rate != td2.sampling_rate:
        raise ValueError(
            f"Los dos canales tienen frecuencias de muestreo distintas: "
            f"{td1.sampling_rate:g} Hz y {td2.sampling_rate:g} Hz.")

    if (td1.t0, td1.t1) != (td2.t0, td2.t1):
        raise ValueError(
            f"Las ventanas de recorte no coinciden: '{td1.channel_name}' va de "
            f"{td1.t0:g} a {td1.t1:g} s y '{td2.channel_name}' de {td2.t0:g} a "
            f"{td2.t1:g} s.")

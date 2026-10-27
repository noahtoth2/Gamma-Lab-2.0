from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

from core.model.trial_dataset import TrialDataset


'''
    Holds raw data transformed directly from the loaded files.
    General format for raw signals.
    Contains metadata and general information about the signal.
'''
@dataclass
class SignalDataset:
    name: str
    format: str                     # "abf"
    source_path: str
    sampling_rate: float            
    time: np.ndarray                
    signals: np.ndarray             
    channel_names: List[str]
    units: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    sampling_rate_source: str = "header"     
    original_sampling_rate: float | None = None  # value auto-detected at load time
    vtk_table = None

    __trials_dataset:List[TrialDataset] = field(default_factory=list)

    __discarded_trials: Dict[tuple[str, str], set[int]] = field(default_factory=dict)


    # Internal cache to avoid recomputing the same trials_dataset
    __filtered_cache: Dict[tuple[str, str], TrialDataset] = field(default_factory=dict, init=False, repr=False)
    __discard_versions: Dict[tuple[str, str], int] = field(default_factory=dict, init=False, repr=False)

    # R79: preprocessing never writes into the cut trials. Its result is a derived
    # TrialDataset (same shape, same discards) kept apart, one per (file, channel);
    # `get_active_trials` serves it, and the original stays available.
    __derived_trials: Dict[tuple[str, str], TrialDataset] = field(default_factory=dict, init=False, repr=False)

    # Add a trial_dataset to the trials list
    def add_trial_dataset(self, trial: "TrialDataset"):
        """Guarda un juego de trials, **reemplazando** el anterior del mismo canal.

        Antes acumulaba: cada *Generate* añadía uno más a la lista y
        `get_active_trials` devolvía el **primero** que coincidiera en canal, o
        sea el más viejo. El efecto era que regenerar los trials con otros
        parámetros no cambiaba nada: los análisis seguían leyendo los de la
        primera vez, y el resultado salía idéntico hasta el último decimal.

        El juego nuevo se añade **al final** aunque reemplace a otro, porque
        `get_active_trials` toma el último de la lista para saber qué canal está
        activo. Si se sustituyera en su sitio, regenerar el canal A dejaría como
        activo al canal B.

        Se tiran también los descartes y la caché de ese canal: sus índices
        apuntaban a los trials viejos y en los nuevos señalarían a otros. Es el
        mismo motivo por el que `replace_trial_datasets` los limpia.
        """
        if not isinstance(trial, TrialDataset):
            raise ValueError("trial must be of type TrialDataset")

        archivo = Path(trial.source).name
        for i, existente in enumerate(self.__trials_dataset):
            if (Path(existente.source).name == archivo
                    and existente.channel_name == trial.channel_name):
                del self.__trials_dataset[i]
                break
        self.__trials_dataset.append(trial)
        self.__olvidar_derivados(trial.channel_name)

    def __olvidar_derivados(self, channel_name: str):
        """Descartes y cachés de un canal, fuera: ya no corresponden a nada."""
        for diccionario in (self.__discarded_trials, self.__filtered_cache,
                            self.__discard_versions, self.__derived_trials):
            for clave in [k for k in diccionario if k[1] == channel_name]:
                diccionario.pop(clave, None)

    def replace_trial_datasets(self, new_trials: List["TrialDataset"]):
        """Swap out all TrialDatasets at once (e.g. after regenerating them
        under a corrected sampling rate, CU-018). Old discards/caches no
        longer apply once the underlying trials have been re-cut."""
        self.__trials_dataset = list(new_trials)
        self.__discarded_trials.clear()
        self.__filtered_cache.clear()
        self.__discard_versions.clear()
        self.__derived_trials.clear()

    # ---------------- sampling rate (CU-018) ----------------
    def set_sampling_rate(self, new_fs: float):
        """Public API to correct the sampling rate (R67): no caller should
        reach into `sampling_rate`/`time` directly. Recomputes the time axis
        and invalidates the cached VTK table so a stale axis is never drawn (R72)."""
        new_fs = float(new_fs)
        if new_fs <= 0:
            raise ValueError("Sampling rate must be greater than zero.")
        n = self.time.shape[0]
        self.sampling_rate = new_fs
        self.time = np.arange(n, dtype=np.float64) / new_fs
        self.sampling_rate_source = "manual"
        self.vtk_table = None

    def restore_original_sampling_rate(self):
        """Restore the sampling rate auto-detected from the file header at load time."""
        if self.original_sampling_rate is None:
            raise ValueError("No original sampling rate was recorded for this signal.")
        self.set_sampling_rate(self.original_sampling_rate)
        self.sampling_rate_source = "header"

    def number_of_trials_dataset(self):
        return len(self.__trials_dataset)

    # ---------------- derived trial sets (R79) ----------------
    def get_original_trials(self, file_name: str, channel_name: str = None):
        """The cut trials as they were generated, never modified by preprocessing."""
        if not self.__trials_dataset:
            return None
        if channel_name is None:
            channel_name = self.__trials_dataset[-1].channel_name
        coincidencias = [t for t in self.__trials_dataset
                         if Path(t.source).name == file_name and t.channel_name == channel_name]
        return coincidencias[-1] if coincidencias else None

    def get_derived_trials(self, file_name: str, channel_name: str = None):
        """The derived set of a (file, channel), or None if nothing was derived."""
        if channel_name is None and self.__trials_dataset:
            channel_name = self.__trials_dataset[-1].channel_name
        return self.__derived_trials.get((file_name, channel_name))

    def register_derived_trials(self, derived: "TrialDataset"):
        """Registers the result of a preprocessing operation as the active set of its channel.

        It must come from an existing original (same file, channel and shape). The
        original is left untouched and stays reachable with `get_original_trials`;
        `discard_derived_trials` goes back to it.
        """
        if not isinstance(derived, TrialDataset):
            raise ValueError("derived must be of type TrialDataset")
        archivo = Path(derived.source).name
        original = self.get_original_trials(archivo, derived.channel_name)
        if original is None:
            raise ValueError(f"There are no original trials for ({archivo}, {derived.channel_name}).")
        if derived.trials.shape != original.trials.shape:
            raise ValueError("A derived set keeps the shape of its original "
                             f"({original.trials.shape}); got {derived.trials.shape}.")
        if derived.trials is original.trials:
            raise ValueError("A derived set must own its data, not share the original's array.")
        derived.metadata = derived.metadata or {}
        derived.metadata["derived_from"] = {"source": archivo, "channel": derived.channel_name}
        key = (archivo, derived.channel_name)
        self.__derived_trials[key] = derived
        self.__invalidate_cache(key)

    def discard_derived_trials(self, file_name: str, channel_name: str) -> bool:
        """Drops the derived set so the original is served again. True if there was one."""
        key = (file_name, channel_name)
        existia = self.__derived_trials.pop(key, None) is not None
        if existia:
            self.__invalidate_cache(key)
        return existia

    def get_all_trials_datasets(self) -> List["TrialDataset"]:
        """All generated TrialDatasets, in generation order (for project save/restore)."""
        return list(self.__trials_dataset)

    def get_discarded_trials_map(self) -> Dict[tuple[str, str], set[int]]:
        """Discarded-trial indices per (source, channel) key (for project save/restore)."""
        return {k: set(v) for k, v in self.__discarded_trials.items()}

    def get_active_trials(self, file_name: str, channel_name: str = None):
        """Los trials activos de un archivo y un canal, ya sin los descartados.

        `channel_name = None` devuelve los del **último canal generado**, que es
        el que la aplicación considera activo. Es lo que piden los nueve plugins
        de análisis: trabajan sobre un canal, el que el usuario acaba de cortar.

        **Pasar un nombre devuelve el de ese canal**, aunque no sea el último.
        Hasta la Fase 2 del plan de PPC el argumento se recibía y se tiraba:

            '''Change in future developments'''
            channel_name = self.__trials_dataset[-1].channel_name

        —una línea que los autores originales dejaron marcada—. La lista **ya**
        guardaba un juego por canal, porque `add_trial_dataset` reemplaza por
        `(archivo, canal)` y no borra los demás; lo que faltaba era poder
        pedirlos. PPC los necesita de dos canales a la vez, y recortar primero
        uno y luego el otro dejaba los dos guardados pero solo uno alcanzable.

        Devuelve `None` si no hay trials, o si no hay ninguno de ese canal.
        """
        if not self.__trials_dataset or len(self.__trials_dataset) == 0:
            print(f"[SignalDataset] The signal '{self.name}' has no TrialDataset loaded yet.")
            return None

        if channel_name is None:
            channel_name = self.__trials_dataset[-1].channel_name

        key = (file_name, channel_name)

        # El ULTIMO que coincida, no el primero. `add_trial_dataset` ya se
        # encarga de que haya uno solo por (archivo, canal), pero cargar un
        # proyecto antiguo puede traer duplicados: quedarse con el primero
        # devolveria el mas viejo.
        coincidencias = [
            t for t in self.__trials_dataset
            if Path(t.source).name == file_name and t.channel_name == channel_name
        ]
        td = coincidencias[-1] if coincidencias else None

        if td is None:
            print(f"[SignalDataset] No dataset found for {key}")
            return None

        # R79: if preprocessing derived this channel, that is what the analyses read
        td = self.__derived_trials.get(key, td)

        # Get the discards specific to that dataset
        discarded = self.__discarded_trials.get(key, set())
        version = len(discarded)

        # If present in cache and discard version hasn't changed, reuse it
        if key in self.__filtered_cache and self.__discard_versions.get(key) == version:
            return self.__filtered_cache[key]

        # If there are no discards, return the original dataset
        if not discarded:
            self.__filtered_cache[key] = td
            self.__discard_versions[key] = version
            return td

        # Apply filter

        Ns, T = td.trials.shape
        valid_mask = np.ones(T, dtype=bool)

        for idx in discarded:
            if 0 <= idx < T:
                valid_mask[idx] = False

        # If all trials are valid, return the original dataset directly
        if valid_mask.all():
            return td

        # Apply the filter only to valid indices
        filtered_trials = td.trials[:, valid_mask]
        filtered_onsets = [on for i, on in enumerate(td.onsets_s) if valid_mask[i]] if td.onsets_s else []

        # Create a new filtered instance (without copying arrays unnecessarily)
        filtered_dataset = TrialDataset(
            source=td.source,
            sampling_rate=td.sampling_rate,
            channel_index=td.channel_index,
            channel_name=td.channel_name,
            unit=td.unit,
            t0=td.t0,
            t1=td.t1,
            time_rel=td.time_rel,
            trials=filtered_trials,
            onsets_s=filtered_onsets,
            isi_s=td.isi_s,
            metadata=td.metadata
        )

        # Cache with current version
        self.__filtered_cache[key] = filtered_dataset
        self.__discard_versions[key] = version

        return filtered_dataset

    def get_active_trial_indices(self, file_name: str, channel_name: str = None) -> List[int]:
        """Indices **originales** de los trials que `get_active_trials` devuelve.

        `get_active_trials` quita las columnas descartadas y pierde la numeracion
        original: la columna k del resultado es el trial `indices[k]` del corte.
        La aplicacion numera los trials por su posicion entre los validos, y esto
        sirve para traducir entre las dos numeraciones (p. ej. el plugin Trials
        navega por el indice original, incluidos los descartados).

        Devuelve `[]` si no hay trials para ese canal.
        """
        if not self.__trials_dataset:
            return []
        if channel_name is None:
            channel_name = self.__trials_dataset[-1].channel_name
        coincidencias = [
            t for t in self.__trials_dataset
            if Path(t.source).name == file_name and t.channel_name == channel_name
        ]
        if not coincidencias:
            return []
        T = coincidencias[-1].trials.shape[1]
        discarded = self.__discarded_trials.get((file_name, channel_name), set())
        return [i for i in range(T) if i not in discarded]

    def discard_trial(self, source: str, channel: str, index: int):
        """Discard a specific trial from the given channel."""
        key = (source, channel)
        self.__discarded_trials.setdefault(key, set()).add(index)
        print(f"discarded trials: {self.__discarded_trials} :")
        self.__invalidate_cache(key)


    def include_trial(self, source: str, channel: str, index: int):
        """Re-include a previously discarded trial."""
        key = (source, channel)
        if key in self.__discarded_trials:
            self.__discarded_trials[key].discard(index)
            if not self.__discarded_trials[key]:
                del self.__discarded_trials[key]  # clean empty entries
        self.__invalidate_cache(key)


    def clear_discarded_trials(self): 
        """Clear all discards and cache."""
        self.__discarded_trials.clear()
        self.__filtered_cache.clear()
        self.__discard_versions.clear()
        print("[SignalDataset] Cache and discards cleared")
    
    def is_trial_discarded(self, source: str, channel: str, index: int) -> bool:
        key = (source, channel)
        return key in self.__discarded_trials and index in self.__discarded_trials[key]


    def __invalidate_cache(self, key: tuple[str, str]):
        if key in self.__filtered_cache:
            del self.__filtered_cache[key]
            del self.__discard_versions[key]
            print(f"[SignalDataset] Cache invalidated for {key}")

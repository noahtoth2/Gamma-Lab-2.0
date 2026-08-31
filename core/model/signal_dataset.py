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
    vtk_table = None

    __trials_dataset:List[TrialDataset] = field(default_factory=list)

    __discarded_trials: Dict[tuple[str, str], set[int]] = field(default_factory=dict)


    # Internal cache to avoid recomputing the same trials_dataset
    __filtered_cache: Dict[tuple[str, str], TrialDataset] = field(default_factory=dict, init=False, repr=False)
    __discard_versions: Dict[tuple[str, str], int] = field(default_factory=dict, init=False, repr=False)

    # Add a trial_dataset to the trials list
    def add_trial_dataset(self, trial: "TrialDataset"):
        if not isinstance(trial, TrialDataset):
            raise ValueError("trial must be of type TrialDataset")
        self.__trials_dataset.append(trial)

    def number_of_trials_dataset(self):
        return len(self.__trials_dataset)

    def get_active_trials(self, file_name: str, channel_name: str = None):
        """
        Return the active TrialDataset for a specific file and channel,
        applying discards defined in self.__discarded_trials.

        Parameters:
            name (str): Source file name.
            channel_name (str): Channel name.

        Returns:
            TrialDataset | None: The filtered dataset or None if it does not exist.
        """

        '''Change in future developments'''
        # Take the last TD if channel_name is not provided

        if not self.__trials_dataset or len(self.__trials_dataset) == 0:
            print(f"[SignalDataset] The signal '{self.name}' has no TrialDataset loaded yet.")
            return None
        
        channel_name = self.__trials_dataset[-1].channel_name

        key = (file_name, channel_name)

        # Find the corresponding dataset
        td = next(
            (t for t in self.__trials_dataset 
             if Path(t.source).name == file_name and t.channel_name == channel_name),
            None
        )

        if td is None:
            print(f"[SignalDataset] No dataset found for {key}")
            return None

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

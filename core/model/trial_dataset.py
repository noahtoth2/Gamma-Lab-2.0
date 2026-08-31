# core/services/trials_matrix.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np

@dataclass
class TrialDataset:
    source: str                         # source file
    sampling_rate: float                # Hz
    channel_index: int                  # channel index used
    channel_name: str                   # channel name
    unit: str                           # channel unit (e.g., "uV", "mV")
    t0: float                           # s (relative to onset)
    t1: float                           # s
    time_rel: np.ndarray                # (Ns,) relative time axis [t0..t1)
    trials: np.ndarray                  # (Ns, T) matrix -> each column is a trial
    onsets_s: List[float]               # onsets in seconds (len = T)
    isi_s: List[float] = field(default_factory=list)    # inter-stimulus intervals (optional)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        assert self.trials.ndim == 2, "trials must be 2D (Ns, T)"
        Ns, T = self.trials.shape
        assert self.time_rel.shape[0] == Ns, "time_rel and trials do not match in Ns"
        assert len(self.onsets_s) == T or len(self.onsets_s) == 0, "onsets_s must match T (or be empty)"

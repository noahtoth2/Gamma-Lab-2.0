from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np

@dataclass
class TrialDataset:
    source: str
    sampling_rate: float
    channel_index: int
    channel_name: str
    unit: str
    t0: float
    t1: float
    time_rel: np.ndarray
    trials: np.ndarray
    onsets_s: List[float]
    isi_s: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        assert self.trials.ndim == 2, "trials must be 2D (Ns, T)"
        Ns, T = self.trials.shape
        assert self.time_rel.shape[0] == Ns, "time_rel and trials do not match in Ns"
        assert len(self.onsets_s) == T or len(self.onsets_s) == 0, "onsets_s must match T (or be empty)"

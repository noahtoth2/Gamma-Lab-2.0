import types
import numpy as np
import pytest
from core.services.fileio_service import FileIOService, SignalDataset

# ---------------------------------------------------------------------
# Dummy classes simulating pyedflib.EdfReader behavior
# ---------------------------------------------------------------------
class _EDFBase:
    def __init__(self, path):
        self._closed = False

    def close(self):
        self._closed = True

class DummyEDF_Uniform(_EDFBase):
    """
    Valid EDF: 2 channels, same length, same fs (uniform).
    """
    def __init__(self, path):
        super().__init__(path)
        self.signals_in_file = 2
        self._n = 1000
        self._fs = [1000.0, 1000.0]
        t = np.arange(self._n) / self._fs[0]
        self._sig = [
            np.sin(2 * np.pi * 10 * t),
            np.cos(2 * np.pi * 7 * t),
        ]

    def readSignal(self, i): return self._sig[i]
    def samplefrequency(self, i): return self._fs[i]
    def getLabel(self, i): return f"ch{i}"
    def getPhysicalDimension(self, i): return "uV"

class DummyEDF_Inconsistent(_EDFBase):
    """
    Invalid EDF: channel sample rates / lengths differ (non-uniform).
    Depending on your implementation this should raise (preferred for a unit test)
    or trigger a resampling path. Here we expect a failure.
    """
    def __init__(self, path):
        super().__init__(path)
        self.signals_in_file = 2
        self._n0, self._n1 = 1000, 900
        self._fs = [1000.0, 500.0]
        t0 = np.arange(self._n0) / self._fs[0]
        t1 = np.arange(self._n1) / self._fs[1]
        self._sig = [
            np.sin(2 * np.pi * 8 * t0),
            np.cos(2 * np.pi * 5 * t1),
        ]

    def readSignal(self, i): return self._sig[i]
    def samplefrequency(self, i): return self._fs[i]
    def getLabel(self, i): return f"ch{i}"
    def getPhysicalDimension(self, i): return "uV"

class DummyEDF_Raises(_EDFBase):
    """
    Corrupted/unreadable EDF: constructor raises.
    """
    def __init__(self, path):
        raise IOError("Not a valid EDF file")

# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------

def test_load_edf_valid_uniform(monkeypatch, tmp_path):
    """
    Valid case: uniform EDF → signals stack cleanly into a SignalDataset.
    """
    import core.services.fileio_service as fileio_mod
    monkeypatch.setattr(
        fileio_mod,
        "pyedflib",
        types.SimpleNamespace(EdfReader=DummyEDF_Uniform),
        raising=True,
    )

    svc = FileIOService()
    ds = svc.load_edf(str(tmp_path / "ok.edf"))

    assert isinstance(ds, SignalDataset)
    assert ds.format == "edf"
    assert ds.signals.shape == (2, 1000)
    # if your loader takes fs from the file, it should be 1000.0
    assert ds.channel_names == ["ch0", "ch1"]
    assert ds.units == ["uV", "uV"]


def test_load_edf_corrupted(monkeypatch, tmp_path):
    """
    Error case: pyedflib.EdfReader raises on open → service should raise.
    """
    import core.services.fileio_service as fileio_mod
    monkeypatch.setattr(
        fileio_mod,
        "pyedflib",
        types.SimpleNamespace(EdfReader=DummyEDF_Raises),
        raising=True,
    )

    svc = FileIOService()
    with pytest.raises((IOError, ValueError)):
        _ = svc.load_edf(str(tmp_path / "bad.edf"))

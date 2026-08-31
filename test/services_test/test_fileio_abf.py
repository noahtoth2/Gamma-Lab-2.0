import types
import numpy as np
import pytest
from core.services.fileio_service import FileIOService, SignalDataset

# ---------------------------------------------------------------------
# Dummy class simulating pyabf.ABF behavior
# ---------------------------------------------------------------------
class DummyABF:
    """
    Simulates a valid ABF file with 2 channels, 1000 samples each, fs=1000 Hz.
    Channel 0: sine wave (5 Hz)
    Channel 1: cosine wave (7 Hz)
    """
    def __init__(self, path):
        self._N = 1000
        self.dataRate  = 1000.0
        self.channelCount = 2
        self.sweepCount = 1 
        self.adcNames = ["ch0", "ch1"]
        self.adcUnits = ["mV", "mV"]

        self.sweepX = np.arange(self._N) / self.dataRate
        t = self.sweepX
        self._data = np.vstack([
            np.sin(2 * np.pi * 5 * t),
            np.cos(2 * np.pi * 7 * t)
        ])
        self._ch = 0  # current channel index

    def setSweep(self, sweepNumber=0, channel=0):
        self._ch = int(channel)

    def setSweepChannel(self, ch):
        self._ch = int(ch)

    @property
    def sweeps(self):
        return [0]

    @property
    def sweepY(self):
        return self._data[self._ch]

# ---------------------------------------------------------------------
# Dummy variants for failure cases
# ---------------------------------------------------------------------
class DummyABF_Raises:
    """Simulates a corrupted or unreadable ABF file."""
    def __init__(self, path):
        raise IOError("Invalid or corrupted ABF file")

class DummyABF_BadShape(DummyABF):
    """Simulates channels with mismatched lengths."""
    def __init__(self, path):
        super().__init__(path)
        self._data[1] = self._data[1][:-10]  # second channel shorter (990 samples)

    @property
    def sweepY(self):
        return self._data[self._ch]

# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------

def test_load_abf_valid(monkeypatch, tmp_path):
    """
    Valid case: correctly formatted ABF file with two channels.
    """
    import core.services.fileio_service as fileio_mod
    monkeypatch.setattr(fileio_mod, "pyabf", types.SimpleNamespace(ABF=DummyABF), raising=True)

    svc = FileIOService()
    ds = svc.load_abf(str(tmp_path / "fake.abf"))

    # Structural checks
    assert isinstance(ds, SignalDataset)
    assert ds.format == "abf"
    assert ds.signals.shape == (2, 1000)
    assert ds.sampling_rate == 1000.0
    assert ds.channel_names == ["ch0", "ch1"]

    # Data consistency checks
    ch0, ch1 = ds.signals
    assert not np.allclose(ch0, ch1)              # channels must differ
    assert np.isclose(ch0[0], 0.0, atol=1e-12)    # sin(0)=0
    assert np.isclose(ch1[0], 1.0, atol=1e-12)    # cos(0)=1
    assert len(ds.time) == ds.signals.shape[1]    # time axis matches signal length


def test_load_abf_corrupted(monkeypatch, tmp_path):
    """
    Error case: the ABF constructor raises an exception (corrupted file).
    """
    import core.services.fileio_service as fileio_mod
    monkeypatch.setattr(fileio_mod, "pyabf", types.SimpleNamespace(ABF=DummyABF_Raises), raising=True)

    svc = FileIOService()
    with pytest.raises((IOError, ValueError)):
        _ = svc.load_abf(str(tmp_path / "bad.abf"))

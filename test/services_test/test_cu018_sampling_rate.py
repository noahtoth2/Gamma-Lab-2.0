import numpy as np
import pytest

from core.model.signal_dataset import SignalDataset


def make_signal(fs=1000.0):
    n = 6000
    t = np.arange(n) / fs
    signals = np.vstack([np.sin(2 * np.pi * 5 * t), np.zeros(n)])
    return SignalDataset(
        name="sig.abf", format="abf", source_path=r"C:\fake\sig.abf",
        sampling_rate=fs, time=t, signals=signals,
        channel_names=["data", "stim"], units=["mV", "V"],
        sampling_rate_source="header", original_sampling_rate=fs,
    )


def test_set_sampling_rate_recomputes_time_and_invalidates_cache():
    ds = make_signal(fs=1000.0)
    old_n = ds.time.shape[0]
    ds.vtk_table = object()  # pretend it was cached

    ds.set_sampling_rate(500.0)

    assert ds.sampling_rate == 500.0
    assert ds.time.shape[0] == old_n
    assert np.isclose(ds.time[1] - ds.time[0], 1.0 / 500.0)
    assert ds.sampling_rate_source == "manual"
    assert ds.vtk_table is None


def test_rejects_non_positive_sampling_rate():
    ds = make_signal(fs=1000.0)
    with pytest.raises(ValueError):
        ds.set_sampling_rate(0.0)
    with pytest.raises(ValueError):
        ds.set_sampling_rate(-10.0)
    assert ds.sampling_rate == 1000.0


def test_restore_original_sampling_rate():
    ds = make_signal(fs=1000.0)
    ds.set_sampling_rate(250.0)
    assert ds.sampling_rate_source == "manual"

    ds.restore_original_sampling_rate()

    assert ds.sampling_rate == 1000.0
    assert ds.sampling_rate_source == "header"


def test_restore_original_without_known_original_raises():
    ds = make_signal(fs=1000.0)
    ds.original_sampling_rate = None
    with pytest.raises(ValueError):
        ds.restore_original_sampling_rate()

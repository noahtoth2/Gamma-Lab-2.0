# test/services_test/test_data_store.py
import pytest
import numpy as np

from core.services.data_store import DataStore
from core.model.signal_dataset import SignalDataset


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def make_signal_dataset(
    C=1, N=100, fs=1000.0, path="dummy.edf", name="dummy", fmt="edf"
) -> SignalDataset:
    signals = np.random.randn(C, N).astype(float)
    time = np.arange(N, dtype=float) / fs
    ch_names = [f"ch{i}" for i in range(C)]
    units = ["u"] * C
    return SignalDataset(
        name=name,
        format=fmt,
        source_path=path,
        sampling_rate=fs,
        time=time,
        signals=signals,
        channel_names=ch_names,
        units=units,
        metadata={},
    )


# ---------------------------------------------------------------------
# Basic key-value operations
# ---------------------------------------------------------------------
def test_set_get_has_remove_and_items():
    ds = DataStore()
    ds.set("a", 123)
    ds.set("b", {"x": 1})

    assert ds.has("a")
    assert ds.has("b")
    assert not ds.has("c")

    assert ds.get("a") == 123
    assert ds.get("zzz", default="nope") == "nope"

    items = dict(ds.items())
    assert items["a"] == 123 and items["b"] == {"x": 1}

    ds.remove("a")
    assert not ds.has("a")
    assert ds.has("b")


# ---------------------------------------------------------------------
# add_signal & get_signals
# ---------------------------------------------------------------------
def test_add_signal_with_explicit_key_and_get_signals_filters():
    store = DataStore()
    sig = make_signal_dataset()
    key = store.add_signal(sig, key="raw_signal_main")

    assert key == "raw_signal_main"
    assert store.get("raw_signal_main") is sig

    # Non-signal entry should NOT appear in get_signals
    store.set("misc", 42)
    signals = store.get_signals()
    assert "raw_signal_main" in signals and "misc" not in signals
    assert signals["raw_signal_main"] is sig


def test_add_signal_auto_keys_increment():
    store = DataStore()
    k1 = store.add_signal(make_signal_dataset())
    k2 = store.add_signal(make_signal_dataset())
    k3 = store.add_signal(make_signal_dataset())
    # Expected pattern: raw_signal_1, raw_signal_2, raw_signal_3
    assert k1.endswith("_1") and k2.endswith("_2") and k3.endswith("_3")
    assert store.has(k1) and store.has(k2) and store.has(k3)


# ---------------------------------------------------------------------
# Active signal management
# ---------------------------------------------------------------------
def test_set_active_signal_success_and_getters():
    store = DataStore()
    k1 = store.add_signal(make_signal_dataset(name="sig1"))
    k2 = store.add_signal(make_signal_dataset(name="sig2"))

    store.set_active_signal(k2)

    assert store.get_active_signal_key() == k2
    assert store.get_active_signal() is store.get(k2)
    assert store.is_active_signal(k2) is True
    assert store.is_active_signal(k1) is False


def test_set_active_signal_invalid_key_raises():
    store = DataStore()
    with pytest.raises(ValueError):
        store.set_active_signal("not_there")


def test_set_active_signal_non_signal_raises():
    store = DataStore()
    store.set("not_a_signal", {"foo": "bar"})
    with pytest.raises(ValueError):
        store.set_active_signal("not_a_signal")


def test_clear_active_signal_and_is_active_signal():
    store = DataStore()
    key = store.add_signal(make_signal_dataset())
    store.set_active_signal(key)
    assert store.is_active_signal(key) is True

    store.clear_active_signal()
    assert store.get_active_signal() is None
    assert store.get_active_signal_key() is None
    assert store.is_active_signal(key) is False

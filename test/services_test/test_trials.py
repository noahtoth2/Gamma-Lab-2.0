# test/trials_test/test_trials.py
import math
import numpy as np
import pytest

# SUT
import core.filters.trials as tr
from core.model.signal_dataset import SignalDataset


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def impulse_train(length, idxs, amp=1.0):
    x = np.zeros(length, dtype=float)
    for i in idxs:
        if 0 <= i < length:
            x[i] = amp
    return x


def sine(N, f, fs):
    t = np.arange(N) / fs
    return np.sin(2 * np.pi * f * t)


def make_signal_dataset(signals, fs, ch_names=None, units=None, path="dummy.edf", name="dummy", fmt="edf"):
    """
    Build a real SignalDataset instance (no ad-hoc stubs).
    - signals: array-like (C, N)
    - fs: sampling rate (float)
    """
    signals = np.asarray(signals, dtype=float)
    if signals.ndim == 1:
        signals = signals[None, :]
    C, N = signals.shape
    time = np.arange(N, dtype=float) / float(fs)
    ch_names = ch_names or [f"ch{i}" for i in range(C)]
    units = units or ["u"] * C
    return SignalDataset(
        name=name,
        format=fmt,
        source_path=path,
        sampling_rate=float(fs),
        time=time,
        signals=signals,
        channel_names=ch_names,
        units=units,
        metadata={}
    )


def _asdict(x):
    """Access either dict-like or attribute-based result."""
    if isinstance(x, dict):
        return x
    return {
        "trials": getattr(x, "trials"),
        "time_rel": getattr(x, "time_rel"),
        "onsets_s": getattr(x, "onsets_s", []),
        "isi_s": getattr(x, "isi_s", []),
        "metadata": getattr(x, "metadata", {}),
    }


# ---------------------------------------------------------------------
# _detect_onsets_abs
# ---------------------------------------------------------------------

def test_detect_onsets_abs_no_crossings():
    x = np.zeros(100)
    idxs = tr._detect_onsets_abs(x, threshold=0.5)
    assert idxs.size == 0


def test_detect_onsets_abs_single_crossing():
    N, thr = 100, 0.5
    x = np.zeros(N)
    x[37] = 1.0
    idxs = tr._detect_onsets_abs(x, threshold=thr)
    assert idxs.tolist() == [37]


def test_detect_onsets_abs_multiple_crossings_mixed_sign():
    N, thr = 120, 0.5
    x = np.zeros(N)
    x[10] = +1.0
    x[55] = -2.0
    x[90] = +0.6
    idxs = tr._detect_onsets_abs(x, threshold=thr)
    assert idxs.tolist() == [10, 55, 90]



# ---------------------------------------------------------------------
# _compute_windows (fixed / until_next_onset)
# windows items are tuples: (a_clip, b_clip, lead_pad)
# ---------------------------------------------------------------------

def test_compute_windows_fixed_basic_clipping_and_ns():
    fs = 1000.0
    N = 2000
    onsets = np.array([1000])
    t0, t1 = -0.05, 0.15
    group_starts = [0]
    S = 1

    windows, Ns = tr._compute_windows(
        onsets_all=onsets,
        N=N,
        fs=fs,
        t0=t0,
        t1=t1,
        end_mode="fixed",
        group_starts=group_starts,
        stim_per_trial_for_cut=S
    )
    assert Ns == int(round((t1 - t0) * fs))
    a_clip, b_clip, lead_pad = windows[0]
    n0 = int(round(t0 * fs))
    assert a_clip == max(0, onsets[0] + n0)
    assert b_clip == min(N, a_clip + Ns)
    # accept native int or NumPy integer
    assert isinstance(lead_pad, (int, np.integer))


def test_compute_windows_until_next_onset_groups_and_last_to_end():
    fs = 1000.0
    N = 2000
    onsets = np.array([100, 300, 500, 700])
    t0 = -0.01
    group_starts = [0, 2]  # two groups: [0..1], [2..3]
    S = 2

    windows, Ns = tr._compute_windows(
        onsets_all=onsets,
        N=N,
        fs=fs,
        t0=t0,
        t1=0.0,  # ignored in this mode
        end_mode="until_next_onset",
        group_starts=group_starts,
        stim_per_trial_for_cut=S
    )
    n0 = int(round(t0 * fs))
    a0, b0, _ = windows[0]
    assert a0 == max(0, onsets[0] + n0)
    assert b0 == onsets[2]

    a1, b1, _ = windows[1]
    assert a1 == max(0, onsets[2] + n0)
    assert b1 == N

    assert Ns == max(b0 - a0, b1 - a1)


# ---------------------------------------------------------------------
# _extract_trials_matrix
# ---------------------------------------------------------------------

def test_extract_trials_matrix_alignment_and_padding():
    y = np.arange(100, dtype=float)
    # We want a lead_pad of 2 for the first column:
    # start index = a_clip - a_orig -> 2  => a_orig = a_clip - 2 = 8
    windows = [
        (10, 25, 8),   # unclipped a = 8  -> lead_pad = 2
        (50, 60, 50),  # unclipped a = 50 -> lead_pad = 0
    ]
    Ns = 20
    pad = np.nan

    M = tr._extract_trials_matrix(y_tgt=y, windows=windows, Ns=Ns, pad_value=pad)
    assert M.shape == (Ns, 2)

    # Column 0 starts with 2 NaNs (lead_pad)
    assert np.isnan(M[0, 0]) and np.isnan(M[1, 0])
    # Then the real data from y[10:25] (15 samples)
    np.testing.assert_allclose(M[2:2 + 15, 0], y[10:25])
    # Tail padded
    assert np.all(np.isnan(M[17:, 0]))

    # Column 1 starts at offset 0 (no lead pad), contains 10 samples then pad
    np.testing.assert_allclose(M[0:10, 1], y[50:60])
    assert np.all(np.isnan(M[10:, 1]))


# ---------------------------------------------------------------------
# _assemble_trials_general
# ---------------------------------------------------------------------

def test_assemble_trials_general_groups_three_per_trial():
    fs = 1000.0
    pad = np.nan
    Ns_in = 5
    raw = np.arange(Ns_in * 6, dtype=float).reshape(Ns_in, 6)  # 6 columns
    S = 3
    out = tr._assemble_trials_general(
        trials=raw,
        stim_per_trial=S,
        tis=0.1,
        fs=fs,
        pad_value=pad,
        debug=False
    )
    # Expect 6/3 = 2 output columns
    assert out.shape[1] == 2
    # Rows follow implementation: head_len = min(floor(tis*fs), Ns_in)
    head_len = min(int(math.floor(0.1 * fs)), Ns_in)
    expected_rows = head_len + (S - 1) * Ns_in
    assert out.shape[0] == expected_rows


# ---------------------------------------------------------------------
# cut_trials_single_channel (end-to-end) — using REAL SignalDataset
# ---------------------------------------------------------------------

def test_cut_trials_no_stimuli_returns_single_column():
    fs = 1000.0
    N = 2000
    sig0 = sine(N, f=10, fs=fs)
    sig1 = np.zeros(N)
    ds = make_signal_dataset(np.vstack([sig0, sig1]), fs)

    res = tr.cut_trials_single_channel(
        ds=ds,
        channel=0,
        stim_channel=1,
        threshold=0.5,
        t0=0.0,
        t1=1.0,
        end_mode="fixed",
        stim_expected=1,
        inter_stim_time=0.0,
        pad_value=np.nan,
        debug=False,
    )
    R = _asdict(res)
    assert R["trials"].shape[1] == 1
    assert R["onsets_s"] == [] or len(R["onsets_s"]) == 0
    assert isinstance(R["time_rel"], np.ndarray)
    assert "stim_detected" in R["metadata"]


def test_cut_trials_forced_no_stimulus_even_with_triggers():
    fs = 1000.0
    N = 1000
    sig0 = sine(N, f=5, fs=fs)
    sig1 = impulse_train(N, [100, 500, 800], amp=1.0)
    ds = make_signal_dataset(np.vstack([sig0, sig1]), fs)

    res = tr.cut_trials_single_channel(
        ds=ds,
        channel=0,
        stim_channel=1,
        threshold=0.5,
        t0=0.0,
        t1=0.5,
        end_mode="fixed",
        stim_expected=0,        # force no-stim
        inter_stim_time=0.0,
        pad_value=np.nan,
        debug=False,
    )
    R = _asdict(res)
    assert R["trials"].shape[1] == 1
    assert R["metadata"].get("stim_per_trial", None) == 0


def test_cut_trials_single_stim_fixed_window_alignment_and_ns():
    fs = 1000.0
    N = 4000
    on = [1000, 3000]
    sig0 = sine(N, f=8, fs=fs)
    sig1 = impulse_train(N, on, amp=1.0)
    ds = make_signal_dataset(np.vstack([sig0, sig1]), fs)

    t0, t1 = -0.05, 0.15
    res = tr.cut_trials_single_channel(
        ds=ds,
        channel=0,
        stim_channel=1,
        threshold=0.5,
        t0=t0,
        t1=t1,
        end_mode="fixed",
        stim_expected=1,
        inter_stim_time=0.0,
        pad_value=np.nan,
        debug=False,
    )
    R = _asdict(res)
    trials = R["trials"]
    Ns = int(round((t1 - t0) * fs))
    assert trials.shape == (Ns, len(on))

    n0 = int(round(t0 * fs))  # negative
    zero_idx = -n0 if -n0 < Ns else Ns - 1
    for k, onset in enumerate(on):
        col_val = trials[zero_idx, k]
        sig_val = ds.signals[0, onset]
        assert abs(col_val - sig_val) < 1e-6


def test_cut_trials_single_stim_until_next_onset_variable_lengths():
    fs = 1000.0
    N = 2000
    on = [100, 300, 450]
    sig0 = sine(N, f=5, fs=fs)
    sig1 = impulse_train(N, on, amp=1.0)
    ds = make_signal_dataset(np.vstack([sig0, sig1]), fs)

    res = tr.cut_trials_single_channel(
        ds=ds,
        channel=0,
        stim_channel=1,
        threshold=0.5,
        t0=-0.01,
        t1=0.0,  # ignored
        end_mode="until_next_onset",
        stim_expected=1,
        inter_stim_time=0.0,
        pad_value=np.nan,
        debug=False,
    )
    R = _asdict(res)
    trials = R["trials"]
    assert trials.shape[1] == 3

    # At least one earlier column should be shorter than the max-length column → expect some NaNs somewhere
    assert np.isnan(trials[:, 0]).any() or np.isnan(trials[:, 1]).any()


def test_cut_trials_multi_stim_assemble_ok():
    fs = 1000.0
    N = 4000
    # 2 trials, each with 3 stimuli, equally spaced by 100 ms
    on = [500, 600, 700, 2500, 2600, 2700]
    sig0 = sine(N, f=12, fs=fs)
    sig1 = impulse_train(N, on, amp=1.0)
    ds = make_signal_dataset(np.vstack([sig0, sig1]), fs)

    res = tr.cut_trials_single_channel(
        ds=ds,
        channel=0,
        stim_channel=1,
        threshold=0.5,
        t0=-0.02,
        t1=0.08,
        end_mode="fixed",
        stim_expected=3,
        inter_stim_time=0.1,
        pad_value=np.nan,
        debug=False,
    )
    R = _asdict(res)
    assert R["trials"].shape[1] == 2
    assert R["metadata"].get("stim_per_trial") == 3
    assert R["metadata"].get("stim_detected") == len(on)
    assert len(R["onsets_s"]) in (0, 2)


def test_cut_trials_stim_channel_differs_from_target_channel():
    fs = 1000.0
    N = 3000
    on = [500, 1500, 2500]
    sig0 = sine(N, f=7, fs=fs)          # target
    sig1 = impulse_train(N, on, 1.0)    # stim
    ds = make_signal_dataset(np.vstack([sig0, sig1]), fs)

    res = tr.cut_trials_single_channel(
        ds=ds,
        channel=0,
        stim_channel=1,
        threshold=0.5,
        t0=-0.02,
        t1=0.08,
        end_mode="fixed",
        stim_expected=1,
        inter_stim_time=0.0,
        pad_value=np.nan,
        debug=False,
    )
    R = _asdict(res)
    assert R["trials"].shape[1] == len(on)
    zero_idx = int(round(-(-0.02 * fs)))
    for k, onset in enumerate(on):
        assert abs(R["trials"][zero_idx, k] - ds.signals[0, onset]) < 1e-6


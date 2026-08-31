from typing import List, Optional, Literal, Tuple
import math
import numpy as np
from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset

EndMode = Literal["fixed", "until_next_onset"]

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
    force_per_onset_for_assemble = (
        end_mode == "until_next_onset"
        and (inter_stim_time and inter_stim_time > 0)
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

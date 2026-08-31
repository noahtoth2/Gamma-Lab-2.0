# plugins/preprocessing/prepare/artifact_remove/artifact_logic.py
from typing import List, Tuple
import numpy as np
from pathlib import Path
from scipy.interpolate import CubicSpline

LOGL = "[ArtifactLogic]"

# ----------------- Helpers -----------------

def _get_active_signal_and_name(kernel):
    store = kernel.get_service("DataStore")
    if not store:
        raise RuntimeError("DataStore missing.")
    sd = store.get_active_signal()
    if sd is None:
        raise RuntimeError("No active signal.")
    # SignalDataset uses file_name (Path(source).name) as key.
    # Try to take it from the last TrialDataset if available; otherwise from source_path.
    file_name = None
    try:
        if sd.trials_dataset:
            file_name = Path(sd.trials_dataset[-1].source).name
    except Exception:
        pass
    if not file_name:
        file_name = Path(getattr(sd, "source_path", "")).name or getattr(sd, "name", None)
    if not file_name:
        raise RuntimeError("Active signal has no file name.")
    return sd, file_name

def _get_current_channel_name(sd) -> str:
    """
    Current channel resolution order:
      1) channel_name from the last TrialDataset
      2) first name in sd.channel_names
      3) 'ch-1' if there are signals loaded
    """
    try:
        if sd.trials_dataset:
            ch = getattr(sd.trials_dataset[-1], "channel_name", None)
            if ch:
                return str(ch)
    except Exception:
        pass
    try:
        names = getattr(sd, "channel_names", None)
        if names and len(names) > 0:
            return str(names[0])
    except Exception:
        pass
    sig = getattr(sd, "signals", None)
    if sig is not None and getattr(sig, "shape", None) and sig.shape[0] > 0:
        return "ch-1"
    raise RuntimeError("No channel selected/found. Generate Trials first or select a channel.")

def _time_window_indices(t: np.ndarray, a: float, b: float) -> Tuple[int, int]:
    """Return indices [i_a, i_b) for window [a, b] (swap if b<a)."""
    if b < a:
        a, b = b, a
    i_a = int(np.searchsorted(t, a, side="left"))
    i_b = int(np.searchsorted(t, b, side="right"))
    i_a = max(0, min(i_a, t.shape[0]))
    i_b = max(0, min(i_b, t.shape[0]))
    return i_a, i_b


def _fill_nan_segments(t: np.ndarray, data: np.ndarray) -> np.ndarray:
    """
    Replace NaN/Inf segments column-wise using interpolation so downstream analysis
    receives finite values. Uses np.interp which clamps to edge values when the
    NaN block touches the start/end.
    """
    if not np.isnan(data).any():
        return data

    for col in range(data.shape[1]):
        y = data[:, col]
        valid = np.isfinite(y)
        if valid.all():
            continue
        idx = np.where(valid)[0]
        if idx.size == 0:
            data[:, col] = 0.0
            continue
        data[:, col] = np.interp(t, t[idx], y[idx])
    return data

# ----------------- Public logic -----------------

def apply_modification_to_all_valid(kernel, *, mode: str, point_a: float, point_b: float = 0.0):
    """
    Modify values inside ACTIVE trials without re-segmentation or discards:
      - mode='blank' (alias 'cut'): set NaN in [A,B] or until A if B is missing.
      - mode='interpolate': fill [A,B] using cubic spline (natural) when possible; otherwise linear.
    Reads active trials with SignalDataset.get_active_trials(...), and writes modifications
    back to the base TrialDataset (sd.trials_dataset) by mapping active columns
    to original indices using sd.discarded_trials[(file_name, channel_name)].
    """
    sd, file_name = _get_active_signal_and_name(kernel)
    channel_name = _get_current_channel_name(sd)

    # 1) Read ACTIVE trials (filtered by discards) from the dataset
    td_active = sd.get_active_trials(file_name, channel_name)
    if td_active is None:
        raise RuntimeError(f"No active trials for ({file_name}, {channel_name}).")

    t = np.asarray(td_active.time_rel)          # (Ns,)
    trials_active = np.asarray(td_active.trials)  # (Ns, T_act)
    if t.ndim != 1 or trials_active.ndim != 2:
        raise RuntimeError(f"Active trials missing (time_rel or trials).")
    Ns, T_act = trials_active.shape
    if T_act == 0:
        return None

    # 1.5) Prefer file_name from the active trials metadata/source if available
    try:
        active_src = getattr(td_active, "source", None)
        if active_src is None:
            active_src = getattr(getattr(td_active, "metadata", {}), "get", lambda *_: None)("source")
        if active_src:
            file_name = Path(active_src).name
    except Exception:
        pass

    # 2) Find BASE TrialDataset (unfiltered) for this file+channel
    td_list = getattr(sd, "_SignalDataset__trials_dataset", [])
    td_base = next(
        (tdb for tdb in td_list
         if Path(getattr(tdb, "source", "")).name == file_name and getattr(tdb, "channel_name", None) == channel_name),
        None
    )
    # Fallbacks: by channel and sample count, or by channel only (last occurrence)
    if td_base is None:
        try:
            ns = trials_active.shape[0]
            candidates = [tdb for tdb in td_list
                          if getattr(tdb, "channel_name", None) == channel_name]
            td_base = next((tdb for tdb in candidates if getattr(tdb.trials, "shape", (0,))[0] == ns),
                           candidates[-1] if candidates else None)
        except Exception:
            td_base = None
    if td_base is None:
        raise RuntimeError(f"No base TrialDataset found for ({file_name}, {channel_name}).")
    if td_base.trials.shape[0] != Ns:
        raise RuntimeError(f"Shape mismatch: base Ns={td_base.trials.shape[0]} vs active Ns={Ns}.")

    # 3) Build ACTIVE → ORIGINAL index mapping using discarded_trials if present
    discarded_dict = getattr(sd, "_SignalDataset__discarded_trials", {})
    discarded = discarded_dict.get((file_name, channel_name), set()) or set()
    T_total = td_base.trials.shape[1]
    if not discarded and isinstance(discarded_dict, dict):
        # Try alternate keys by filename stem
        stem = Path(file_name).stem
        for (k_file, k_ch), disc in discarded_dict.items():
            try:
                if k_ch == channel_name and Path(k_file).stem == stem:
                    discarded = disc or set()
                    break
            except Exception:
                continue
    orig_indices = [i for i in range(T_total) if i not in discarded]
    # If mapping length still mismatched, assume no discards
    if len(orig_indices) != T_act:
        # Safety: adjust to shorter length (e.g., if discards changed live)
        T_act = min(T_act, len(orig_indices))
        trials_active = trials_active[:, :T_act]
        orig_indices = orig_indices[:T_act]

    # 4) Create a copy to modify
    out_active = trials_active.copy()

    if mode in ("blank", "cut"):
        if point_b and point_b != point_a:
            i_a, i_b = _time_window_indices(t, point_a, point_b)
            if i_b > i_a:
                out_active[i_a:i_b, :] = np.nan
            else:
                return None
        else:
            # blank until A
            i_a = int(np.searchsorted(t, point_a, side="left"))
            i_a = max(0, min(i_a, Ns))
            if i_a > 0:
                out_active[:i_a, :] = np.nan
            else:
                return None

    elif mode == "interpolate":
        if point_a == point_b:
            raise ValueError("Points A and B cannot be the same for interpolation.")
        i_a, i_b = _time_window_indices(t, point_a, point_b)
        if i_b - i_a < 2:
            return None
        for j in range(T_act):
            y = out_active[:, j].copy()
            valid = np.isfinite(y)
            # Exclude the interval [i_a, i_b) from the fit; we want to bridge over it
            keep = valid.copy()
            keep[i_a:i_b] = False

            x_keep = t[keep]
            y_keep = y[keep]

            if x_keep.size >= 4:
                try:
                    spline = CubicSpline(x_keep, y_keep, bc_type='natural')
                    y[i_a:i_b] = spline(t[i_a:i_b])
                    out_active[:, j] = y
                    continue
                except Exception:
                    # Fallback to linear interpolation if spline fails
                    pass

            # Linear fallback (uses points outside the interval)
            if x_keep.size >= 2:
                ya = np.interp(t[i_a], x_keep, y_keep)
                yb = np.interp(t[i_b-1], x_keep, y_keep)
                r = np.linspace(0.0, 1.0, i_b - i_a)
                y[i_a:i_b] = ya + (yb - ya) * r
                out_active[:, j] = y
            # else: not enough context to interpolate — leave as-is
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Smooth NaN segments so later analysis plugins receive finite values
    out_active = _fill_nan_segments(t, out_active)

    # 5) Write changes into the BASE TrialDataset (by mapped columns)
    for k, orig_col in enumerate(orig_indices):
        if 0 <= orig_col < td_base.trials.shape[1]:
            td_base.trials[:, orig_col] = out_active[:, k]

    # 5.5) Invalidate filtered cache so get_active_trials recomputes arrays after edits
    key = (file_name, channel_name)
    try:
        cache = getattr(sd, "_SignalDataset__filtered_cache", None)
        if isinstance(cache, dict):
            cache.pop(key, None)
        versions = getattr(sd, "_SignalDataset__discard_versions", None)
        if isinstance(versions, dict):
            versions.pop(key, None)
    except Exception:
        pass

    # 6) Mark metadata of modified trials (optional)
    try:
        mods = td_base.metadata.get("modified_trials", set())
        mods = set(mods)
        mods.update(orig_indices)
        td_base.metadata["modified_trials"] = mods
    except Exception:
        td_base.metadata = getattr(td_base, "metadata", {}) or {}
        td_base.metadata["modified_trials"] = set(orig_indices)

    # 7) Notify the UI (if the pipeline uses it)
    if hasattr(kernel, "event"):
        try:
            kernel.event.emit("trials_generated", {"signal": file_name, "channel": channel_name})
        except Exception:
            pass

    print(f"{LOGL} Mode='{mode}' applied to {len(orig_indices)} active trials on ({file_name}, {channel_name}).")
    return True

import numpy as np
from bisect import bisect_left, bisect_right
from math import isfinite
def two_point_metrics(p1, p2, kind="slope"):
    """
    p1, p2: tuples (x, y)
    """
    x1, y1 = map(np.float64, p1)
    x2, y2 = map(np.float64, p2)

    dx = x2 - x1
    dy = y2 - y1

    # Slope and Euclidean distance
    slope = np.inf if dx == 0 else dy / dx
    dist = np.hypot(dx, dy)

    # Homogeneous output
    return {
        "type": kind,
        "p1": (float(x1), float(y1)),
        "p2": (float(x2), float(y2)),
        "dx": float(dx),
        "dy": float(dy),
        "slope": float(slope),
        "dist": float(dist),
    }
    
def _slice_window(xs, ys, x1, x2):
    """Return (i0, i1) and views xs[i0:i1], ys[i0:i1] with x1<=x<x2."""
    if x2 < x1:
        x1, x2 = x2, x1
    i0 = bisect_left(xs, x1)
    i1 = bisect_right(xs, x2)
    i0 = max(0, min(i0, len(xs)))
    i1 = max(i0, min(i1, len(xs)))
    return i0, i1, xs[i0:i1], ys[i0:i1]

def amplitude_in_window(xs, ys, x1, x2):
    """
    Peak-to-peak amplitude in [x1, x2].
    Returns a dict:
      {
        "type": "amplitude",
        "x1": x1r, "x2": x2r, "n": n,
        "y_min": y_min, "y_max": y_max,
        "amp_pp": y_max - y_min,
        "x_at_min": x_at_min, "x_at_max": x_at_max
      }
    """
    i0, i1, wxs, wys = _slice_window(xs, ys, x1, x2)
    n = len(wxs)
    if n == 0:
        return None

    # Find min and max within the window
    y_min = None; y_max = None
    j_min = j_max = None
    for j, v in enumerate(wys):
        if v is None or not isfinite(v):
            continue
        if y_min is None or v < y_min:
            y_min = v; j_min = j
        if y_max is None or v > y_max:
            y_max = v; j_max = j

    if y_min is None or y_max is None:
        return None

    res = {
        "type": "amplitude",
        "x1": float(wxs[0]), "x2": float(wxs[-1]),
        "n": int(n),
        "y_min": float(y_min), "y_max": float(y_max),
        "amp_pp": float(y_max - y_min),
        "x_at_min": float(wxs[j_min]),
        "x_at_max": float(wxs[j_max]),
    }
    return res


def derivative_in_window(xs, ys, x1, x2, max_curve_points=500):
    """
    Derivative dy/dx of the signal, sample by sample, inside [x1, x2].

    Uses central differences (numpy.gradient) with the real X spacing, so the
    result is in signal units per X unit (e.g. mV/s).
    Returns a dict:
      {
        "type": "difference",
        "x1", "x2", "n",
        "d_mean":  mean derivative in the window,
        "d_max", "x_at_dmax", "d_min", "x_at_dmin",
        "curve": [(x, dy/dx), ...]   (at most `max_curve_points`, for drawing)
      }
    or None when the window has fewer than 2 samples.
    """
    i0, i1, wxs, wys = _slice_window(xs, ys, x1, x2)
    x = np.asarray(wxs, dtype=np.float64)
    y = np.asarray(wys, dtype=np.float64)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 2:
        return None

    d = np.gradient(y, x)
    j_max = int(np.nanargmax(d))
    j_min = int(np.nanargmin(d))

    paso = max(1, int(np.ceil(x.size / float(max_curve_points))))
    curve = [(float(a), float(b)) for a, b in zip(x[::paso], d[::paso])]

    return {
        "type": "difference",
        "x1": float(x[0]), "x2": float(x[-1]),
        "n": int(x.size),
        "d_mean": float(np.nanmean(d)),
        "d_max": float(d[j_max]), "x_at_dmax": float(x[j_max]),
        "d_min": float(d[j_min]), "x_at_dmin": float(x[j_min]),
        "curve": curve,
    }

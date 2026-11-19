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

    slope = np.inf if dx == 0 else dy / dx
    dist = np.hypot(dx, dy)

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


def derivative_in_window(xs, ys, x1, x2):
    """
    Derivative of the signal inside [x1, x2], as the tutor asked: diff of the vector.

        d = diff(y) / diff(x)        (signal units per X unit, e.g. mV/s)

    Each value belongs to the midpoint between two samples. The maximum is the
    measurement; the minimum is also reported, useful when the response is a negative wave.

    Returns a dict, or None when the window has fewer than 2 samples:
      {
        "type": "difference", "x1", "x2", "n",
        "d_mean", "d_max", "x_at_dmax", "y_at_dmax", "d_min", "x_at_dmin", "y_at_dmin",
        "tangent": [(x, y), (x, y)]   short line of slope d_max through the maximum, for drawing
      }
    """
    x_all = np.asarray(xs, dtype=np.float64)
    y_all = np.asarray(ys, dtype=np.float64)

    i0, i1, _, _ = _slice_window(x_all, y_all, x1, x2)
    x = x_all[i0:i1]
    y = y_all[i0:i1]
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 2:
        return None

    dx = np.diff(x)
    valido = dx > 0
    if not np.any(valido):
        return None
    d = np.diff(y)[valido] / dx[valido]
    xm = ((x[:-1] + x[1:]) / 2.0)[valido]
    ym = ((y[:-1] + y[1:]) / 2.0)[valido]

    j_max = int(np.argmax(d))
    j_min = int(np.argmin(d))

    medio = (x[-1] - x[0]) / 8.0
    x0, y0, m = float(xm[j_max]), float(ym[j_max]), float(d[j_max])
    tangent = [(x0 - medio, y0 - m * medio), (x0 + medio, y0 + m * medio)]

    return {
        "type": "difference",
        "x1": float(x[0]), "x2": float(x[-1]),
        "n": int(x.size),
        "d_mean": float(np.mean(d)),
        "d_max": m, "x_at_dmax": x0, "y_at_dmax": y0,
        "d_min": float(d[j_min]), "x_at_dmin": float(xm[j_min]), "y_at_dmin": float(ym[j_min]),
        "tangent": tangent,
    }

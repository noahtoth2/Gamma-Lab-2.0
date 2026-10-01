# plugins/preprocessing/prepare/artifact_remove/compute.py
"""Cálculo puro de la modificación de artefactos.

Es lo que corre dentro del orquestador (TaskService): recibe arreglos de NumPy
y devuelve arreglos de NumPy. No toca el Kernel, el DataStore ni ningún widget;
la lectura y la escritura de los trials viven en artifact_logic.py y corren en
el hilo de la interfaz.
"""
from typing import Tuple

import numpy as np
from scipy.interpolate import CubicSpline


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


def calcular_modificacion(t, trials, *, mode: str, point_a: float, point_b: float = 0.0, ctx=None):
    """
    Devuelve una copia modificada de `trials` (muestras × trials activos), o None si
    no hay nada que modificar o si se canceló.

      - mode='blank' (alias 'cut'): NaN en [A, B], o hasta A si no hay B; después
        esos tramos se rellenan interpolando para que los análisis reciban valores finitos.
      - mode='interpolate': rellena [A, B] con un spline cúbico natural cuando se puede;
        si no, con una recta.

    `ctx` lo inyecta el orquestador: permite cancelar entre trial y trial y reportar avance.
    """
    t = np.asarray(t)
    Ns, T_act = trials.shape
    out_active = trials.copy()

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
            raise ValueError("Los puntos A y B no pueden ser iguales para interpolar.")
        i_a, i_b = _time_window_indices(t, point_a, point_b)
        if i_b - i_a < 2:
            return None
        for j in range(T_act):
            if ctx is not None and ctx.cancelled:
                return None
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
                    if ctx is not None:
                        ctx.progress(int(100 * (j + 1) / T_act), f"Trial {j + 1}/{T_act}")
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
            if ctx is not None:
                ctx.progress(int(100 * (j + 1) / T_act), f"Trial {j + 1}/{T_act}")
    else:
        raise ValueError(f"Modo de modificación desconocido: {mode}.")

    # Smooth NaN segments so later analysis plugins receive finite values
    return _fill_nan_segments(t, out_active)

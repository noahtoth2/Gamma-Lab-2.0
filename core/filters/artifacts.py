"""Cálculo puro de la modificación de artefactos.

Vive en core y no en la carpeta del plugin porque lo necesitan dos capas: el
plugin `artifact_remove`, que lo manda al orquestador, y `ProjectService`, que
reaplica las modificaciones guardadas al abrir un proyecto. Es la misma
situación de `core/filters/trials.py`, que comparten plugins y servicios.

Recibe arreglos de NumPy y devuelve arreglos de NumPy: no toca el Kernel, el
DataStore ni ningún widget.
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


# --------------------------------------------------------------------------
# Persistencia: la "receta" de una modificación
# --------------------------------------------------------------------------

def receta(mode: str, point_a: float, point_b: float, discarded) -> dict:
    """Describe una modificación con lo justo para poder repetirla.

    Los descartes vigentes van incluidos porque determinan qué columnas del
    TrialDataset base se tocaron: sin ellos, reaplicar la receta sobre otro
    conjunto de descartes modificaría columnas distintas.
    """
    return {
        "mode": str(mode),
        "point_a": float(point_a),
        "point_b": float(point_b),
        "discarded_indices": sorted(int(i) for i in (discarded or ())),
    }


def columnas_activas(n_trials_total: int, discarded) -> list:
    """Columnas del TrialDataset base que estaban activas con esos descartes."""
    fuera = {int(i) for i in (discarded or ())}
    return [i for i in range(int(n_trials_total)) if i not in fuera]


def reaplicar_modificaciones(td, recetas) -> int:
    """Reaplica en orden las modificaciones guardadas sobre un TrialDataset.

    Se llama al abrir un proyecto, después de recortar los trials y de reaplicar
    los descartes. Modifica `td.trials` en el sitio y devuelve cuántas recetas
    llegaron a aplicarse. Una receta que no corresponde a estos datos se salta
    sin interrumpir las demás.
    """
    if not recetas:
        return 0

    t = np.asarray(td.time_rel)
    aplicadas = 0

    for r in recetas:
        try:
            cols = columnas_activas(td.trials.shape[1], r.get("discarded_indices"))
            if not cols:
                continue
            activos = np.array(td.trials[:, cols], copy=True)
            salida = calcular_modificacion(
                t, activos,
                mode=r.get("mode", ""),
                point_a=float(r.get("point_a", 0.0)),
                point_b=float(r.get("point_b", 0.0)),
            )
            if salida is None:
                continue
            for k, col in enumerate(cols):
                td.trials[:, col] = salida[:, k]
            aplicadas += 1
        except Exception:
            continue

    if aplicadas:
        td.metadata = getattr(td, "metadata", None) or {}
        td.metadata["modificaciones"] = list(recetas)
        marcados = set()
        for r in recetas:
            marcados.update(columnas_activas(td.trials.shape[1], r.get("discarded_indices")))
        td.metadata["modified_trials"] = marcados

    return aplicadas

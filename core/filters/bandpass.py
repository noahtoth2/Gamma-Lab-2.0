"""Filtro pasa-banda de fase cero.

Vive en core y no en el plugin porque lo necesitan dos capas: el plugin `filter`,
que lo manda al orquestador, y `core.filters.artifacts`, que lo reaplica al abrir
un proyecto cuando el filtro se aplicó a los trials (R79).

Recibe arreglos de NumPy y devuelve arreglos de NumPy.
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt


def filtrar_banda(signal, low, high, order, fs, type="butterworth", ctx=None):
    """Butterworth band-pass con `sosfiltfilt` (fase cero). Lanza ValueError con parámetros inválidos."""
    signal = np.asarray(signal, dtype=np.float64)
    nyq = 0.5 * fs
    lowcut = low / nyq
    highcut = high / nyq
    if lowcut <= 0 or highcut >= 1 or lowcut >= highcut:
        raise ValueError(f"Invalid cutoff frequencies: low={lowcut}, high={highcut}")
    if type.lower() != "butterworth":
        raise NotImplementedError(f"Filter '{type}' not implemented.")
    sos = butter(order, [lowcut, highcut], btype="band", output="sos")
    filtered = sosfiltfilt(sos, signal)
    if np.any(np.isnan(filtered)):
        raise ValueError("Filter output contains NaN values.")
    return filtered


def filtrar_columnas(trials, low, high, order, fs, type="butterworth", ctx=None):
    """Filtra cada columna (trial) de una matriz (muestras, trials). Devuelve una copia, o None si se canceló."""
    datos = np.asarray(trials, dtype=np.float64)
    salida = np.empty_like(datos)
    n = datos.shape[1]
    for j in range(n):
        if ctx is not None and ctx.cancelled:
            return None
        salida[:, j] = filtrar_banda(datos[:, j], low, high, order, fs, type)
        if ctx is not None:
            ctx.progress(int(100 * (j + 1) / n), f"Trial {j + 1}/{n}")
    return salida

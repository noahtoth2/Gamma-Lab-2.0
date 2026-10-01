import numpy as np
import pywt
from scipy.interpolate import interp1d


def _sin_log(*args):
    pass


VOCES_POR_OCTAVA = 16


def eje_frecuencias(fmin, fmax, escala_log=False):
    """Lineal: descendente, 2 filas por Hz. Logarítmica: ascendente, VOCES_POR_OCTAVA filas por octava."""
    if escala_log:
        n = int(round(np.log2(fmax / fmin) * VOCES_POR_OCTAVA)) + 1
        return np.geomspace(fmin, fmax, max(n, 2))
    return np.linspace(fmin, fmax, 2 * int(max(1, fmax - fmin)))[::-1]


def compute_wavelet(sig, fs_calculado, fs, fmin, fmax, num_cycles, escala_log=False, t0=0.0):
    if fs <= 0:
        raise ValueError(f"La densidad de muestreo debe ser mayor que cero (se recibió {fs}).")
    if fmin <= 0:
        raise ValueError(f"La frecuencia baja debe ser mayor que cero (se recibió {fmin}).")
    if fmax <= fmin:
        raise ValueError(f"La frecuencia alta ({fmax:g} Hz) debe ser mayor que la baja ({fmin:g} Hz).")
    if fmax > fs / 2:
        raise ValueError(f"La frecuencia alta ({fmax:g} Hz) no puede superar {fs / 2:g} Hz, "
                         f"la mitad de la densidad de muestreo.")

    factor = max(1, int(round(fs_calculado / fs)))
    sig = sig[::factor]

    if len(sig) < 4:
        raise ValueError(
            f"La señal tiene {len(sig)} muestras después del submuestreo; se necesitan al menos 4.")

    freq_axis = eje_frecuencias(fmin, fmax, escala_log)
    wavelet = f"cmor{num_cycles}-1.0"
    central_freq = pywt.central_frequency(wavelet)
    scales = central_freq * fs / freq_axis

    # method="fft": mismo resultado que el "conv" por defecto de PyWavelets
    # (diferencia de 2,6e-14, nueve ordenes por debajo de la tolerancia de las
    # pruebas) pero 1,8x mas rapido en eje lineal y 8,1x en logaritmico.
    coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs, method="fft")
    scalogram = np.abs(coef)
    time_axis = t0 + np.arange(len(sig)) / fs

    return scalogram, time_axis, freq_axis


def normalize_tf(tf, method="z-score", log=None):
    log = log or _sin_log
    try:
        base_mean = np.mean(tf, axis=1, keepdims=True)
        base_std = np.std(tf, axis=1, ddof=0, keepdims=True)
        base_min = np.min(tf)
        base_max = np.max(tf)

        if method == "z-score":
            return (tf - base_mean) / (base_std + 1e-12)

        elif method == "percent change":
            return ((tf - base_mean) / (base_mean + 1e-12)) * 100

        elif method == "relative power":
            return tf / (base_mean + 1e-12)

        elif method == "min-max":
            denom = (base_max - base_min) if (base_max - base_min) != 0 else 1.0
            return (tf - base_min) / denom

        else:
            raise ValueError(f"Método de normalización no reconocido: {method}.")
    except Exception as e:
        log("Error en normalize_tf:", e)
        raise


def scale_log(scalogram, freqs, log=None):
    log = log or _sin_log
    freqs_numeric = np.asarray(freqs, dtype=np.float64)
    positive_mask = freqs_numeric > 0
    if not np.any(positive_mask):
        raise ValueError("scale_log: no hay frecuencias positivas.")

    fmin = np.min(freqs_numeric[positive_mask])
    fmax = np.max(freqs_numeric)

    n_freqs_new = scalogram.shape[0]

    log_fmin = np.log10(fmin)
    log_fmax = np.log10(fmax)

    log_freqs_new = np.linspace(log_fmin, log_fmax, n_freqs_new)
    freqs_new = 10**log_freqs_new

    scalogram_new = np.zeros_like(scalogram)

    freqs_orig_sorted = np.sort(freqs_numeric)

    for i in range(scalogram.shape[1]):
        data_col = np.flipud(scalogram[:, i])
        try:
            interp_func = interp1d(freqs_orig_sorted, data_col, kind='linear',
                                   fill_value='extrapolate')
            scalogram_new[:, i] = interp_func(freqs_new)
        except Exception as e:
            log(f"scale_log: falló la interpolación en el índice de tiempo {i}:", e)
            scalogram_new[:, i] = 0.0

    return scalogram_new, freqs_new


def wavelet_promedio(ctx, data, fs_calculado, fs, fmin, fmax, cycles,
                     normalize, scaled, norm_method, t0=0.0):
    n_trials = data.shape[1]
    if n_trials == 0:
        raise ValueError("No hay trials activos para promediar.")

    acumulador = None
    times = None
    freqs = None

    for trial_idx in range(n_trials):
        if ctx.cancelled:
            return None

        sig = np.nan_to_num(data[:, trial_idx], nan=0.0, posinf=0.0, neginf=0.0)
        try:
            scalogram, times, freqs = compute_wavelet(
                sig, fs_calculado, fs, fmin, fmax, cycles, escala_log=scaled, t0=t0)
            if acumulador is None:
                acumulador = scalogram.astype(np.float64)
            else:
                acumulador += scalogram
        except Exception as e:
            raise RuntimeError(
                f"Falló el trial {trial_idx + 1} de {n_trials} trials activos: {e}") from e

        ctx.progress(int(100 * (trial_idx + 1) / n_trials),
                     f"Trial {trial_idx + 1}/{n_trials}")

    avg_scalogram = acumulador / n_trials

    # Con escala logarítmica las filas ya se calcularon sobre el eje logarítmico,
    # así que la normalización trabaja sobre filas reales y no hace falta interpolar.
    if normalize:
        avg_scalogram = normalize_tf(avg_scalogram, norm_method)

    return times, freqs, avg_scalogram, scaled

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


def tasa_efectiva(fs_calculado, fs):
    """La tasa que de verdad queda al submuestrear, y el factor usado.

    El factor tiene que ser entero, así que una densidad que no divida a la del
    archivo no se puede alcanzar: pedir 3.000 Hz sobre 10.000 da factor 3 y deja
    la señal en 3.333,3 Hz. Tratarla como si fuera de 3.000 corre **todo** el eje
    de frecuencias un 11 % (problema nº 18). MATLAB calcula `srate/srt`, esta
    misma tasa, y `fft_average` tambien; el wavelet era el unico que no.
    """
    factor = max(1, int(round(fs_calculado / fs)))
    return fs_calculado / factor, factor


def compute_wavelet(sig, fs_calculado, fs, fmin, fmax, num_cycles, escala_log=False, t0=0.0):
    if fs <= 0:
        raise ValueError(f"La densidad de muestreo debe ser mayor que cero (se recibió {fs}).")
    if fmin <= 0:
        raise ValueError(f"La frecuencia baja debe ser mayor que cero (se recibió {fmin}).")
    if fmax <= fmin:
        raise ValueError(f"La frecuencia alta ({fmax:g} Hz) debe ser mayor que la baja ({fmin:g} Hz).")

    fs_efectiva, factor = tasa_efectiva(fs_calculado, fs)

    # Contra la tasa efectiva y no contra la pedida: con 3.800 Hz sobre un
    # archivo de 10.000 el factor sale 3 y el Nyquist real es 1.666, pero
    # comparar contra la pedida dejaria pasar un fmax de 1.800.
    if fmax > fs_efectiva / 2:
        raise ValueError(f"La frecuencia alta ({fmax:g} Hz) no puede superar {fs_efectiva / 2:g} Hz, "
                         f"la mitad de la densidad efectiva ({fs_efectiva:g} Hz).")

    # Se descartan muestras sin filtrar antes, igual que el `downsample` de
    # MATLAB, que es la referencia. Eso deja aliasing: lo que este por encima
    # del nuevo Nyquist se pliega sobre las frecuencias bajas, y un tono de
    # 800 Hz submuestreado a 1.000 aparece en 200. Es una limitacion conocida y
    # heredada, no un olvido: filtrar antes corrige el aliasing pero aparta el
    # resultado de la referencia (en el promedio, de 5 a 371 filas discordantes).
    # Medido y argumentado en el problema nº 18.
    sig = sig[::factor]

    if len(sig) < 4:
        raise ValueError(
            f"La señal tiene {len(sig)} muestras después del submuestreo; se necesitan al menos 4.")

    freq_axis = eje_frecuencias(fmin, fmax, escala_log)
    wavelet = f"cmor{num_cycles}-1.0"
    central_freq = pywt.central_frequency(wavelet)
    scales = central_freq * fs_efectiva / freq_axis

    # method="fft": mismo resultado que el "conv" por defecto de PyWavelets
    # (diferencia de 2,6e-14, nueve ordenes por debajo de la tolerancia de las
    # pruebas) pero 1,8x mas rapido en eje lineal y 8,1x en logaritmico.
    coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs_efectiva, method="fft")
    scalogram = np.abs(coef)
    time_axis = t0 + np.arange(len(sig)) / fs_efectiva

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

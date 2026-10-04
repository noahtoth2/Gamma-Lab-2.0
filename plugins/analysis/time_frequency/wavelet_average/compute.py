import numpy as np

# El cálculo de wavelet vive en core/filters/wavelet.py porque lo comparten este
# plugin y el individual. Se importan los nombres sueltos, no el módulo: así
# wavelet_promedio resuelve compute_wavelet por el espacio de este módulo y la
# prueba de "un trial falla" puede sustituirlo.
from core.filters.wavelet import (  # noqa: F401
    VOCES_POR_OCTAVA,
    eje_frecuencias,
    compute_wavelet,
    normalize_tf,
    scale_log,
    tasa_efectiva,
)


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

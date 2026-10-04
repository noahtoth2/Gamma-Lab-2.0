import numpy as np

# El cálculo de wavelet vive en core/filters/wavelet.py porque lo comparten este
# plugin y el del promedio.
from core.filters.wavelet import (  # noqa: F401
    VOCES_POR_OCTAVA,
    eje_frecuencias,
    compute_wavelet,
    normalize_tf,
    scale_log,
    tasa_efectiva,
)


def wavelet_individual(ctx, sig, fs_calculado, fs, fmin, fmax, cycles,
                       normalize, scaled, norm_method, t0=0.0):
    if ctx.cancelled:
        return None

    sig = np.nan_to_num(np.asarray(sig).ravel(), nan=0.0, posinf=0.0, neginf=0.0)

    ctx.progress(0, "Calculando la transformada wavelet")
    scalogram, times, freqs = compute_wavelet(
        sig, fs_calculado, fs, fmin, fmax, cycles, escala_log=scaled, t0=t0)

    # La CWT entra de un salto en el codigo C de PyWavelets y no vuelve hasta
    # terminar, asi que la cancelacion solo puede atenderse a los extremos.
    if ctx.cancelled:
        return None

    if normalize:
        ctx.progress(90, "Normalizando")
        scalogram = normalize_tf(scalogram, norm_method)

    ctx.progress(100, "Listo")
    return times, freqs, scalogram, scaled

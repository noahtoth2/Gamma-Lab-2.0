"""Índice de modulación (comodulograma), portado de `f_PAC_sing`.

Es un algoritmo **distinto** al de PAC, aunque viva en la misma familia: barre
una rejilla de bandas con filtros IIR y no usa wavelet. Por eso es un plugin
aparte y no un modo más del combo de PAC.

Vive aquí y no en `core/filters/` porque solo lo usa este plugin. Lo que sí
comparte con PAC son los filtros, que están en `core/filters/iir.py`.
"""
from dataclasses import dataclass

import numpy as np
from scipy.signal import hilbert

from core.filters.iir import bifiltro, filtro_iir, tope_banda_alta
from core.filters.wavelet import tasa_efectiva

ANCHO_BANDA_FASE = 1.0
ANCHO_BANDA_AMPLITUD = 10.0

LIMITE_BANDAS_AMPLITUD = 178

CICLOS_MINIMOS_FASE = 6.0


@dataclass
class ResultadoMI:
    """El comodulograma y sus ejes."""
    mi_norm: np.ndarray
    mi: np.ndarray
    frecuencias_fase: np.ndarray
    frecuencias_amplitud: np.ndarray
    bandas_calculadas: int
    fs_efectiva: float
    duracion_s: float
    ciclos_banda_lenta: float
    limite_matlab: bool


def eje_barrido(inicio, fin, paso):
    """`inicio:paso:fin` de MATLAB: incluye el extremo si cae justo."""
    if paso <= 0:
        raise ValueError(f"El paso debe ser mayor que cero (se recibió {paso}).")
    n = int(np.floor((fin - inicio) / paso + 1e-9)) + 1
    return inicio + paso * np.arange(max(n, 0), dtype=np.float64)


def comodulograma(ctx, sig, fs_calculado, fs, p_ini, p_fin, pstep, a_ini, a_fin, astep,
                  limite_matlab=False):
    """El comodulograma de `f_PAC_sing`.

    Para cada frecuencia de fase extrae la fase instantánea de una banda de
    1 Hz, y para cada frecuencia de amplitud la envolvente de una banda de
    10 Hz. Después cruza todas contra todas:

        MI     = |mean(amp · e^{iφ})|              índice de Canolty
        MInorm = |Σ(amp · e^{iφ}) / Σ amp|          variante de Özkurt

    Los anchos de banda son **fijos**: `pstep` y `astep` solo mueven dónde se
    centra cada banda, no cuán ancha es. Si `astep < 10` las bandas de amplitud
    se solapan, y lo mismo con `pstep < 1` en la fase.

    Por omisión se calcula **el barrido entero**, salvo las bandas de arriba
    que no admiten filtro por quedar pegadas al Nyquist, que se quedan en `NaN`.

    `limite_matlab=True` reproduce en cambio el tope de 178 de `f_PAC_sing`. No
    lo usa la interfaz: está para las pruebas que comparan contra la referencia.
    Da igual para esa comparación —las primeras 178 filas salen idénticas bit a
    bit de las dos formas, porque cada fila depende solo de su banda de amplitud
    y de ninguna otra—, pero permite reproducir también las filas vacías.
    """
    if ctx is not None and ctx.cancelled:
        return None

    if p_ini <= 0:
        raise ValueError(f"La frecuencia inicial de fase debe ser mayor que cero (se recibió {p_ini}).")
    if p_fin < p_ini:
        raise ValueError(f"La frecuencia final de fase ({p_fin:g} Hz) no puede ser menor que la inicial ({p_ini:g} Hz).")
    if a_ini <= 0:
        raise ValueError(f"La frecuencia inicial de amplitud debe ser mayor que cero (se recibió {a_ini}).")
    if a_fin < a_ini:
        raise ValueError(f"La frecuencia final de amplitud ({a_fin:g} Hz) no puede ser menor que la inicial ({a_ini:g} Hz).")

    fs_efectiva, factor = tasa_efectiva(fs_calculado, fs)
    rango_fase = eje_barrido(p_ini, p_fin, pstep)
    rango_amplitud = eje_barrido(a_ini, a_fin, astep)
    if rango_fase.size == 0 or rango_amplitud.size == 0:
        raise ValueError("Los rangos de barrido quedaron vacíos; revisa los pasos.")

    n_amp_total = rango_amplitud.size

    limite_filtro = tope_banda_alta(fs_efectiva)
    n_filtrables = int(np.count_nonzero(
        rango_amplitud + ANCHO_BANDA_AMPLITUD < limite_filtro))

    if not limite_matlab:
        n_calculadas = n_filtrables
        if n_calculadas == 0:
            raise ValueError(
                f"Ninguna banda de amplitud cabe por debajo del Nyquist efectivo "
                f"({fs_efectiva / 2.0:g} Hz): la primera ya llegaría a "
                f"{rango_amplitud[0] + ANCHO_BANDA_AMPLITUD:g} Hz. Baja la frecuencia "
                f"inicial de amplitud o sube la frecuencia de muestreo.")
    else:
        if n_amp_total < LIMITE_BANDAS_AMPLITUD:
            raise ValueError(
                f"El barrido de amplitud da {n_amp_total} frecuencias y el cálculo necesita "
                f"al menos {LIMITE_BANDAS_AMPLITUD}. Amplía el rango o reduce el paso: "
                f"hace falta que (fin − inicio) ≥ {LIMITE_BANDAS_AMPLITUD - 1} × paso.")
        n_calculadas = min(LIMITE_BANDAS_AMPLITUD, n_amp_total)

        if n_calculadas > n_filtrables:
            tope = rango_amplitud[n_calculadas - 1] + ANCHO_BANDA_AMPLITUD
            raise ValueError(
                f"La banda de amplitud más alta que se calcula llegaría a {tope:g} Hz y el "
                f"Nyquist efectivo es {fs_efectiva / 2.0:g} Hz. Baja la frecuencia final de "
                f"amplitud, reduce el paso de amplitud o sube la frecuencia de muestreo.")

    x = np.nan_to_num(np.asarray(sig, dtype=np.float64).ravel(),
                      nan=0.0, posinf=0.0, neginf=0.0)[::factor]
    if x.size < 4:
        raise ValueError(
            f"La señal tiene {x.size} muestras después del submuestreo; se necesitan al menos 4.")

    m_fase = np.empty((x.size, rango_fase.size), dtype=np.float64)
    for i, f in enumerate(rango_fase):
        if ctx is not None and ctx.cancelled:
            return None
        sos, _ = filtro_iir(fs_efectiva, f, f + ANCHO_BANDA_FASE)
        m_fase[:, i] = np.angle(hilbert(bifiltro(sos, x)))
        if ctx is not None and i % 10 == 0:
            ctx.progress(int(35 * (i + 1) / rango_fase.size), f"Fase {i + 1}/{rango_fase.size}")

    m_amp = np.zeros((x.size, n_amp_total), dtype=np.float64)
    for i in range(n_calculadas):
        if ctx is not None and ctx.cancelled:
            return None
        f = rango_amplitud[i]
        sos, _ = filtro_iir(fs_efectiva, f, f + ANCHO_BANDA_AMPLITUD)
        m_amp[:, i] = np.abs(hilbert(bifiltro(sos, x)))
        if ctx is not None and i % 10 == 0:
            ctx.progress(35 + int(55 * (i + 1) / n_calculadas),
                         f"Amplitud {i + 1}/{n_calculadas}")

    if ctx is not None:
        ctx.progress(92, "Cruzando fase y amplitud")

    S = m_amp.T @ np.exp(1j * m_fase)
    suma_amp = m_amp.sum(axis=0)

    with np.errstate(divide="ignore", invalid="ignore"):
        mi = np.abs(S) / x.size
        mi_norm = np.abs(S / suma_amp[:, None])

    if ctx is not None:
        ctx.progress(100, "Listo")

    duracion = x.size / fs_efectiva
    return ResultadoMI(
        mi_norm=mi_norm, mi=mi,
        frecuencias_fase=rango_fase, frecuencias_amplitud=rango_amplitud,
        bandas_calculadas=n_calculadas, fs_efectiva=fs_efectiva,
        duracion_s=duracion, ciclos_banda_lenta=duracion * p_ini,
        limite_matlab=limite_matlab)

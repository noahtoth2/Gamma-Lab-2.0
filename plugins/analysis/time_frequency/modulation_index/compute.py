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

from core.filters.iir import bifiltro, filtro_iir
from core.filters.wavelet import tasa_efectiva

ANCHO_BANDA_FASE = 1.0        # f_PAC_sing filtra [f, f+1] para la fase
ANCHO_BANDA_AMPLITUD = 10.0   # y [f, f+10] para la amplitud

# El numero escrito a mano en f_PAC_sing, linea 41. El bucle correcto está
# justo encima, comentado y con un paréntesis de menos:
#
#     %for counta = 1:(size(amp_range,2)
#         for counta = 1:178
#
# Con los valores por defecto (10 : 0,5 : 500) el barrido da 981 frecuencias,
# así que solo se calculan las primeras 178 —hasta 98,5 Hz— y el resto del
# comodulograma sale en NaN: el 81,9 % de las filas. Y si el barrido diera menos
# de 178, MATLAB se cae con un error de índice.
#
# Se replica a propósito, a la espera de la decisión pendiente en
# `docs/Plan de Programación/plan-implementacion-pac.md`. Corregirlo es poner
# este valor en None.
LIMITE_BANDAS_AMPLITUD = 178

# Cuantos ciclos de la banda de fase mas lenta tienen que caber en el trial para
# que MInorm sea fiable. No sale de la teoria sino de medirlo: con un
# acoplamiento construido a 75 Hz de amplitud y 3,5 Hz de fase, un trial de 3 s
# y la fase arrancando en 1 Hz —3 ciclos— pone el maximo en cualquier parte;
# arrancando en 2 Hz —6 ciclos— lo pone exactamente donde se construyo.
#
# MATLAB no comprueba nada de esto: calcula igual y devuelve un comodulograma
# que parece correcto. El aviso es un anadido nuestro y **no cambia el
# calculo**, solo advierte, para no leer como acoplamiento lo que es ruido.
CICLOS_MINIMOS_FASE = 6.0


@dataclass
class ResultadoMI:
    """El comodulograma y sus ejes."""
    mi_norm: np.ndarray       # amplitud x fase — es el que se dibuja (Özkurt)
    mi: np.ndarray            # el mismo con el índice de Canolty, sin normalizar
    frecuencias_fase: np.ndarray       # eje X
    frecuencias_amplitud: np.ndarray   # eje Y
    bandas_calculadas: int    # cuántas bandas de amplitud se filtraron de verdad
    fs_efectiva: float
    duracion_s: float         # cuánto dura el trial ya submuestreado
    ciclos_banda_lenta: float # cuántos ciclos de `p_ini` caben en esa duración


def eje_barrido(inicio, fin, paso):
    """`inicio:paso:fin` de MATLAB: incluye el extremo si cae justo."""
    if paso <= 0:
        raise ValueError(f"El paso debe ser mayor que cero (se recibió {paso}).")
    n = int(np.floor((fin - inicio) / paso + 1e-9)) + 1
    return inicio + paso * np.arange(max(n, 0), dtype=np.float64)


def comodulograma(ctx, sig, fs_calculado, fs, p_ini, p_fin, pstep, a_ini, a_fin, astep):
    """El comodulograma de `f_PAC_sing`.

    Para cada frecuencia de fase extrae la fase instantánea de una banda de
    1 Hz, y para cada frecuencia de amplitud la envolvente de una banda de
    10 Hz. Después cruza todas contra todas:

        MI     = |mean(amp · e^{iφ})|              índice de Canolty
        MInorm = |Σ(amp · e^{iφ}) / Σ amp|          variante de Özkurt

    Los anchos de banda son **fijos**: `pstep` y `astep` solo mueven dónde se
    centra cada banda, no cuán ancha es. Si `astep < 10` las bandas de amplitud
    se solapan, y lo mismo con `pstep < 1` en la fase.
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

    # Cuántas bandas de amplitud se filtran de verdad
    n_amp_total = rango_amplitud.size
    if LIMITE_BANDAS_AMPLITUD is None:
        n_calculadas = n_amp_total
    else:
        if n_amp_total < LIMITE_BANDAS_AMPLITUD:
            raise ValueError(
                f"El barrido de amplitud da {n_amp_total} frecuencias y el cálculo necesita "
                f"al menos {LIMITE_BANDAS_AMPLITUD}. Amplía el rango o reduce el paso: "
                f"hace falta que (fin − inicio) ≥ {LIMITE_BANDAS_AMPLITUD - 1} × paso.")
        n_calculadas = min(LIMITE_BANDAS_AMPLITUD, n_amp_total)

    # El Nyquist se comprueba sobre la banda más alta que se filtra **de verdad**,
    # no sobre el final del barrido: las frecuencias que el límite de 178 deja
    # fuera nunca llegan a tener filtro, ni aquí ni en MATLAB, así que no importa
    # a qué altura queden. Con los valores por defecto —10 : 0,5 : 500 sobre
    # 1.000 Hz— el barrido termina en 500 Hz, pero la banda 178 es la de
    # 98,5-108,5 Hz y cabe de sobra. Mirar el final del barrido rechazaba por
    # Nyquist justo el caso por defecto, que en MATLAB corre sin problema.
    tope = rango_amplitud[n_calculadas - 1] + ANCHO_BANDA_AMPLITUD
    nyquist = fs_efectiva / 2.0
    if tope >= nyquist:
        raise ValueError(
            f"La banda de amplitud más alta que se calcula llegaría a {tope:g} Hz y el "
            f"Nyquist efectivo es {nyquist:g} Hz. Baja la frecuencia final de amplitud, "
            f"reduce el paso de amplitud o sube la frecuencia de muestreo.")

    x = np.nan_to_num(np.asarray(sig, dtype=np.float64).ravel(),
                      nan=0.0, posinf=0.0, neginf=0.0)[::factor]
    if x.size < 4:
        raise ValueError(
            f"La señal tiene {x.size} muestras después del submuestreo; se necesitan al menos 4.")

    # --- Fase: una banda de 1 Hz por cada frecuencia del barrido
    m_fase = np.empty((x.size, rango_fase.size), dtype=np.float64)
    for i, f in enumerate(rango_fase):
        if ctx is not None and ctx.cancelled:
            return None
        sos, _ = filtro_iir(fs_efectiva, f, f + ANCHO_BANDA_FASE)
        m_fase[:, i] = np.angle(hilbert(bifiltro(sos, x)))
        if ctx is not None and i % 10 == 0:
            ctx.progress(int(35 * (i + 1) / rango_fase.size), f"Fase {i + 1}/{rango_fase.size}")

    # --- Amplitud: una banda de 10 Hz por cada frecuencia. Las que el límite
    # deja fuera se quedan en cero, como la preasignación de MATLAB.
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

    # --- El cruce, vectorizado.
    # MATLAB lo hace con dos bucles anidados —100 x 981 vueltas con los valores
    # por defecto—, que en Python seria inviable. Es exactamente una
    # multiplicacion de matrices:
    #     S[ca, cp] = sum_n  m_amp[n, ca] * exp(i*m_fase[n, cp])
    # y de ahi MI = |S|/N y MInorm = |S| / sum(m_amp por columna).
    S = m_amp.T @ np.exp(1j * m_fase)
    suma_amp = m_amp.sum(axis=0)

    with np.errstate(divide="ignore", invalid="ignore"):
        mi = np.abs(S) / x.size
        # Donde la banda no se filtro, la suma es cero: 0/0 da NaN, igual que
        # MATLAB. No es un olvido, es el comportamiento de la referencia.
        mi_norm = np.abs(S / suma_amp[:, None])

    if ctx is not None:
        ctx.progress(100, "Listo")

    duracion = x.size / fs_efectiva
    return ResultadoMI(
        mi_norm=mi_norm, mi=mi,
        frecuencias_fase=rango_fase, frecuencias_amplitud=rango_amplitud,
        bandas_calculadas=n_calculadas, fs_efectiva=fs_efectiva,
        duracion_s=duracion, ciclos_banda_lenta=duracion * p_ini)

"""Transformada tiempo-frecuencia con wavelet de Gabor.

Réplica de `f_GaborAWTransformMatlab` de BOARD_FTD_PACC.

**Por qué vive en `core/filters/` y no dentro de un plugin.** Empezó en
`plugins/analysis/time_frequency/pac/compute.py`, y estaba bien: la usaba
solo PAC Psel. Desde que **PPC** también la necesita cruza una frontera de
plugin, y la regla de la arquitectura es que lo compartido sube a `core`. Es
el mismo camino que recorrieron los filtros IIR cuando PAC y el índice de
modulación empezaron a compartirlos.

La wavelet de **Morse** no subió: la usa un solo plugin y sigue en el
`compute.py` de PAC. Las dos están construidas igual —ventana en el dominio
de la frecuencia, multiplicada por la FFT de la señal, y vuelta con la IFFT—,
así que si algún día un segundo plugin la pide, el movimiento es este mismo.
"""
import numpy as np

CICLOS_GABOR = 1.0   # ps_StDevCycles de f_Phase_PAC_Pdetect (el .m dice 3)


def gabor_tf(sig, fs, fmin, fmax, n_freq, cycles=CICLOS_GABOR, magnitudes=True):
    """Transformada tiempo-frecuencia con wavelet de Gabor (gaussiana modulada).

    Réplica de `f_GaborAWTransformMatlab`. La usan dos análisis: **PAC Psel**,
    porque `f_Phase_PAC_Pdetect` llama a esta y no a la Morse, y **PPC**, donde
    `f_phase_coherence` la pide con `ps_Phases = 1` para quedarse solo con la
    fase de los coeficientes (`magnitudes=False` y después `np.angle`).

    La estructura es la misma que la de `morse_tf` —que se quedó en
    `plugins/analysis/time_frequency/pac/compute.py`—: ventana construida en el
    dominio de la frecuencia, multiplicada por la FFT de la señal, y vuelta con
    la IFFT, así que tampoco hace falta ninguna librería nueva. Lo que cambia
    es la ventana: aquí es una gaussiana centrada en cada frecuencia,

        W(ω) = exp(−½ · (ω − 2πf)² · σ²)      con σ = ciclos / f

    normalizada después a `sqrt(N) / ‖W‖₂`, y el coeficiente se divide por
    `sqrt(σ)`. Solo se llena media ventana, igual que en la Morse: el wavelet
    es analítico.

    Devuelve `(tf, eje_tiempo, eje_frecuencias)` con `tf` de forma
    **(frecuencia, tiempo)** y el eje de frecuencias **descendente**.

    > **Dos diferencias con `morse_tf` que no son erratas sino el original.**
    >
    > 1. Si la señal tiene largo par, las dos descartan la última muestra, pero
    >    `f_MorseAWTransformMatlab` **repone** la columna al final
    >    (`horzcat(m_MorseWT, m_MorseWT(:, end))`, línea 241) y
    >    `f_GaborAWTransformMatlab` **no**: devuelve la matriz corta. Así que
    >    con largo par la Gabor entrega una columna menos que la Morse.
    > 2. La cabecera del `.m` dice que `ps_StDevCycles` vale 3 por omisión,
    >    pero `f_Phase_PAC_Pdetect` le pasa **1**. Se usa 1.
    """
    x = np.asarray(sig, dtype=np.float64).ravel()
    if x.size < 4:
        raise ValueError(f"La señal tiene {x.size} muestras; se necesitan al menos 4.")
    if fs <= 0:
        raise ValueError(f"La frecuencia de muestreo debe ser mayor que cero (se recibió {fs}).")
    if fmin <= 0:
        raise ValueError(f"La frecuencia baja debe ser mayor que cero (se recibió {fmin}).")
    if cycles <= 0:
        raise ValueError(f"Los ciclos deben ser mayores que cero (se recibió {cycles}).")
    if fmax <= fmin:
        raise ValueError(f"La frecuencia alta ({fmax:g} Hz) debe ser mayor que la baja "
                         f"({fmin:g} Hz).")

    # MATLAB hace aqui dos ajustes **en silencio**: sube `ps_MinFreqHz` de 0 a
    # 0,1 y recorta `ps_MaxFreqHz` al Nyquist. No se replican, a proposito:
    # quien pide un analisis hasta 1.500 Hz y recibe uno hasta 1.000 sin que
    # nadie se lo diga leera el resultado como si cubriera lo que pidio. Es mas
    # util negarse y decir por que. El resto de PAC ya se comporta asi
    # —`_preparar` lanza el mismo error para la Morse—, y dejar una transformada
    # recortando y la otra avisando seria lo peor de los dos mundos.
    nyquist = fs / 2.0
    if fmax > nyquist:
        raise ValueError(
            f"La frecuencia alta ({fmax:g} Hz) pasa del Nyquist ({nyquist:g} Hz) de una "
            f"señal de {fs:g} Hz: por encima de ahí no hay información que analizar. "
            f"Baja la frecuencia final de amplitud o sube la de muestreo.")
    n_freq = int(n_freq)
    if n_freq < 2:
        raise ValueError(f"Se necesitan al menos 2 frecuencias (se pidieron {n_freq}).")

    # Eje lineal e invertido, como el MATLAB
    return gabor_en(x, fs, np.linspace(fmin, fmax, n_freq)[::-1],
                    cycles=cycles, magnitudes=magnitudes)


def gabor_en(sig, fs, frecuencias, cycles=CICLOS_GABOR, magnitudes=True):
    """La misma transformada, sobre **un eje de frecuencias dado**.

    `gabor_tf` reparte su eje linealmente entre `fmin` y `fmax`, que es lo que
    hace el MATLAB. Esto hace falta para dos cosas que aquel no permite:

    - **Un eje logarítmico.** PPC dibuja el mapa en `log10`, y poner las filas
      a distancias iguales en lineal para después estirarlas en logarítmico
      amontona casi todas arriba (es el defecto §2.5 del plan de PPC).
    - **Calcular por tandas.** Una matriz de 500 filas × 60.000 muestras son
      480 MB en complejo. Pidiendo 32 filas por vez son 30 MB, y quien llama
      va acumulando.

    `frecuencias` se usa **tal como llega**: ni se ordena ni se invierte, así
    que las filas de la salida salen en ese mismo orden. `gabor_tf` le pasa su
    eje ya descendente y por eso conserva su comportamiento exacto.
    """
    x = np.asarray(sig, dtype=np.float64).ravel()
    frecuencias = np.asarray(frecuencias, dtype=np.float64).ravel()

    if x.size < 4:
        raise ValueError(f"La señal tiene {x.size} muestras; se necesitan al menos 4.")
    if fs <= 0:
        raise ValueError(f"La frecuencia de muestreo debe ser mayor que cero (se recibió {fs}).")
    if cycles <= 0:
        raise ValueError(f"Los ciclos deben ser mayores que cero (se recibió {cycles}).")
    if frecuencias.size == 0:
        raise ValueError("No se recibió ninguna frecuencia que transformar.")
    if not np.all(frecuencias > 0):
        raise ValueError(
            f"Todas las frecuencias deben ser mayores que cero; la menor es "
            f"{frecuencias.min():g} Hz.")
    nyquist = fs / 2.0
    if frecuencias.max() > nyquist:
        raise ValueError(
            f"La frecuencia más alta ({frecuencias.max():g} Hz) pasa del Nyquist "
            f"({nyquist:g} Hz) de una señal de {fs:g} Hz: por encima de ahí no hay "
            f"información que analizar.")

    n_freq = frecuencias.size
    eje_frecuencias = frecuencias

    # Largo par: se descarta la ultima muestra y **no** se repone (ver arriba)
    if x.size % 2 == 0:
        x = x[:-1]

    n = x.size
    eje_tiempo = np.arange(n, dtype=np.float64) / fs
    mitad = n // 2 + 1

    # Eje angular: (2π/N)·(0:N−1)·fs
    w_mitad = ((2.0 * np.pi / n) * np.arange(mitad, dtype=np.float64)) * fs

    fft_sig = np.fft.fft(x)

    # Mismo criterio de memoria que morse_tf: si solo se quieren magnitudes se
    # reserva float64 y se escribe fila por fila con el abs ya aplicado.
    salida = np.empty((n_freq, n), dtype=np.float64 if magnitudes else np.complex128)
    ventana = np.zeros(n, dtype=np.float64)

    for i, f in enumerate(eje_frecuencias):
        desviacion = cycles / f          # s_StDevSec, en segundos
        ventana[:mitad] = np.exp(
            -0.5 * (w_mitad - 2.0 * np.pi * f) ** 2 * desviacion ** 2)
        # La cola sigue en cero y queda en cero al escalar, asi que se puede
        # normalizar sobre el arreglo entero sin reservar otro.
        ventana *= np.sqrt(n) / np.linalg.norm(ventana)
        coef = np.fft.ifft(fft_sig * ventana) / np.sqrt(desviacion)
        salida[i, :] = np.abs(coef) if magnitudes else coef

    return salida, eje_tiempo, eje_frecuencias

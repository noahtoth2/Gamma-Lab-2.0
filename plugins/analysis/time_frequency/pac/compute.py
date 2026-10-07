"""Cálculo de PAC, portado del MATLAB de BOARD_FTD_PACC.

Es lo que corre dentro del orquestador: recibe arreglos de NumPy y devuelve
arreglos de NumPy. No toca el Kernel, el DataStore ni ningún widget.

  - `morse_tf`         → réplica de `f_MorseAWTransformMatlab`
  - `agrupar_por_fase` → el paso 5 de `f_Phase_PAC`, el que de verdad define PAC
  - `promediar_bins`, `zscore_por_fila`, `vector_medio` → los pasos 6, 7 y 8

Vive aquí y no en `core/filters/` porque **solo lo usa este plugin**: PAC, PAC
Average y PAC Psel son tres modos del mismo plugin, no tres plugins. En `core/`
están únicamente los filtros IIR (`core/filters/iir.py`), que sí cruzan una
frontera: los comparten este plugin y el del índice de modulación.
"""
from dataclasses import dataclass

import numpy as np
from scipy.signal import hilbert

from core.filters.iir import bifiltro, filtro_butterworth, filtro_iir
from core.filters.wavelet import tasa_efectiva

GAMMA = 3.0          # ps_Gamma: el valor por defecto de la Morse generalizada
NBINS = 100          # los bins de fase de f_Phase_PAC
CICLOS = 1.0         # ps_StDevCycles de f_Phase_PAC
FILAS_POR_HZ = 4     # ps_FreqSeg = 4*(A2-A1) en f_Phase_PAC


def morse_tf(sig, fs, fmin, fmax, n_freq, cycles=1.0, magnitudes=True):
    """Transformada tiempo-frecuencia con wavelet de Morse generalizada.

    Réplica de `f_MorseAWTransformMatlab` (Lilly y Olhede, 2012). PyWavelets no
    sirve aquí: ofrece 21 wavelets continuas y ninguna Morse. Pero el MATLAB la
    calcula **en el dominio de la frecuencia**, así que son FFT, aritmética
    vectorial e IFFT; no hace falta ninguna librería nueva.

    Devuelve `(tf, eje_tiempo, eje_frecuencias)` con `tf` de forma
    **(frecuencia, tiempo)** y el eje de frecuencias en orden **descendente**.

    > La cabecera del `.m` dice «Time in rows, frequency in columns» y está
    > equivocada: el código hace `zeros(numel(v_FreqAxis), numel(v_TimeAxis))`.

    A diferencia del wavelet de los otros plugins, aquí **no puede aparecer el
    problema nº 17** (las franjas falsas de PyWavelets en frecuencias bajas):
    ese defecto viene de discretizar la wavelet con una malla fija, y la Morse
    se evalúa directamente sobre el eje de frecuencias.
    """
    x = np.asarray(sig, dtype=np.float64).ravel()
    if x.size < 4:
        raise ValueError(f"La señal tiene {x.size} muestras; se necesitan al menos 4.")
    if fs <= 0:
        raise ValueError(f"La frecuencia de muestreo debe ser mayor que cero (se recibió {fs}).")
    if fmin <= 0:
        raise ValueError(f"La frecuencia baja debe ser mayor que cero (se recibió {fmin}).")
    if fmax <= fmin:
        raise ValueError(f"La frecuencia alta ({fmax:g} Hz) debe ser mayor que la baja ({fmin:g} Hz).")
    n_freq = int(n_freq)
    if n_freq < 2:
        raise ValueError(f"Se necesitan al menos 2 frecuencias (se pidieron {n_freq}).")

    # Eje lineal e invertido, como el MATLAB
    eje_frecuencias = np.linspace(fmin, fmax, n_freq)[::-1]

    # Si la señal tiene largo par se descarta la última muestra; al final se
    # duplica la última columna para devolver el largo original.
    era_par = (x.size % 2 == 0)
    if era_par:
        x = x[:-1]

    n = x.size
    eje_tiempo = np.arange(n, dtype=np.float64) / fs
    mitad = n // 2 + 1

    # Eje angular: (2π/N)·(0:N−1)·fs
    w = (2.0 * np.pi / n) * np.arange(n, dtype=np.float64) * fs
    w_mitad = w[:mitad]

    beta = (cycles * np.pi) ** 2 / GAMMA
    pico = (beta / GAMMA) ** (1.0 / GAMMA)
    constante = (beta / GAMMA) * ((1.0 + np.log(GAMMA)) - np.log(beta))

    fft_sig = np.fft.fft(x)

    # Cuando solo se quieren magnitudes se reserva float64 y se escribe fila por
    # fila con el abs ya aplicado. Guardar la matriz compleja entera y convertir
    # al final costaria el triple: con los valores por defecto de PAC
    # —1.900 frecuencias x 8.000 muestras— son 348 MB contra 116 MB. Es el mismo
    # patron del acumulador de la Fase 1.2 del orquestador.
    salida = np.empty((n_freq, n), dtype=np.float64 if magnitudes else np.complex128)
    ventana = np.zeros(n, dtype=np.float64)

    with np.errstate(divide="ignore", invalid="ignore"):
        for i, f in enumerate(eje_frecuencias):
            escala = pico / (2.0 * np.pi * f)
            w_escalado = w_mitad * escala
            # Solo se llena media ventana: el wavelet es analitico.
            ventana[:mitad] = 2.0 * np.exp(
                constante + beta * np.log(w_escalado) - w_escalado ** GAMMA)
            ventana[~np.isfinite(ventana)] = 0.0   # w=0 da log(0) en la primera muestra
            coef = np.fft.ifft(fft_sig * ventana)
            salida[i, :] = np.abs(coef) if magnitudes else coef

    if era_par:
        salida = np.hstack([salida, salida[:, -1:]])
        eje_tiempo = np.append(eje_tiempo, eje_tiempo[-1] + 1.0 / fs)

    return salida, eje_tiempo, eje_frecuencias


def bordes_bins(nbins=NBINS):
    """Los `nbins + 1` bordes que parten el círculo de fase, de −π a π."""
    return np.linspace(-np.pi, np.pi, int(nbins) + 1)


def centros_bins(nbins=NBINS):
    """El eje que MATLAB usa para dibujar: `index(1:nbins)`, o sea los bordes
    izquierdos, no los centros. Se conserva el nombre del original."""
    return bordes_bins(nbins)[:int(nbins)]


def agrupar_por_fase(tf, fase, nbins=NBINS):
    """Reordena la energía por posición en el ciclo lento. Es el núcleo de PAC.

    Por cada bin busca **qué instantes** tenían su fase dentro —dispersos por
    toda la señal, no contiguos— y suma las columnas correspondientes de la
    matriz tiempo-frecuencia.

    Devuelve `(suma, cuenta)` **sin dividir**, para que quien llame pueda
    acumular sobre varios trials antes de promediar, que es justo lo que hace
    `f_Phase_PAC_Average`.
    """
    tf = np.asarray(tf)
    fase = np.asarray(fase, dtype=np.float64).ravel()
    if tf.ndim != 2:
        raise ValueError(f"Se esperaba una matriz (frecuencia, tiempo); llegó con {tf.ndim} dimensiones.")
    if tf.shape[1] != fase.size:
        raise ValueError(
            f"La matriz tiene {tf.shape[1]} instantes y la fase {fase.size}; deben coincidir.")

    nbins = int(nbins)
    bordes = bordes_bins(nbins)
    suma = np.zeros((tf.shape[0], nbins), dtype=np.float64)
    cuenta = np.zeros(nbins, dtype=np.float64)

    for k in range(nbins):
        # `fase >= borde_izq & fase < borde_der`, igual que el find() del MATLAB
        dentro = (fase >= bordes[k]) & (fase < bordes[k + 1])
        n = int(np.count_nonzero(dentro))
        if n:
            suma[:, k] = tf[:, dentro].sum(axis=1)
        cuenta[k] = n

    return suma, cuenta


def promediar_bins(suma, cuenta):
    """`suma / cuenta`, dejando `NaN` donde el bin quedó vacío.

    Es lo que hace MATLAB: como a un bin vacío no se le sumó nada, la división
    es `0/0` y da `NaN` —no infinito—. Se replica a propósito; la decisión está
    en `plan-implementacion-pac.md`.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.asarray(suma, dtype=np.float64) / np.asarray(cuenta, dtype=np.float64)[None, :]


def zscore_por_fila(m):
    """Z-score de cada frecuencia a lo largo de los bins de fase.

    Deja `NaN` en las filas constantes, igual que MATLAB: el numerador también
    vale cero, así que es `0/0`. Sirve para que las frecuencias con poca energía
    absoluta se vean igual que las fuertes — lo que importa no es cuánta energía
    hay, sino si varía según la fase.
    """
    m = np.asarray(m, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (m - m.mean(axis=1, keepdims=True)) / m.std(axis=1, ddof=0, keepdims=True)


def vector_medio(hist, nbins=None):
    """Vector medio circular: `mean(hist · e^{i·ángulo})`.

    Resume el acoplamiento en un número complejo: su **magnitud** dice cuánto
    acoplamiento hay y su **ángulo** en qué fase ocurre el máximo. Es lo que
    MATLAB dibuja como brújula.
    """
    hist = np.asarray(hist, dtype=np.float64).ravel()
    angulos = centros_bins(nbins if nbins is not None else hist.size)
    return complex(np.mean(hist * np.exp(1j * angulos)))


# --------------------------------------------------------------------------
# Las funciones de alto nivel: lo que el plugin manda al orquestador
# --------------------------------------------------------------------------

@dataclass
class ResultadoPac:
    """Todo lo que el plugin necesita para dibujar las cuatro salidas."""
    mapa: np.ndarray            # frecuencia x fase, con z-score por fila (lo que se dibuja)
    mapa_crudo: np.ndarray      # el mismo sin normalizar (para comparar contra MATLAB)
    frecuencias: np.ndarray     # eje de frecuencias, descendente
    fases: np.ndarray           # los 100 bordes izquierdos de los bins, en radianes
    histograma: np.ndarray      # un valor por bin: la suma sobre todas las frecuencias
    vector: complex             # magnitud y angulo del acoplamiento
    cuenta_por_bin: np.ndarray  # cuantas muestras cayeron en cada bin
    senal: np.ndarray           # la senal ya submuestreada
    banda_fase: np.ndarray      # la senal filtrada en [P1, P2]
    fase: np.ndarray            # la fase instantanea, en radianes
    banda_amplitud: np.ndarray  # la senal filtrada en [A1, A2]
    tiempo: np.ndarray          # eje de tiempo de las cuatro senales
    fs_efectiva: float
    n_trials: int = 1           # cuantos trials se promediaron


def _preparar(sig, fs_calculado, fs, p1, p2, a1, a2):
    """Validaciones y submuestreo, comunes a un trial y al promedio."""
    if p1 <= 0:
        raise ValueError(f"La frecuencia baja de fase debe ser mayor que cero (se recibió {p1}).")
    if p2 <= p1:
        raise ValueError(f"La frecuencia alta de fase ({p2:g} Hz) debe ser mayor que la baja ({p1:g} Hz).")
    if a1 <= 0:
        raise ValueError(f"La frecuencia baja de amplitud debe ser mayor que cero (se recibió {a1}).")
    if a2 <= a1:
        raise ValueError(f"La frecuencia alta de amplitud ({a2:g} Hz) debe ser mayor que la baja ({a1:g} Hz).")

    fs_efectiva, factor = tasa_efectiva(fs_calculado, fs)
    if a2 >= fs_efectiva / 2:
        raise ValueError(
            f"La frecuencia alta de amplitud ({a2:g} Hz) no puede alcanzar {fs_efectiva / 2:g} Hz, "
            f"la mitad de la densidad efectiva ({fs_efectiva:g} Hz).")

    n_freq = int(round(FILAS_POR_HZ * (a2 - a1)))
    if n_freq < 2:
        raise ValueError(
            f"El rango de amplitud [{a1:g}, {a2:g}] Hz es demasiado estrecho: daría {n_freq} filas.")
    return fs_efectiva, factor, n_freq


def pac_un_trial(ctx, sig, fs_calculado, fs, p1, p2, a1, a2):
    """PAC de un solo trial. Réplica de `f_Phase_PAC`.

    Recibe **un** trial ya elegido; quién lo elige es el plugin, según el
    selector. Los ocho pasos están numerados abajo tal como en el MATLAB.
    """
    if ctx is not None and ctx.cancelled:
        return None

    fs_efectiva, factor, n_freq = _preparar(sig, fs_calculado, fs, p1, p2, a1, a2)

    # 1) Submuestrear, sin filtro antialias: es lo que hace `downsample`
    x = np.nan_to_num(np.asarray(sig, dtype=np.float64).ravel(),
                      nan=0.0, posinf=0.0, neginf=0.0)[::factor]
    if x.size < 4:
        raise ValueError(
            f"La señal tiene {x.size} muestras después del submuestreo; se necesitan al menos 4.")

    if ctx is not None:
        ctx.progress(10, "Extrayendo la fase")

    # 2) La fase lenta
    sos_fase, _ = filtro_iir(fs_efectiva, p1, p2)
    banda_fase = bifiltro(sos_fase, x)
    # Se filtra y se saca el ángulo por separado —en vez de usar
    # `fase_instantanea`— porque la señal filtrada se necesita también para el
    # cuarto panel del dibujo, y filtrar dos veces costaría el doble.
    fase = np.angle(hilbert(banda_fase))

    if ctx is not None and ctx.cancelled:
        return None
    if ctx is not None:
        ctx.progress(25, "Transformada de Morse")

    # 3) La energía rápida
    tf, tiempo, frecuencias = morse_tf(x, fs_efectiva, a1, a2, n_freq, cycles=CICLOS)

    if ctx is not None and ctx.cancelled:
        return None
    if ctx is not None:
        ctx.progress(80, "Agrupando por fase")

    # 4 y 5) Repartir la energía en los 100 bins de fase
    suma, cuenta = agrupar_por_fase(tf, fase)

    # 6) Promediar, 7) z-score por fila y 8) el vector medio
    crudo = promediar_bins(suma, cuenta)
    histograma = np.nansum(crudo, axis=0)
    mapa = zscore_por_fila(crudo)
    vector = vector_medio(histograma)

    # El cuarto panel del dibujo: la banda de amplitud filtrada.
    # Butterworth de orden 8 y no el Chebyshev II del calculo, igual que MATLAB.
    # Con la banda por defecto [25, 500] a 2.000 Hz el orden automatico del
    # Chebyshev se dispara a 228 y el filtrado devuelve NaN en todo.
    banda_amplitud = bifiltro(filtro_butterworth(fs_efectiva, a1, a2), x)

    if ctx is not None:
        ctx.progress(100, "Listo")

    return ResultadoPac(
        mapa=mapa, mapa_crudo=crudo, frecuencias=frecuencias, fases=centros_bins(),
        histograma=histograma, vector=vector, cuenta_por_bin=cuenta,
        senal=x, banda_fase=banda_fase, fase=fase, banda_amplitud=banda_amplitud,
        tiempo=tiempo[:x.size], fs_efectiva=fs_efectiva, n_trials=1)


def pac_promedio(ctx, data, fs_calculado, fs, p1, p2, a1, a2):
    """PAC promediado sobre todos los trials. Réplica de `f_Phase_PAC_Average`.

    Es el mismo algoritmo que `pac_un_trial` salvo en un punto: **acumula la
    suma y la cuenta de los bins sobre todos los trials y divide una sola vez al
    final**, en lugar de promediar cada trial por separado. Es el mismo patrón
    de acumulador incremental de `wavelet_promedio`.

    > Se corrige de paso un desperdicio del MATLAB: su línea 52 calcula la
    > transformada del primer trial solo para conocer la forma de la matriz, y
    > el bucle la vuelve a calcular. Aquí el acumulador se reserva en la primera
    > vuelta.
    """
    if ctx is not None and ctx.cancelled:
        return None

    datos = np.asarray(data, dtype=np.float64)
    if datos.ndim == 1:
        datos = datos[:, None]
    n_trials = datos.shape[1]
    if n_trials == 0:
        raise ValueError("No hay trials activos para promediar.")

    fs_efectiva, factor, n_freq = _preparar(datos[:, 0], fs_calculado, fs, p1, p2, a1, a2)
    sos_fase, _ = filtro_iir(fs_efectiva, p1, p2)

    acumulado_suma = None
    acumulada_cuenta = None
    frecuencias = tiempo = None
    primer_x = primera_banda = primera_fase = None

    for i in range(n_trials):
        if ctx is not None and ctx.cancelled:
            return None

        x = np.nan_to_num(datos[:, i], nan=0.0, posinf=0.0, neginf=0.0)[::factor]
        if x.size < 4:
            raise ValueError(
                f"El trial {i + 1} tiene {x.size} muestras después del submuestreo; "
                f"se necesitan al menos 4.")

        banda_fase = bifiltro(sos_fase, x)
        fase = np.angle(hilbert(banda_fase))
        tf, tiempo, frecuencias = morse_tf(x, fs_efectiva, a1, a2, n_freq, cycles=CICLOS)
        suma, cuenta = agrupar_por_fase(tf, fase)

        if acumulado_suma is None:
            acumulado_suma, acumulada_cuenta = suma, cuenta
            primer_x, primera_banda, primera_fase = x, banda_fase, fase
        else:
            acumulado_suma += suma
            acumulada_cuenta += cuenta

        if ctx is not None:
            ctx.progress(int(100 * (i + 1) / n_trials), f"Trial {i + 1}/{n_trials}")

    crudo = promediar_bins(acumulado_suma, acumulada_cuenta)
    histograma = np.nansum(crudo, axis=0)

    banda_amplitud = bifiltro(filtro_butterworth(fs_efectiva, a1, a2), primer_x)

    return ResultadoPac(
        mapa=zscore_por_fila(crudo), mapa_crudo=crudo, frecuencias=frecuencias,
        fases=centros_bins(), histograma=histograma, vector=vector_medio(histograma),
        cuenta_por_bin=acumulada_cuenta, senal=primer_x, banda_fase=primera_banda,
        fase=primera_fase, banda_amplitud=banda_amplitud,
        tiempo=tiempo[:primer_x.size], fs_efectiva=fs_efectiva, n_trials=n_trials)

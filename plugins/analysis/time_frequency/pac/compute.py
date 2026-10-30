"""Cálculo de PAC, portado del MATLAB de BOARD_FTD_PACC.

Es lo que corre dentro del orquestador: recibe arreglos de NumPy y devuelve
arreglos de NumPy. No toca el Kernel, el DataStore ni ningún widget.

  - `morse_tf`         → réplica de `f_MorseAWTransformMatlab`
  - `agrupar_por_fase` → el paso 5 de `f_Phase_PAC`, el que de verdad define PAC
  - `promediar_bins`, `zscore_por_fila`, `vector_medio` → los pasos 6, 7 y 8

Lo que queda aquí es lo que **solo usa este plugin**: PAC, PAC Average y PAC
Psel son tres modos del mismo plugin, no tres plugins. Lo que cruza una
frontera está en `core/filters/`: los filtros IIR (`iir.py`), que comparten
este plugin y el del índice de modulación, y la wavelet de **Gabor**
(`gabor.py`), que comparten PAC Psel y PPC. `gabor_tf` se reexporta desde aquí
para que el resto del módulo la siga llamando por su nombre de siempre.
"""
from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks, hilbert

from core.filters.gabor import CICLOS_GABOR, gabor_tf
from core.filters.iir import bifiltro, filtro_butterworth, filtro_iir
from core.filters.wavelet import tasa_efectiva
from core.utils.parallel import map_ordenado

GAMMA = 3.0          # ps_Gamma: el valor por defecto de la Morse generalizada
NBINS = 100          # los bins de fase de f_Phase_PAC
CICLOS = 1.0         # ps_StDevCycles de f_Phase_PAC
FILAS_POR_HZ_PSEL = 2   # ps_FreqSeg = 2*(A2-A1) en f_Phase_PAC_Pdetect
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


# --------------------------------------------------------------- PAC Psel
# La deteccion de ciclos de `f_Phase_PAC_Pdetect`. No existe en PAC ni en MI:
# en vez de recorrer la señal entera, Psel busca ciclos completos del ritmo
# lento y promedia ventanas centradas en sus valles.

BANDA_GAMMA_PSEL = (25.0, 129.0)   # g_Liml y g_Limh, escritas a mano en el .m


def detectar_extremos(y):
    """Picos y valles de `y`, como los dos `findpeaks` del MATLAB.

    Devuelve `(indices_picos, indices_valles)`. Los valles salen de
    `findpeaks(-y)`, igual que en el original.

    `scipy.signal.find_peaks` y el `findpeaks` de MATLAB coinciden en lo que
    importa aquí —máximos locales estrictos, sin contar los extremos del
    arreglo—. Se diferencian en las mesetas: MATLAB no las cuenta como pico y
    SciPy devuelve el centro. Sobre una señal filtrada, que es lo único que
    entra aquí, una meseta exacta no aparece.
    """
    y = np.asarray(y, dtype=np.float64).ravel()
    picos, _ = find_peaks(y)
    valles, _ = find_peaks(-y)
    return picos, valles


def cruces_por_cero(y):
    """Índices donde `y` cambia de signo.

    Réplica literal de la función anónima del MATLAB:

        zci = @(v) find(v(:).*circshift(v(:), [-1 0]) <= 0);

    **El `circshift` da la vuelta**, así que el último elemento se compara con
    el primero y la última muestra puede salir marcada por casualidad. Se
    replica porque forma parte del resultado de la referencia.
    """
    y = np.asarray(y, dtype=np.float64).ravel()
    return np.flatnonzero(y * np.roll(y, -1) <= 0)


def seleccionar_valles(y_filt, tiempo, picos, valles, ceros, min_t, max_t,
                       permisivo=False):
    """Qué valles del ritmo lento abren un ciclo utilizable.

    Réplica de la cascada de descartes de `f_Phase_PAC_Pdetect` (líneas
    120-208). Un valle sobrevive solo si a su alrededor aparece la secuencia
    pico → cruce → valle → cruce → pico en el orden correcto, con los dos picos
    por encima de la media de los picos, el valle por debajo de la media de los
    valles, y los dos semiperiodos dentro de `[min_t, max_t]`.

    Con `permisivo` los dos umbrales de amplitud se relajan en una desviación
    típica: el pico solo tiene que superar `media − σ` y el valle solo tiene que
    bajar de `media + σ`. Entran más ciclos. Es lo que hacen las **dos**
    versiones entre canales del original —`f_Phase_PAC_Pdetect_inter` líneas
    69 y 86, `..._window` líneas 68 y 84— mientras que la de un canal usa las
    medias a secas. En los tres archivos la otra opción está escrita al lado,
    comentada, así que es un criterio que alguien eligió, no un descuido.

    Devuelve los índices (sobre la señal) de los valles elegidos.
    """
    y_filt = np.asarray(y_filt, dtype=np.float64).ravel()
    picos = np.asarray(picos, dtype=np.int64)
    valles = np.asarray(valles, dtype=np.int64)
    ceros = np.asarray(ceros, dtype=np.int64)
    if picos.size == 0 or valles.size < 4 or ceros.size == 0:
        return np.empty(0, dtype=np.int64)

    # Los umbrales de amplitud. MATLAB recorta la lista mas larga a la corta
    # antes de promediar la diferencia pico-valle; `Min_Vpp` se calcula y
    # despues no se usa —la condicion que lo usaba quedo comentada—, asi que
    # aqui no se calcula.
    alto_pico = float(y_filt[picos].mean())
    alto_valle = float(y_filt[valles].mean())
    if permisivo:
        # `std` de MATLAB divide entre N-1 y el de numpy entre N, de ahi `ddof=1`.
        # Con un solo elemento MATLAB devuelve 0 y numpy avisaria de un nan.
        altos, bajos = y_filt[picos], y_filt[valles]
        alto_pico -= float(altos.std(ddof=1)) if altos.size > 1 else 0.0
        alto_valle += float(bajos.std(ddof=1)) if bajos.size > 1 else 0.0

    valido = np.ones(valles.size, dtype=bool)
    valido[0] = False

    # Primero, los valles que caen antes del primer cruce por cero.
    i = 1
    while i < valles.size and valles[i] < ceros[0]:
        valido[i] = False
        i += 1

    while i < valles.size - 2:
        actual, anterior, siguiente = valles[i], valles[i - 1], valles[i + 1]

        antes = np.flatnonzero(ceros < actual)
        despues = np.flatnonzero(ceros > actual)
        pre_pico = np.flatnonzero(picos < actual)
        post_pico = np.flatnonzero(picos > actual)
        if antes.size == 0 or despues.size == 0 or pre_pico.size == 0 or post_pico.size == 0:
            valido[i] = False
            i += 1
            continue

        cero_pre, cero_post = ceros[antes[-1]], ceros[despues[0]]
        pico_pre, pico_post = picos[pre_pico[-1]], picos[post_pico[0]]

        descartar = (
            siguiente < cero_post            # el valle siguiente llega antes que el cruce
            or siguiente < pico_post         # o antes que el pico siguiente
            or pico_post < cero_post         # el pico siguiente llega antes que el cruce
            or anterior > cero_pre           # el valle anterior esta despues del cruce previo
            or anterior > pico_pre           # o despues del pico previo
            or pico_pre > cero_pre           # el pico previo esta despues del cruce previo
            or y_filt[actual] > alto_valle   # el valle no baja lo suficiente
            or y_filt[pico_pre] < alto_pico  # el pico previo no sube lo suficiente
            or y_filt[pico_post] < alto_pico # ni el siguiente
            or not (min_t <= tiempo[actual] - tiempo[pico_pre] <= max_t)
            or not (min_t <= tiempo[pico_post] - tiempo[actual] <= max_t))

        valido[i] = not descartar
        i += 1

    # Los dos ultimos nunca valen
    valido[-2:] = False

    # MATLAB lo hace con `v_sel .* v_plw` y luego quita los ceros. Aqui se usa
    # una mascara: multiplicar borraria tambien un valle que cayera en la
    # muestra 0, que en MATLAB no puede pasar porque sus indices empiezan en 1.
    return valles[valido]


def ventanas_por_valle(senales, valles, semiancho):
    """Recorta una ventana de `2·semiancho+1` muestras centrada en cada valle.

    `senales` es un diccionario `{nombre: arreglo}`; devuelve otro con una
    matriz `(muestras, ciclos)` por cada uno, que es la forma en que el MATLAB
    arma `m_lows_full`, `m_lows_theta` y `m_lows_gamma`.

    **Se saltan los dos primeros valles**, como el `for count=3:...` del
    original.

    > **Una desviación deliberada.** MATLAB recorta sin comprobar los bordes,
    > así que si un valle elegido queda a menos de `semiancho` muestras del
    > principio o del final, se cae con un error de índice. Con los valores por
    > defecto `semiancho` son unas 666 muestras, y que un ciclo caiga ahí es
    > perfectamente posible. Aquí esos ciclos **se omiten** y se informa de
    > cuántos: parar el análisis entero por un ciclo del borde no ayudaría a
    > nadie.
    """
    valles = np.asarray(valles, dtype=np.int64)[2:]
    if valles.size == 0:
        vacias = {n: np.empty((2 * semiancho + 1, 0)) for n in senales}
        return vacias, 0

    largos = {len(np.asarray(v).ravel()) for v in senales.values()}
    if len(largos) != 1:
        raise ValueError(f"Las señales a recortar tienen largos distintos: {sorted(largos)}.")
    largo = largos.pop()

    cabe = (valles - semiancho >= 0) & (valles + semiancho < largo)
    usables = valles[cabe]
    descartados = int(valles.size - usables.size)

    rangos = usables[None, :] + np.arange(-semiancho, semiancho + 1)[:, None]
    return ({n: np.asarray(v, dtype=np.float64).ravel()[rangos] for n, v in senales.items()},
            descartados)


def _recorte_por_valles(av):
    """Qué tramo del promedio se conserva, según sus valles.

    Réplica de las líneas 303-315. Busca los valles del promedio del ritmo lento
    y se queda con un ciclo entero a cada lado del central:

    | Valles encontrados | Tramo |
    |---|---|
    | 3 | del 1.º al 3.º |
    | más de 3 | del 2.º al 4.º |
    | 1 o 2 | el promedio entero |

    > **Con 0 valles MATLAB se cae**: `ct1` y `ct2` se quedan sin asignar y la
    > línea siguiente falla. Aquí se devuelve el tramo entero, que es lo que el
    > propio MATLAB hace con 1 y con 2.
    """
    valles, _ = find_peaks(-np.asarray(av, dtype=np.float64).ravel())
    if valles.size == 3:
        return int(valles[0]), int(valles[2])
    if valles.size > 3:
        return int(valles[1]), int(valles[3])
    return 0, len(av) - 1


@dataclass
class ResultadoPsel:
    """Todo lo que `f_Phase_PAC_Pdetect` calcula y dibuja."""
    mapa: np.ndarray            # m_phase_av_aux: (frecuencia, bin de fase), en z
    frecuencias: np.ndarray     # fr, descendente
    fases: np.ndarray           # index_pi, los bordes izquierdos de los bins
    histograma: np.ndarray      # hist_pre_1
    vector: complex             # v_pha_av_pre1
    vectores_por_grupo: np.ndarray   # angulos_av: 16 vectores, de 6 bins cada uno
    mapa_tf: np.ndarray         # tf_av_aux: el tiempo-frecuencia promedio, en z
    tiempo_tf: np.ndarray       # t_tf
    ciclos_full: np.ndarray     # m_lows_full recortado
    ciclos_theta: np.ndarray    # m_lows_theta recortado
    ciclos_gamma: np.ndarray    # m_lows_gamma (el MATLAB no lo recorta)
    promedio_theta: np.ndarray  # av, ya recortado dos veces
    promedio_full: np.ndarray   # av_full
    n_ciclos: int
    vpp: float                  # max(av) - min(av)
    vpp_full: float
    vrms: float                 # rms(av_full)
    ciclos_descartados: int     # los que no cabian enteros en la senal
    fs_efectiva: float
    senal: np.ndarray           # v_Data: los trials concatenados
    senal_filtrada: np.ndarray  # v_Data_Filt: la misma en la banda de fase
    tiempo: np.ndarray          # v_Time
    # Lo que sigue solo se llena en el modo entre canales. En el de un canal
    # `inter_canal` es False y los demas quedan en None, asi que el codigo que
    # ya existia no nota la diferencia.
    inter_canal: bool = False
    senal_amplitud: np.ndarray | None = None   # v_Data2 concatenado
    canal_fase: str | None = None
    canal_amplitud: str | None = None
    permisivo: bool = False


def pac_psel(ctx, data, fs_calculado, fs, p1, p2, a1, a2,
             data_amplitud=None, permisivo=None,
             canal_fase=None, canal_amplitud=None):
    """PAC Psel: acoplamiento promediado sobre los ciclos detectados.

    Réplica de `f_Phase_PAC_Pdetect`. A diferencia de `pac_un_trial` y de
    `pac_promedio`, esta operación **concatena todos los trials** en una señal
    continua, busca en ella ciclos completos del ritmo lento y promedia
    ventanas centradas en sus valles.

    Las otras diferencias con PAC, todas del original:

    - usa **Gabor** y no Morse (`gabor_tf`)
    - `n_freq = 2·(a2 − a1)`, no `4·`
    - la banda gamma del tercer panel está **fija en 25-129 Hz** e ignora
      `a1`/`a2`, que solo gobiernan el rango de la transformada

    > **No se replica el `A = 0`** que el MATLAB pone antes del `horzcat`
    > (línea 10): deja una muestra espuria en cero al principio de la señal
    > concatenada. Tampoco la llamada a `fvtool` de la línea 41, que abre la
    > ventana de análisis de filtros y es depuración que quedó en el código.

    ## El modo entre canales

    Con `data_amplitud` la operación pasa a ser la de `f_Phase_PAC_Pdetect_inter`:
    **los ciclos y la fase salen de `data`, la amplitud de `data_amplitud`**. Es
    decir, se buscan los ciclos del ritmo lento en el canal de fase y se mira qué
    hace la actividad rápida del *otro* canal en cada uno.

    El reparto, panel por panel:

    | Qué | De dónde | Línea del original |
    |---|---|---|
    | ciclos, fase y `ciclos_theta` | `data` | 61, 215, 228 |
    | `ciclos_full` y el mapa | `data_amplitud` | 227, 303 |
    | `ciclos_gamma` | `data_amplitud` | — |

    > **La fila de `ciclos_gamma` es una decisión nuestra, no una réplica.** La
    > `_inter` no dibuja ese panel y la `_window` lo saca del canal de *fase*
    > (línea 41, `v_Data_Filt2 = f_IIRBiFilter(v_Data1, ...)`), con ventanas
    > centradas en los valles de ese mismo canal. Eso es, exactamente, lo que ya
    > produce este `pac_psel` de un canal corrido sobre el canal de fase: el
    > panel no aportaría nada que la aplicación no dé por otro camino, y a cambio
    > dejaría fuera lo único que el modo entre canales no puede conseguir de otra
    > forma. Aquí sale del canal de amplitud, de modo que los tres paneles se
    > leen juntos: el canal de amplitud crudo, su parte rápida, y encima en negro
    > el ritmo lento del otro canal que los organiza.

    Los dos canales tienen que venir del **mismo corte**: mismo umbral, mismos
    tiempos y mismos trials, cambiando solo el canal. Si las dos matrices no
    tienen la misma forma no están alineadas muestra a muestra y se rechaza.

    `permisivo` controla los umbrales de selección de ciclos; con `None` —lo
    normal— se activa justo cuando el análisis es entre canales, que es lo que
    hace el original.
    """
    if ctx is not None and ctx.cancelled:
        return None

    m = np.asarray(data, dtype=np.float64)
    if m.ndim == 1:
        m = m[:, None]
    if m.size == 0:
        raise ValueError("No hay trials que analizar.")

    fs_efectiva, factor = tasa_efectiva(fs_calculado, fs)
    # Concatenados en una sola senal continua, trial tras trial
    senal = np.nan_to_num(m[::factor].T.ravel(), nan=0.0, posinf=0.0, neginf=0.0)
    if senal.size < 16:
        raise ValueError(
            f"La señal concatenada tiene {senal.size} muestras; se necesitan al menos 16.")

    # El segundo canal, el de amplitud. Sin el, el analisis es el de siempre y
    # `amplitud` apunta a la misma senal, asi que no hay ninguna rama distinta.
    senal_amplitud = None
    if data_amplitud is not None:
        ma = np.asarray(data_amplitud, dtype=np.float64)
        if ma.ndim == 1:
            ma = ma[:, None]
        if ma.shape != m.shape:
            raise ValueError(
                f"Los trials de los dos canales no están alineados: el de fase tiene "
                f"{m.shape[0]} muestras × {m.shape[1]} trials y el de amplitud "
                f"{ma.shape[0]} × {ma.shape[1]}. Vuelve a cortarlos con el mismo "
                f"umbral, los mismos tiempos y los mismos trials, cambiando solo "
                f"el canal.")
        senal_amplitud = np.nan_to_num(ma[::factor].T.ravel(),
                                       nan=0.0, posinf=0.0, neginf=0.0)

    inter_canal = senal_amplitud is not None
    amplitud = senal_amplitud if inter_canal else senal
    if permisivo is None:
        permisivo = inter_canal

    if ctx is not None:
        ctx.progress(5, "Filtrando")

    # Dos filtros: el del ritmo lento y el de gamma, este ultimo con la banda
    # fija. El lento sale siempre del canal de fase; gamma, del de amplitud.
    sos_fase, _ = filtro_iir(fs_efectiva, p1, p2)
    lento = bifiltro(sos_fase, senal)
    sos_gamma, _ = filtro_iir(fs_efectiva, *BANDA_GAMMA_PSEL)
    gamma = bifiltro(sos_gamma, amplitud)

    if ctx is not None and ctx.cancelled:
        return None
    if ctx is not None:
        ctx.progress(15, "Detectando ciclos")

    tiempo = np.arange(senal.size, dtype=np.float64) / fs_efectiva
    picos, valles = detectar_extremos(lento)
    ceros = cruces_por_cero(lento)
    min_t, max_t = 0.5 / p2, 0.5 / p1
    elegidos = seleccionar_valles(lento, tiempo, picos, valles, ceros, min_t, max_t,
                                  permisivo)
    if elegidos.size < 3:
        raise ValueError(
            f"Solo se encontraron {elegidos.size} ciclos utilizables en la banda "
            f"{p1:g}-{p2:g} Hz y hacen falta al menos 3. Prueba con una banda de fase "
            f"más ancha o con más trials.")

    semiancho = int(np.floor(2 * max_t * fs_efectiva))
    ventanas, descartados = ventanas_por_valle(
        {"full": amplitud, "theta": lento, "gamma": gamma}, elegidos, semiancho)
    ciclos_full = ventanas["full"]
    ciclos_theta = ventanas["theta"]
    ciclos_gamma = ventanas["gamma"]
    n_ciclos = ciclos_theta.shape[1]
    if n_ciclos == 0:
        raise ValueError(
            "Ningún ciclo cabe entero en la señal: todos quedan a menos de "
            f"{semiancho} muestras de algún borde. Hacen falta trials más largos.")

    av = ciclos_theta.mean(axis=1)
    av_full = ciclos_full.mean(axis=1)

    # Recorte a un ciclo entero a cada lado del valle central
    ct1, ct2 = _recorte_por_valles(av)
    av = av[ct1:ct2 + 1]
    av_full = av_full[ct1:ct2 + 1]
    ciclos_full = ciclos_full[ct1:ct2 + 1]
    ciclos_theta = ciclos_theta[ct1:ct2 + 1]

    # Entre los dos primeros picos del promedio recortado: el tramo que se
    # agrupa por fase. MATLAB usa `l2_av(1):l2_av(2)` sin comprobar que existan.
    picos_av, _ = find_peaks(av)
    if picos_av.size < 2:
        raise ValueError(
            "El promedio de los ciclos no tiene dos máximos, así que no se puede "
            "delimitar el tramo a agrupar por fase. Suele pasar cuando la banda de "
            "fase es demasiado estrecha o hay muy pocos ciclos.")
    i1, i2 = int(picos_av[0]), int(picos_av[1])

    n_freq = int(FILAS_POR_HZ_PSEL * (a2 - a1))

    suma = None
    cuenta = np.zeros(NBINS, dtype=np.int64)
    acumulado_tf = None
    angulos_por_ciclo = np.empty(n_ciclos, dtype=np.complex128)
    eje_frecuencias = None

    for c in range(n_ciclos):
        if ctx is not None and ctx.cancelled:
            return None
        tf, _, eje_frecuencias = gabor_tf(
            ciclos_full[:, c], fs_efectiva, a1, a2, n_freq, cycles=CICLOS_GABOR)

        # El acumulador del mapa tiempo-frecuencia. La Gabor descarta una
        # muestra cuando el largo es par, asi que las anchuras pueden no
        # coincidir; MATLAB rellena con ceros o recorta, y aqui igual.
        if acumulado_tf is None:
            acumulado_tf = np.zeros_like(tf)
        if tf.shape[1] > acumulado_tf.shape[1]:
            acumulado_tf += tf[:, :acumulado_tf.shape[1]]
        elif tf.shape[1] < acumulado_tf.shape[1]:
            acumulado_tf[:, :tf.shape[1]] += tf
        else:
            acumulado_tf += tf

        # Agrupado por fase, solo en el tramo entre los dos primeros picos
        recorte = tf[:, i1:i2 + 1]
        fase = np.angle(hilbert(ciclos_theta[i1:i2 + 1, c]))
        # Se reutiliza `agrupar_por_fase` en vez de repetir el reparto aqui.
        # Antes se hacia con `searchsorted` + `clip`, y el `clip` metia una fase
        # de exactamente pi en el ultimo bin, cuando MATLAB —y nuestro propio
        # `agrupar_por_fase`— la dejan fuera: el criterio es `>= izq & < der`,
        # asi que el borde derecho del ultimo bin no pertenece a ninguno.
        suma_ciclo, cuenta_ciclo = agrupar_por_fase(recorte, fase, NBINS)
        if suma is None:
            suma = suma_ciclo
        else:
            suma += suma_ciclo
        cuenta += cuenta_ciclo.astype(np.int64)

        # v_angles: MATLAB divide el acumulado de TODOS los ciclos entre la
        # cuenta de ESTE, asi que el valor crece con el indice del ciclo. Se
        # replica; es el dato del segundo compas y no entra en el mapa.
        with np.errstate(divide="ignore", invalid="ignore"):
            parcial = suma / cuenta_ciclo[None, :]
        hist_parcial = parcial.sum(axis=0)
        hist_parcial[~np.isfinite(hist_parcial)] = 0.0
        angulos_por_ciclo[c] = vector_medio(hist_parcial, NBINS)

        if ctx is not None and c % 5 == 0:
            ctx.progress(20 + int(60 * (c + 1) / n_ciclos), f"Ciclo {c + 1}/{n_ciclos}")

    if ctx is not None:
        ctx.progress(85, "Promediando")

    promedio = promediar_bins(suma, cuenta)
    mapa = zscore_por_fila(promedio)
    histograma = np.nanmean(promedio, axis=0)
    fases = centros_bins(NBINS)

    # Los 16 vectores del segundo compas: la media de hist*e^{i*theta} en grupos
    # de 6 bins. Cubren 96 de los 100 y los 4 ultimos se quedan fuera: el bucle
    # del MATLAB avanza de 6 en 6 mientras el indice sea menor o igual que 95.
    angulos_todos = histograma * np.exp(1j * fases)
    vectores_por_grupo = np.array(
        [angulos_todos[f:f + 6].mean() for f in range(0, 96, 6)], dtype=np.complex128)

    acumulado_tf /= n_ciclos
    acumulado_tf = acumulado_tf[:, i1:i2 + 1]
    av = av[i1:i2 + 1]
    tiempo_tf = np.arange(acumulado_tf.shape[1], dtype=np.float64) / fs_efectiva

    if ctx is not None:
        ctx.progress(100, "Listo")

    return ResultadoPsel(
        mapa=mapa, frecuencias=eje_frecuencias, fases=fases,
        histograma=histograma, vector=complex(vector_medio(histograma, NBINS)),
        vectores_por_grupo=vectores_por_grupo,
        mapa_tf=zscore_por_fila(acumulado_tf), tiempo_tf=tiempo_tf,
        ciclos_full=ciclos_full, ciclos_theta=ciclos_theta, ciclos_gamma=ciclos_gamma,
        promedio_theta=av, promedio_full=av_full, n_ciclos=n_ciclos,
        vpp=float(av.max() - av.min()), vpp_full=float(av_full.max() - av_full.min()),
        vrms=float(np.sqrt(np.mean(av_full ** 2))),
        ciclos_descartados=descartados, fs_efectiva=fs_efectiva,
        senal=senal, senal_filtrada=lento, tiempo=tiempo,
        inter_canal=inter_canal, senal_amplitud=senal_amplitud,
        canal_fase=canal_fase, canal_amplitud=canal_amplitud,
        permisivo=bool(permisivo))


def remuestrear_en_log(mapa, frecuencias, n_filas=None):
    """Lleva las filas de `mapa` a una rejilla uniforme en `log10(f)`.

    Hace falta por cómo dibuja MATLAB. `f_ImageMatrix` tiene dos ramas:

    - con 6 argumentos entra por `imagesc`, que **solo mira el primer y el
      último valor** del eje y reparte las filas a intervalos iguales;
    - con 10 activa `ps_NonEquAxis` y usa `pcolor`, que **respeta cada valor** y
      coloca cada fila donde de verdad le toca.

    `f_Phase_PAC` llama con 6 y su eje es lineal, así que repartir a intervalos
    iguales es correcto. `f_Phase_PAC_Pdetect` llama con 10 **y además convierte
    el eje a `log10`** (líneas 403-404). Las frecuencias salen uniformes de la
    Gabor, pero su logaritmo no lo es, así que dibujarlo con una imagen de
    espaciado uniforme sin remuestrear deshace el logaritmo: saldría un eje
    lineal con etiquetas de logaritmo, que es justo mentir.

    Devuelve `(matriz, log_min, log_max)` con la matriz ya **ascendente** en
    frecuencia, lista para una imagen de espaciado uniforme entre esos dos
    límites.

    > Se usa el **vecino más cercano**, no interpolación: `pcolor` pinta cada
    > celda de un color plano (`shading(gca, 'flat')`), así que interpolar
    > inventaría valores intermedios que la referencia no muestra.
    """
    m = np.asarray(mapa, dtype=np.float64)
    f = np.asarray(frecuencias, dtype=np.float64).ravel()
    if m.ndim != 2:
        raise ValueError(f"Se esperaba una matriz de dos dimensiones; llegó con {m.ndim}.")
    if f.size != m.shape[0]:
        raise ValueError(
            f"El eje tiene {f.size} frecuencias y la matriz {m.shape[0]} filas.")
    if f.size < 2:
        raise ValueError("Hacen falta al menos 2 frecuencias para remuestrear.")
    if np.any(f <= 0):
        raise ValueError("No se puede pasar a logaritmo un eje con frecuencias <= 0.")

    # El eje de la Gabor viene descendente; aqui se ordena de menor a mayor
    # porque la imagen de VTK crece hacia arriba.
    orden = np.argsort(f)
    log_f = np.log10(f[orden])
    m_ord = m[orden]

    n = int(n_filas) if n_filas else f.size
    if n < 2:
        raise ValueError(f"Se necesitan al menos 2 filas de salida (se pidieron {n}).")
    destino = np.linspace(log_f[0], log_f[-1], n)

    # Vecino mas cercano, sin construir la matriz de distancias entera
    pos = np.clip(np.searchsorted(log_f, destino), 1, log_f.size - 1)
    izquierda, derecha = pos - 1, pos
    elegida = np.where(destino - log_f[izquierda] <= log_f[derecha] - destino,
                       izquierda, derecha)
    return m_ord[elegida], float(log_f[0]), float(log_f[-1])


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
        # ddof=1 y no 0: `std(m_phase_av, [], 2)` de MATLAB normaliza por N-1,
        # que es su opcion por omision. Con los 100 bins de fase la diferencia
        # es un factor sqrt(100/99) = 1,005, un 0,5 % en todo el mapa. Pequeno,
        # pero sistematico, y saldria en cuanto se compare con la referencia.
        return (m - m.mean(axis=1, keepdims=True)) / m.std(axis=1, ddof=1, keepdims=True)


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
    # segundo panel del dibujo, y filtrar dos veces costaría el doble.
    #
    # **Segunda divergencia deliberada.** MATLAB dibuja en los paneles 2 y 3 la
    # senal del BUTTERWORTH (`v_h_Filt_P`) y saca de ella la fase instantanea,
    # no la del Chebyshev que acaba de usar para el calculo. Medido, la fase
    # difiere en 24 grados de mediana. Aqui se dibuja la del Chebyshev: es la
    # que de verdad produjo el mapa, asi que el panel y el mapa cuentan lo
    # mismo. El panel 4 si usa Butterworth, porque alli MATLAB no tiene
    # alternativa —el Chebyshev degenera en la banda ancha de amplitud—.
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
    #
    # **Aqui se diverge del MATLAB a proposito, y conviene no "arreglarlo".**
    # f_Phase_PAC filtra asi las senales que dibuja (lineas 122-124):
    #
    #     v_h_Filt_A = filter(h_FiltA, v_Data);
    #     v_h_Filt_A = filter(h_FiltA, fliplr(v_h_Filt_A));   % <- fliplr
    #     v_h_Filt_A = fliplr(v_h_Filt_A);
    #
    # `v_Data` es un vector COLUMNA y `fliplr` voltea columnas: sobre una sola
    # no hace nada. El autor queria `flipud` —es lo que usa en f_IIRBiFilter—,
    # asi que la senal acaba filtrada dos veces hacia delante y acumula el
    # retardo en vez de cancelarlo. Medido sobre 4 s a 2.000 Hz en 3-8 Hz:
    # correlacion 0,9136 y un desfase de 13 ms, que a 5 Hz son 23 grados.
    #
    # No se replica porque estropearia la lectura: el mapa SI usa el filtrado
    # bidireccional de verdad (f_IIRBiFilter, con flipud), asi que un panel
    # desfasado 23 grados contradiria al mapa que tiene justo encima.
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

    def un_trial(i):
        x = np.nan_to_num(datos[:, i], nan=0.0, posinf=0.0, neginf=0.0)[::factor]
        if x.size < 4:
            raise ValueError(
                f"El trial {i + 1} tiene {x.size} muestras después del submuestreo; "
                f"se necesitan al menos 4.")

        banda_fase = bifiltro(sos_fase, x)
        fase = np.angle(hilbert(banda_fase))
        tf, tiempo, frecuencias = morse_tf(x, fs_efectiva, a1, a2, n_freq, cycles=CICLOS)
        suma, cuenta = agrupar_por_fase(tf, fase)
        if i == 0:
            return suma, cuenta, tiempo, frecuencias, x, banda_fase, fase
        return suma, cuenta, None, None, None, None, None

    # Cada trial en vuelo reserva ~2,2 matrices tiempo-frecuencia (medido)
    bytes_por_trial = int(2.2 * n_freq * -(-datos.shape[0] // factor) * 8)
    resultados = map_ordenado(un_trial, range(n_trials), ctx=ctx, bytes_por_item=bytes_por_trial)
    if resultados is None:
        return None

    (acumulado_suma, acumulada_cuenta, tiempo, frecuencias,
     primer_x, primera_banda, primera_fase) = resultados[0]
    for suma, cuenta, *_ in resultados[1:]:
        acumulado_suma += suma
        acumulada_cuenta += cuenta

    crudo = promediar_bins(acumulado_suma, acumulada_cuenta)
    histograma = np.nansum(crudo, axis=0)

    banda_amplitud = bifiltro(filtro_butterworth(fs_efectiva, a1, a2), primer_x)

    return ResultadoPac(
        mapa=zscore_por_fila(crudo), mapa_crudo=crudo, frecuencias=frecuencias,
        fases=centros_bins(), histograma=histograma, vector=vector_medio(histograma),
        cuenta_por_bin=acumulada_cuenta, senal=primer_x, banda_fase=primera_banda,
        fase=primera_fase, banda_amplitud=banda_amplitud,
        tiempo=tiempo[:primer_x.size], fs_efectiva=fs_efectiva, n_trials=n_trials)

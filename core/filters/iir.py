"""Filtros IIR equivalentes a los del MATLAB de BOARD_FTD_PACC.

Réplica de `f_GetIIRFilter` (diseño) y `f_IIRBiFilter` (aplicación).

Viven en core porque los comparten **dos plugins distintos**: `pac` y
`modulation_index`. Es el mismo criterio que `core/filters/wavelet.py` —que
comparten los dos plugins de wavelet— y que `core/filters/trials.py`. El cálculo
propio de PAC (la transformada de Morse y el agrupado por fase) **no** está aquí
sino en la carpeta de su plugin, porque no cruza ninguna frontera.

El criterio es parecerse a la referencia, no mejorarla: donde MATLAB hace algo
discutible pero determinado, se replica y se explica por qué.
"""
from functools import lru_cache

import numpy as np
from scipy.signal import butter, cheb2ord, cheby2, hilbert, sosfilt

ORDEN_BUTTERWORTH = 8        # el que fija f_Phase_PAC para las señales que dibuja

# Los valores por defecto de f_GetIIRFilter cuando no se le pasa orden ni tipo.
RIZADO_BANDA_PASO = 0.5      # s_Rp, en dB
ATENUACION_RECHAZO = 100.0   # s_Rs, en dB
SEPARACION_HZ = 0.5          # s_Space: a que distancia quedan los bordes de rechazo


def _escala_decimal(f):
    """Cuantos decimales hay que bajar para que `f` llegue a 1.

    Replica el bucle `while s_LowFreq > 0 && s_LowFreq < 1` del MATLAB: para
    frecuencias menores que 1 Hz, la separacion de 0,5 Hz hasta el borde de
    rechazo se escala, porque si no se saldria del rango valido.
    """
    s, x = 0, float(f)
    while 0 < x < 1:
        x *= 10
        s += 1
    return s


def tope_banda_alta(fs):
    """La frecuencia alta mas grande que `filtro_iir` admite a `fs`.

    `filtro_iir` falla cuando el borde de rechazo —que queda `SEPARACION_HZ` por
    encima de la frecuencia alta— alcanza el Nyquist. Saberlo por adelantado
    permite recortar un barrido en vez de abortarlo entero: las bandas que no
    caben son siempre las ultimas, porque el barrido es creciente.

    Vale para `f2 >= 1 Hz`; por debajo, `filtro_iir` escala la separacion y el
    tope seria otro. Las bandas de amplitud siempre estan muy por encima de 1.
    """
    return fs / 2.0 - SEPARACION_HZ


# Cuantos disenos distintos se recuerdan. El indice de modulacion con los
# valores por defecto pide 278 (100 de fase + 178 de amplitud); PAC Psel, 2.
# Cada entrada son unos cientos de bytes, asi que 2.048 son un par de MB.
_MAX_FILTROS_EN_CACHE = 2048


def _disenar(fs, f1, f2):
    """El diseno de verdad. Separado para poder memorizarlo (ver `filtro_iir`)."""
    if fs <= 0:
        raise ValueError(f"La frecuencia de muestreo debe ser mayor que cero (se recibió {fs}).")
    if f1 <= 0:
        raise ValueError(f"La frecuencia baja debe ser mayor que cero (se recibió {f1}).")
    if f2 <= f1:
        raise ValueError(f"La frecuencia alta ({f2:g} Hz) debe ser mayor que la baja ({f1:g} Hz).")

    nyquist = fs / 2.0
    if f2 >= nyquist:
        raise ValueError(f"La frecuencia alta ({f2:g} Hz) no puede alcanzar el Nyquist "
                         f"({nyquist:g} Hz) de una señal de {fs:g} Hz.")

    borde_bajo = f1 - SEPARACION_HZ * 10 ** (-_escala_decimal(f1))
    borde_alto = f2 + SEPARACION_HZ * 10 ** (-_escala_decimal(f2))
    if borde_bajo <= 0 or borde_alto >= nyquist:
        raise ValueError(
            f"La banda [{f1:g}, {f2:g}] Hz queda demasiado cerca de los límites para "
            f"diseñar el filtro a {fs:g} Hz: los bordes de rechazo caerían en "
            f"[{borde_bajo:g}, {borde_alto:g}] Hz.")

    orden, wst = cheb2ord([f1 / nyquist, f2 / nyquist],
                          [borde_bajo / nyquist, borde_alto / nyquist],
                          RIZADO_BANDA_PASO, ATENUACION_RECHAZO)
    with np.errstate(over="ignore", invalid="ignore"):
        sos = cheby2(orden, ATENUACION_RECHAZO, wst, btype="band", output="sos")

    # Con bandas muy anchas el orden automatico se dispara y el diseno degenera:
    # salen coeficientes no finitos y el filtrado devuelve NaN en todas las
    # muestras, sin avisar. Medido: a 2.000 Hz, [25, 250] da orden 181 y funciona,
    # pero [25, 400] da 219 y ya esta roto. Mas vale fallar aqui con un mensaje
    # claro que entregar un resultado lleno de NaN.
    if not np.all(np.isfinite(sos)):
        raise ValueError(
            f"No se pudo diseñar un filtro Chebyshev II estable para la banda "
            f"[{f1:g}, {f2:g}] Hz a {fs:g} Hz: el orden necesario ({orden}) es demasiado "
            f"alto y el filtro degenera. Usa una banda más estrecha.")

    return sos, int(orden)


_disenar_cacheado = lru_cache(maxsize=_MAX_FILTROS_EN_CACHE)(_disenar)


def filtro_iir(fs, f1, f2):
    """Pasa-banda Chebyshev II con orden automatico, como `f_GetIIRFilter`.

    Devuelve `(sos, orden)`. Se usa formato SOS y no coeficientes b/a porque con
    `Rs = 100 dB` y los bordes de rechazo a solo 0,5 Hz los ordenes salen altos
    —26 para 3-8 Hz, 155 para 25-250 Hz— y en forma b/a eso es numericamente
    inestable. El MATLAB hace lo mismo con `zp2sos` + `dfilt.df2sos`.

    **El diseno se recuerda.** No depende de la senal, solo de `(fs, f1, f2)`,
    y calcularlo es lo caro: medido sobre las 178 bandas de amplitud del indice
    de modulacion, **el 86 % del tiempo se va en disenar los filtros y solo el
    14 % en aplicarlos** (450 ms contra 74 ms). Como el plugin tiene selector de
    trial, cada flecha rediseñaba los mismos 278 filtros desde cero. Con la
    cache, cambiar de trial pasa de 609 ms a 136 ms —**4,5 veces mas rapido**—
    y el resultado es identico.

    Se devuelve una **copia** del `sos`: la matriz guardada no sale nunca de
    aqui, asi que nadie puede modificarla sin querer y envenenar la cache para
    los siguientes. Copiar unas decenas de coeficientes cuesta microsegundos,
    nada frente a los milisegundos del diseno.

    Los parametros invalidos siguen lanzando el error de siempre **cada vez**:
    `lru_cache` no guarda excepciones.
    """
    sos, orden = _disenar_cacheado(float(fs), float(f1), float(f2))
    return sos.copy(), orden


def olvidar_filtros():
    """Vacia la cache de disenos. Para las pruebas y para liberar memoria."""
    _disenar_cacheado.cache_clear()


def estado_de_la_cache():
    """Aciertos, fallos y cuantos disenos hay guardados."""
    return _disenar_cacheado.cache_info()


def filtro_butterworth(fs, f1, f2, orden=ORDEN_BUTTERWORTH):
    """Pasa-banda Butterworth de orden fijo, como el que `f_Phase_PAC` usa para
    las señales que dibuja.

    MATLAB lo arma con `fdesign.bandpass('n,f3db1,f3db2', 8, ...)` seguido de
    `design(..., 'butter')`, y **no** reutiliza el Chebyshev II del cálculo.
    Durante el porte quedó claro por qué, y no era arbitrario: con la banda de
    amplitud por defecto —25 a 500 Hz sobre 2.000 Hz— el orden automático del
    Chebyshev II se dispara a **228**, salen coeficientes no finitos y el
    filtrado devuelve `NaN` en todas las muestras. El Butterworth de orden 8
    pasa esa misma banda sin problema.

    Regla práctica: Chebyshev II para bandas estrechas, donde hace falta un
    corte abrupto; Butterworth para bandas anchas, donde no.
    """
    if fs <= 0:
        raise ValueError(f"La frecuencia de muestreo debe ser mayor que cero (se recibió {fs}).")
    if f1 <= 0:
        raise ValueError(f"La frecuencia baja debe ser mayor que cero (se recibió {f1}).")
    if f2 <= f1:
        raise ValueError(f"La frecuencia alta ({f2:g} Hz) debe ser mayor que la baja ({f1:g} Hz).")

    nyquist = fs / 2.0
    if f2 >= nyquist:
        raise ValueError(f"La frecuencia alta ({f2:g} Hz) no puede alcanzar el Nyquist "
                         f"({nyquist:g} Hz) de una señal de {fs:g} Hz.")

    return butter(int(orden), [f1 / nyquist, f2 / nyquist], btype="band", output="sos")


def bifiltro(sos, sig):
    """Filtrado bidireccional literal, como `f_IIRBiFilter`.

    MATLAB hace: filtrar, voltear, filtrar, desvoltear. Sin relleno de bordes.

    **No se usa `sosfiltfilt`**, aunque haga lo mismo conceptualmente, porque
    rellena los bordes (`padtype='odd'`) y eso cambia el resultado. Medido sobre
    4 s a 1.000 Hz: en la banda 3-8 Hz la correlacion entre ambos metodos es de
    solo 0,9806, y la diferencia no se concentra en los bordes sino que esta
    repartida por toda la senal. Como este filtro es el que produce la fase
    instantanea, y la fase decide en cual de los 100 bins cae cada muestra,
    usar `sosfiltfilt` cambiaria el agrupado de forma visible.
    """
    x = np.asarray(sig, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError(f"Se esperaba una señal de una dimensión; llegó con {x.ndim}.")
    y = sosfilt(sos, x)
    y = sosfilt(sos, y[::-1])
    return y[::-1]


def fase_instantanea(sig, fs, f1, f2):
    """Fase instantánea de la señal dentro de la banda `[f1, f2]`, en radianes.

    Es el paso 2 de PAC: filtra en la banda lenta y convierte esa oscilación en
    un ángulo que da una vuelta completa de −π a π en cada ciclo, de modo que
    para cada muestra se sabe en qué punto del ciclo está.
    """
    sos, _ = filtro_iir(fs, f1, f2)
    return np.angle(hilbert(bifiltro(sos, sig)))


def envolvente(sig, fs, f1, f2):
    """Envolvente de amplitud dentro de la banda `[f1, f2]`.

    Lo que el índice de modulación hace con cada banda del barrido de amplitud:
    `abs(hilbert(·))` sobre la señal filtrada.
    """
    sos, _ = filtro_iir(fs, f1, f2)
    return np.abs(hilbert(bifiltro(sos, sig)))

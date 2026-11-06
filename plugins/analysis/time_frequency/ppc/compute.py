"""PPC — consistencia de fase por pares entre dos canales.

Es lo que hay detrás del botón **PPC** del panel *Inter Channel* de
`BOARD_FTD_PACC`, pero **no es una réplica**: el original tiene defectos que no
se pueden copiar sin que el análisis quede mal. El plan los enumera con sus
medidas en `docs/Plan de Programación/plan-implementacion-ppc.md`; aquí va solo
lo imprescindible para leer el código.

**Qué cambia respecto a `f_phase_coherence.m`**

1. El `.m` calcula **PLV**, `|mean(e^{iΔφ})|`, aunque el botón se llame PPC. El
   PLV está sesgado por el número de muestras: con fases al azar da 0,63 con 2
   muestras y 0,02 con 2.000. Aquí se calcula el **PPC** de Vinck et al. (2010),
   `(N·PLV² − 1)/(N − 1)`, que vale 0 en los dos casos.
2. El `.m` usa como N **todas** las muestras de la ventana. Con su σ de un ciclo
   y su ventana de 50 ms, por debajo de 50 Hz solo **una** es independiente: el
   wavelet entrega un tono puro, la diferencia de fase sale constante por
   construcción y la coherencia da 1 con los datos que sean —medido: una
   senoidal de 40 Hz contra ruido blanco puro da 0,99993—. Aquí la N son las
   muestras **independientes**, separadas 2σ.
3. El `.m` usa una sola ventana para toda la banda. Aquí **cada frecuencia tiene
   la suya**, dimensionada para reunir `n_objetivo` muestras independientes
   entre todos los trials. Una ventana fija desperdicia precisión arriba
   (N=820 a 500 Hz) y no llega abajo; la variable da 12 ms de resolución
   temporal en gamma y llega a 2 Hz.
4. Donde no se puede medir sale **NaN**, no 1. Un 1 se lee como acoplamiento
   perfecto; un hueco se lee como hueco.

**Una propiedad del PPC que conviene tener presente al leer un mapa.** Solo
mira la fase: la amplitud no entra en la cuenta. Con señales **sin nada de
ruido** eso tiene un efecto llamativo —dos canales con el mismo tono de 40 Hz
dan PPC alto también a 100 Hz, porque la fuga espectral de ese tono, aunque
valga 3·10⁻⁴ de su amplitud, lleva la misma diferencia de fase—. No es un
defecto del cálculo sino lo que significa medir solo fase. Basta un 1 % de
ruido para que esos valores caigan a cero y quede solo la banda real; cualquier
registro de verdad lo trae de sobra.

Como el resto de los `compute.py`, esto corre dentro del orquestador: recibe
arreglos de NumPy y devuelve arreglos de NumPy. No toca el Kernel, el DataStore
ni ningún widget.
"""
from dataclasses import dataclass

import numpy as np

from core.filters.gabor import gabor_en
from core.filters.wavelet import tasa_efectiva
from core.utils.parallel import MAX_HILOS, map_ordenado

CICLOS_PPC = 3.0          # ps_StDevCycles. El .m pasa 1; su propia cabecera
                          # documenta 3 como lo normal, y con 1 la gaussiana es
                          # tan ancha en frecuencia que no resuelve nada.
VENTANA_MINIMA_S = 0.05   # el `wd` del panel, ahora como piso
N_OBJETIVO = 20           # muestras independientes a reunir por celda
SOLAPE = 0.5              # entre dos columnas consecutivas de la rejilla
FILAS_POR_TANDA = 32      # cuántas frecuencias se transforman de una vez
BORDES = "recortar"       # "recortar" llena el mapa hasta los extremos;
                          # "descartar" deja el cono de influencia en blanco
HILOS = MAX_HILOS         # hilos para repartir los trials; 1 los deja en serie
# Medido el 25 de octubre sobre trials de 3 s a 2.000 Hz, el mejor de tres
# corridas, con los MISMOS datos en las dos columnas:
#
#     escenario                        1 hilo   4 hilos   gana
#     5 trials, 200 filas              1.050ms    576ms   1,82x
#     20 trials, 200 filas             4.223ms  1.832ms   2,31x
#     20 trials, eje completo (322)    4.963ms  1.981ms   2,50x
#     60 trials, 200 filas            13.432ms  5.051ms   2,66x
#
# El resultado sale **identico bit a bit**: cada trial es independiente y
# `map_ordenado` devuelve en orden, asi que la suma no depende de quien acabe
# primero. Cuesta memoria —24 MB en serie contra 89 MB con cuatro hilos—,
# porque conviven los acumulados de todos los trials.
#
# Cuatro es el punto justo: 1,93x con dos, 2,38x con tres, 2,56x con cuatro, y
# con seis u ocho ya no mejora (2,33x y 2,49x). Coincide con el MAX_HILOS que
# el proyecto ya tenia puesto.
#
# En el indice de modulacion el mismo reparto salio **mas lento** (0,65x). Aqui
# gana porque la unidad de trabajo es grande: un trial entero es una
# transformada de 6.000 muestras por 200 frecuencias, asi que el coste de
# arrancar el hilo no se nota y la FFT de NumPy suelta el GIL.


def filas_por_decada(ciclos=CICLOS_PPC):
    """Cuántas filas por década de frecuencia tienen sentido.

    El wavelet de Gabor tiene un ancho **relativo** constante: `σ_f/f` vale
    `1/(2π·ciclos)` a cualquier frecuencia. Poner las filas a media σ_f de
    distancia —lo justo para no perder nada ni repetir— da un paso constante en
    logaritmo, y de ahí sale este número.

    Con `ciclos = 3` son 87 filas por década. El MATLAB pone 500 filas lineales
    entre 0,1 y 500 Hz: a 500 Hz cada una repite casi lo mismo que sus 79
    vecinas, y abajo no hay casi ninguna.
    """
    return 4.0 * np.pi * float(ciclos) * np.log(10.0)


def eje_frecuencias(fmin, fmax, ciclos=CICLOS_PPC, n_freq=None, log=True):
    """El eje de frecuencias del mapa, **descendente** como en MATLAB.

    `log=True` lo reparte en logaritmo, que es como se dibuja. `n_freq=None`
    deja que lo decida `filas_por_decada`.
    """
    if fmin <= 0:
        raise ValueError(f"La frecuencia baja debe ser mayor que cero (se recibió {fmin}).")
    if fmax <= fmin:
        raise ValueError(
            f"La frecuencia alta ({fmax:g} Hz) debe ser mayor que la baja ({fmin:g} Hz).")

    if n_freq is None:
        if log:
            decadas = np.log10(fmax) - np.log10(fmin)
            n_freq = int(round(decadas * filas_por_decada(ciclos)))
        else:
            n_freq = int(round(fmax - fmin))     # ps_FreqSeg del .m
        n_freq = max(2, int(n_freq))             # una banda estrecha puede dar 1
    else:
        # Un numero pedido a mano NO se corrige en silencio: subirlo de 1 a 2
        # sin decirlo es la misma clase de cosa que MATLAB hace al subir fmin
        # de 0 a 0,1, y es lo que este puerto decidio no replicar.
        n_freq = int(n_freq)
        if n_freq < 2:
            raise ValueError(f"Se necesitan al menos 2 frecuencias (se pidieron {n_freq}).")

    if log:
        return np.logspace(np.log10(fmax), np.log10(fmin), n_freq)
    return np.linspace(fmin, fmax, n_freq)[::-1]


@dataclass
class ResultadoPPC:
    """El mapa de consistencia de fase entre dos canales, y sus ejes."""
    mapa: np.ndarray            # (frecuencia, tiempo), en [−1, 1]; NaN donde no se midió
    frecuencias: np.ndarray     # eje Y en Hz, descendente
    tiempos: np.ndarray         # eje X en s, rejilla común a todas las filas
    ventanas_s: np.ndarray      # la ventana que usó cada fila
    n_muestras: np.ndarray      # N nominal por fila = independientes × trials
    n_por_celda: np.ndarray     # N real de CADA celda; en los extremos baja
                                # porque la ventana se recortó contra el borde
    bordes: str                 # "recortar" (mapa lleno) o "descartar" (cono)
    fs_efectiva: float
    fs_pedida: float            # la que se escribió en el panel, que no siempre
                                # se alcanza: el factor de submuestreo es entero
    n_trials: int
    ventana_min_s: float
    solape: float
    ciclos: float
    n_objetivo: int
    filas_sin_resolver: int     # filas que salieron enteras en NaN
    canal_1: str
    canal_2: str


def validar_alineacion(td1, td2):
    """Los dos canales tienen que venir del **mismo corte**.

    El plugin *Trials* corta un canal por vez, así que el usuario genera primero
    uno y después el otro. Si no usó los mismos parámetros, los trials no están
    alineados muestra a muestra y restar sus fases no significa nada: el mapa
    saldría igual de bonito y no mediría nada.

    Se comprueba lo que de verdad puede diferir, en el orden en que importa.
    No se recorta al mínimo común en silencio: se dice qué no cuadra.
    """
    t1, t2 = np.asarray(td1.trials), np.asarray(td2.trials)
    if t1.shape != t2.shape:
        raise ValueError(
            f"Los dos canales no tienen la misma forma: '{td1.channel_name}' da "
            f"{t1.shape[0]} muestras × {t1.shape[1]} trial(s) y '{td2.channel_name}' da "
            f"{t2.shape[0]} × {t2.shape[1]}. Vuelve a generarlos con los mismos "
            f"parámetros, cambiando solo el canal.")

    o1, o2 = np.asarray(td1.onsets_s, dtype=float), np.asarray(td2.onsets_s, dtype=float)
    if o1.shape != o2.shape or not np.allclose(o1, o2):
        raise ValueError(
            f"Los trials de '{td1.channel_name}' y '{td2.channel_name}' empiezan en "
            f"instantes distintos, así que no están alineados. Genéralos con el mismo "
            f"canal de estímulo y el mismo umbral.")

    if td1.sampling_rate != td2.sampling_rate:
        raise ValueError(
            f"Los dos canales tienen frecuencias de muestreo distintas: "
            f"{td1.sampling_rate:g} Hz y {td2.sampling_rate:g} Hz.")

    if (td1.t0, td1.t1) != (td2.t0, td2.t1):
        raise ValueError(
            f"Las ventanas de recorte no coinciden: '{td1.channel_name}' va de "
            f"{td1.t0:g} a {td1.t1:g} s y '{td2.channel_name}' de {td2.t0:g} a "
            f"{td2.t1:g} s.")


def _unidad(coef):
    """El coeficiente llevado al círculo unidad: `e^{i·fase}`, sin la magnitud.

    Es `exp(1j*np.angle(c))` pero sin pasar por el arcotangente y la
    exponencial, que es la parte cara. Un coeficiente exactamente cero no tiene
    fase, así que aporta cero; MATLAB le asigna `angle(0) = 0` y lo cuenta como
    una fase de 0 rad, que es inventarse un dato.
    """
    magnitud = np.abs(coef)
    return np.divide(coef, magnitud, out=np.zeros_like(coef), where=magnitud > 0)


def _trials_planos(x, canal):
    """Los trials sin ninguna variación, que no tienen fase que medir.

    **Por qué hace falta comprobarlo.** El PPC normaliza cada coeficiente a
    módulo 1, así que la amplitud desaparece: da igual que el coeficiente valga
    4 o 10⁻²⁵. Con un canal constante —un electrodo muerto, una saturación, un
    tramo plano— los coeficientes son polvo numérico de 10⁻²⁵, pero no son cero
    exacto, y al normalizarlos sale una «fase» perfectamente repetible. Medido:
    **dos canales constantes dan PPC = 1,0000 en todo el mapa**. Un falso
    positivo perfecto, y encima el peor de todos, porque es el que alguien
    enseñaría como hallazgo.

    Se comprueba a la entrada, sobre la señal, donde el criterio es claro:
    desviación cero es desviación cero. Un tramo plano **dentro** de un trial
    por lo demás vivo no lo coge esto, y poner un umbral para eso sería
    inventarse una constante; queda anotado como límite conocido.
    """
    desviaciones = np.std(x, axis=0)
    planos = np.flatnonzero(desviaciones == 0.0)
    if planos.size == 0:
        return
    cuales = ", ".join(str(int(i) + 1) for i in planos[:5])
    if planos.size > 5:
        cuales += f" y {planos.size - 5} más"
    raise ValueError(
        f"El canal '{canal}' tiene {planos.size} trial(s) sin ninguna variación "
        f"(el {cuales}). Una señal constante no tiene fase, y el PPC normaliza la "
        f"amplitud: sobre polvo numérico devolvería un acoplamiento perfecto que no "
        f"existe. Revisa ese canal o descarta esos trials.")


def _geometria(frecuencias, fs, n_muestras_trial, n_trials, wd, ciclos,
               solape, n_objetivo, bordes="recortar"):
    """Qué ventana le toca a cada fila, y dónde caen las columnas.

    `n_ind` es cuántas muestras independientes hay que pedirle a **cada** trial
    para reunir `n_objetivo` entre todos. De ahí sale la ventana: dos muestras
    separadas 2σ ya son casi independientes, así que `n_ind` de ellas ocupan
    `2·ciclos·n_ind/f` segundos. El piso es `wd` y el techo, el trial entero.
    """
    dur = n_muestras_trial / fs
    n_ind_pedidas = int(np.ceil(n_objetivo / max(1, n_trials)))

    ancho = 2.0 * ciclos * n_ind_pedidas / frecuencias
    ancho = np.clip(ancho, wd, dur)

    # Hacia ARRIBA, no al más cercano. Media muestra de redondeo a la baja
    # bastaba para que el `floor` de abajo contara una muestra independiente
    # menos y la fila reportara la mitad de N de la que de verdad tiene.
    largos = np.maximum(1, np.ceil(ancho * fs - 1e-9).astype(int))
    largos += 1 - largos % 2         # impar: así la ventana tiene centro exacto
    largos = np.minimum(largos, n_muestras_trial - (1 - n_muestras_trial % 2))
    ventanas_s = largos / fs

    # Las independientes que de verdad caben en la ventana que quedó, que no es
    # la pedida cuando el piso o el techo recortaron.
    n_ind = np.maximum(1, np.floor(
        ventanas_s * frecuencias / (2.0 * ciclos) + 1e-9)).astype(int)

    paso = max(1, int(round(wd * (1.0 - solape) * fs)))
    # La rejilla se ancla al centro del trial, no al principio. Si no, la fila
    # cuya ventana ocupa el trial entero —solo cabe centrada— se quedaba en NaN
    # por la tontería de que su único centro posible no caía en la rejilla.
    centro = (n_muestras_trial - 1) // 2
    centros = np.arange(centro % paso, n_muestras_trial, paso)

    # --- Donde empieza y acaba la ventana de cada celda.
    # `bordes="descartar"`: solo valen las celdas cuya ventana cabe ENTERA.
    # Es el cono de influencia clásico y deja los extremos en blanco.
    # `bordes="recortar"`: la ventana se corta contra el final del trial y la
    # celda se calcula con las muestras que haya. Da un valor **más ruidoso,
    # no falso**: el enrollado de la FFT revuelve la fase hasta 60° pegado al
    # borde, pero revuelve los dos canales por separado, así que su diferencia
    # sigue siendo aleatoria. Medido con ruido independiente, las celdas del
    # borde dan entre −0,05 y +0,13, o sea ruido, no acoplamiento inventado.
    # Lo que sí baja es la N, y por eso se cuenta **por celda**.
    semi = largos // 2
    if bordes == "descartar":
        lo = centros[None, :] - semi[:, None]
        hi = centros[None, :] + semi[:, None]
        cabe = (lo >= 0) & (hi <= n_muestras_trial - 1)
        lo = np.clip(lo, 0, n_muestras_trial - 1)
        hi = np.clip(hi, 0, n_muestras_trial - 1)
    else:
        lo = np.clip(centros[None, :] - semi[:, None], 0, n_muestras_trial - 1)
        hi = np.clip(centros[None, :] + semi[:, None], 0, n_muestras_trial - 1)
        cabe = hi > lo

    # Las columnas que no le sirven a NADIE se recortan en vez de devolverlas
    # enteras en NaN: una columna vacía en el borde es exactamente lo que se le
    # critica al MATLAB, y da igual que aquí sea NaN y allí un cero.
    con_dato = cabe.any(axis=0)
    centros, cabe = centros[con_dato], cabe[:, con_dato]
    lo, hi = lo[:, con_dato], hi[:, con_dato]

    # Muestras que de verdad se promedian en cada celda, y las independientes
    # que salen de ellas. Con `descartar` son todas iguales dentro de una fila;
    # con `recortar`, las de los extremos tienen menos.
    cuenta = (hi - lo + 1).astype(np.float64)
    # La N de una celda recortada baja en la misma proporcion que su ventana.
    # Se deja FRACCIONARIA a proposito: la formula del PPC admite cualquier
    # N > 1, y redondear hacia arriba —o peor, poner un minimo de 1 como hacia
    # una version anterior de esto— es exactamente el error que se le critica a
    # MATLAB: declarar mas muestras independientes de las que hay. Una celda
    # con media ventana tiene media N, y asi queda escrito.
    n_ind_celda = n_ind[:, None] * (cuenta / largos[:, None])

    return largos, lo, hi, ventanas_s, n_ind, n_ind_celda, cuenta, centros, cabe


def ppc_mapa(ctx, trials_1, trials_2, fs_calculado, fs, fmin, fmax,
             wd=VENTANA_MINIMA_S, ciclos=CICLOS_PPC, n_freq=None,
             solape=SOLAPE, n_objetivo=N_OBJETIVO, eje_log=True, t0=0.0,
             canal_1="canal 1", canal_2="canal 2", hilos=None,
             bordes=BORDES):
    """El mapa de PPC entre dos canales, frecuencia contra tiempo.

    `trials_1` y `trials_2` son matrices `(muestras, trials)` **ya alineadas**
    —`validar_alineacion` lo comprueba antes—. `wd` es la ventana **mínima**:
    pone el tope a la resolución temporal y el paso de la rejilla.

    Devuelve `None` si `ctx` canceló.
    """
    if ctx is not None and ctx.cancelled:
        return None

    hilos = HILOS if hilos is None else max(1, int(hilos))

    x1 = np.asarray(trials_1, dtype=np.float64)
    x2 = np.asarray(trials_2, dtype=np.float64)
    if x1.ndim == 1:
        x1 = x1[:, None]
    if x2.ndim == 1:
        x2 = x2[:, None]
    if x1.shape != x2.shape:
        raise ValueError(
            f"Los dos canales tienen que traer la misma matriz: llegaron "
            f"{x1.shape} y {x2.shape}.")
    if x1.ndim != 2:
        raise ValueError(f"Se esperaba una matriz (muestras, trials); llegó con {x1.ndim}.")

    if wd <= 0:
        raise ValueError(f"La ventana mínima debe ser mayor que cero (se recibió {wd}).")
    if not 0.0 <= solape < 0.95:
        raise ValueError(f"El solapamiento tiene que estar entre 0 y 0,95 (se recibió {solape}).")
    if ciclos <= 0:
        raise ValueError(f"Los ciclos deben ser mayores que cero (se recibió {ciclos}).")
    if n_objetivo < 2:
        raise ValueError(
            f"El objetivo de muestras independientes debe ser al menos 2 "
            f"(se recibió {n_objetivo}): con una sola no hay ningún par que comparar.")

    fs_efectiva, factor = tasa_efectiva(fs_calculado, fs)
    x1 = np.nan_to_num(x1[::factor, :], nan=0.0, posinf=0.0, neginf=0.0)
    x2 = np.nan_to_num(x2[::factor, :], nan=0.0, posinf=0.0, neginf=0.0)

    # `gabor_en` descarta la ultima muestra si el largo es par, igual que el
    # MATLAB. La geometria se calcula sobre lo que de verdad va a salir.
    n = x1.shape[0]
    if n % 2 == 0:
        n -= 1
    n_trials = x1.shape[1]
    if n < 4:
        raise ValueError(
            f"Cada trial queda en {n} muestras después del submuestreo; "
            f"se necesitan al menos 4.")

    nyquist = fs_efectiva / 2.0
    if fmax > nyquist:
        # `:.10g` y no `:g`: con fmax = 250,0001 y Nyquist 250 los seis digitos
        # de `:g` imprimian «250 Hz pasa del Nyquist (250 Hz)», que no se
        # entiende.
        raise ValueError(
            f"La frecuencia alta ({fmax:.10g} Hz) pasa del Nyquist ({nyquist:.10g} Hz) "
            f"que deja el remuestreo a {fs_efectiva:.10g} Hz. Baja la frecuencia final "
            f"o sube la de muestreo.")

    _trials_planos(x1, canal_1)
    _trials_planos(x2, canal_2)

    if bordes not in ("recortar", "descartar"):
        raise ValueError(
            f"`bordes` solo admite 'recortar' o 'descartar' (se recibió {bordes!r}).")

    frecs = eje_frecuencias(fmin, fmax, ciclos, n_freq, log=eje_log)
    (largos, lo_v, hi_v, ventanas_s, n_ind, n_ind_celda, cuenta,
     centros, cabe) = _geometria(frecs, fs_efectiva, n, n_trials, wd, ciclos,
                                 solape, n_objetivo, bordes)

    # Una celda se puede medir si su ventana cabe **y** reúne al menos dos
    # muestras independientes: con una sola no hay ningún par que comparar, y
    # el PPC es precisamente la media sobre los pares.
    N_fila = n_ind * n_trials
    N_celda = n_ind_celda * n_trials
    if not (cabe.any() and np.any(N_celda[cabe] >= 2)):
        pedida = 2.0 * ciclos * int(np.ceil(n_objetivo / n_trials)) / frecs.max()
        raise ValueError(
            f"Ninguna frecuencia de la banda se puede medir con estos trials. "
            f"La más alta ({frecs.max():g} Hz) necesitaría una ventana de "
            f"{pedida:.3f} s y cada trial dura {n / fs_efectiva:.3f} s, así que ni "
            f"con la ventana entera se reúnen dos muestras independientes. Sube la "
            f"frecuencia inicial, alarga los trials, o genera más trials para "
            f"repartir el trabajo entre ellos.")

    # --- El acumulado sobre los trials. Solo hace falta la suma compleja: el
    # PPC se saca del modulo, no de cada termino por separado.
    def aporte_de(tr):
        """Lo que suma un trial al acumulado. No toca nada de fuera.

        Es una función aparte y no el cuerpo de un bucle para que el reparto
        entre hilos sea un cambio de una línea: cada trial es independiente de
        los demás y solo lee `x1`, `x2` y la geometría, que no se modifican.
        """
        propio = np.zeros((frecs.size, centros.size), dtype=np.complex128)
        for ini in range(0, frecs.size, FILAS_POR_TANDA):
            if ctx is not None and ctx.cancelled:
                return propio
            fin = min(ini + FILAS_POR_TANDA, frecs.size)
            tanda = frecs[ini:fin]

            c1, _, _ = gabor_en(x1[:, tr], fs_efectiva, tanda,
                                cycles=ciclos, magnitudes=False)
            c2, _, _ = gabor_en(x2[:, tr], fs_efectiva, tanda,
                                cycles=ciclos, magnitudes=False)
            # z = e^{i(φ1−φ2)}, sin pasar por angle() ni exp()
            z = _unidad(c1) * np.conj(_unidad(c2))

            # Suma movil por filas: con la suma acumulada, cada ventana cuesta
            # dos restas en vez de recorrerla entera.
            acumulada = np.concatenate(
                [np.zeros((z.shape[0], 1), dtype=np.complex128),
                 np.cumsum(z, axis=1)], axis=1)
            for j in range(z.shape[0]):
                i = ini + j
                validos = cabe[i]
                if not validos.any():
                    continue
                propio[i, validos] += (acumulada[j, hi_v[i, validos] + 1]
                                       - acumulada[j, lo_v[i, validos]])
        return propio

    acum = np.zeros((frecs.size, centros.size), dtype=np.complex128)

    if hilos == 1:
        for tr in range(n_trials):
            if ctx is not None and ctx.cancelled:
                return None
            acum += aporte_de(tr)
            if ctx is not None:
                ctx.progress(int(100 * (tr + 1) / n_trials),
                             f"Trial {tr + 1}/{n_trials}")
    else:
        # El reparto va **por trials**, con el mismo `map_ordenado` que usa
        # `pac_promedio`. Él pone el avance y la cancelación, y acota los hilos
        # por memoria: cada uno tiene en vuelo su acumulado y las dos tandas de
        # la transformada.
        por_hilo = (frecs.size * centros.size
                    + 2 * FILAS_POR_TANDA * n) * 16
        aportes = map_ordenado(aporte_de, range(n_trials), ctx=ctx,
                               max_hilos=hilos, etiqueta="Trial",
                               bytes_por_item=por_hilo)
        if aportes is None:
            return None
        for a in aportes:
            acum += a
        del aportes

    # --- De la suma al PPC.
    # Los dos divisores son distintos a proposito: el PLV es la media de TODAS
    # las muestras promediadas, y la correccion del sesgo usa solo las
    # independientes. Confundirlos es justo el error de MATLAB.
    #
    # SOBRE LA EXACTITUD DE ESA N, que es lo unico aproximado del calculo.
    # `n_ind` sale de suponer que dos puntos separados 2*sigma ya son
    # independientes. Medido —400 ventanas de ruido, mirando E[PLV^2] = 1/N—,
    # la N efectiva de verdad es 2,3 donde nosotros contamos 2: nos quedamos
    # cortos un 15-20 %. Contar de menos hace que la correccion se pase, asi
    # que el mapa queda sesgado **hacia abajo**: con ruido independiente la
    # media sale -0,009 en vez de 0 (40 corridas, N=20).
    #
    # No se corrige, por dos razones. Es 10 veces mas chico que el umbral de
    # ruido al 95 % para esa misma N (0,103), asi que no cambia ninguna
    # lectura. Y el error va en la direccion segura: esta medida nunca inventa
    # acoplamiento, que es el defecto que vinimos a arreglar. Calibrar el 2 a
    # 1,74 seria ajustar una constante a una sola medida y heredar su
    # dependencia de `ciclos`. Hay una prueba que fija el signo y el tamano del
    # sesgo, para que un cambio futuro que lo vuelva positivo salte.
    with np.errstate(invalid="ignore", divide="ignore"):
        plv = np.abs(acum) / (cuenta * n_trials)
        N = N_celda.astype(np.float64)
        mapa = (N * plv ** 2 - 1.0) / (N - 1.0)

    mapa[~cabe] = np.nan
    mapa[N < 2] = np.nan

    sin_resolver = int(np.sum(np.all(np.isnan(mapa), axis=1)))

    if ctx is not None:
        ctx.progress(100, "Listo")

    return ResultadoPPC(
        mapa=mapa, frecuencias=frecs, tiempos=t0 + centros / fs_efectiva,
        ventanas_s=ventanas_s, n_muestras=n_ind * n_trials,
        n_por_celda=(N_celda * np.where(cabe, 1, np.nan)),
        bordes=str(bordes),
        fs_efectiva=fs_efectiva, fs_pedida=float(fs), n_trials=n_trials,
        ventana_min_s=float(wd), solape=float(solape), ciclos=float(ciclos),
        n_objetivo=int(n_objetivo), filas_sin_resolver=sin_resolver,
        canal_1=canal_1, canal_2=canal_2)


def avisos(r):
    """Lo que condiciona la lectura del mapa, en frases listas para mostrar.

    Devuelve una lista de textos en español, vacía si no hay nada que decir.
    Es una **función del resultado**, no un método del plugin, por dos motivos:
    la interfaz la escribe otra persona y no tiene por qué volver a deducir
    estas condiciones, y así se puede probar sin levantar Qt.

    **Ninguno de estos avisos abre un diálogo.** El plugin los registra en el
    log y, si quiere, los pone bajo el gráfico. Un modal abre un bucle de
    eventos anidado y el temporizador de `QVTKRenderWindowInteractor` sigue
    disparando dentro de él: es el nº 24 de `problemas-encontrados.md`. Un
    fallo de verdad sí abre diálogo, pero ese camino es el de `failed`.

    Lo que **no** sale por aquí son los errores: los casos en que el cálculo no
    se puede hacer los lanza `ppc_mapa` como `ValueError` antes de empezar.
    """
    fuera = []
    sin_medir = np.all(np.isnan(r.mapa), axis=1)

    # --- Dos canales iguales
    if r.canal_1 == r.canal_2:
        fuera.append(
            f"Los dos canales son el mismo ('{r.canal_1}'). El PPC de una señal "
            f"consigo misma vale 1 en todo el mapa por definición: no está midiendo "
            f"nada. Elige dos canales distintos.")

    # --- El remuestreo pedido no se alcanzo (el problema nº 18)
    if abs(r.fs_efectiva - r.fs_pedida) > 1e-9:
        fuera.append(
            f"Se pidió remuestrear a {r.fs_pedida:g} Hz, pero el factor tiene que ser "
            f"entero y la señal quedó en {r.fs_efectiva:.1f} Hz. El eje de frecuencias "
            f"es el de {r.fs_efectiva:.1f} Hz, no el de {r.fs_pedida:g}.")

    # --- Filas que no se pudieron medir en absoluto
    if sin_medir.any():
        f_sin = r.frecuencias[sin_medir]
        falta = 2.0 * r.ciclos * 2 / f_sin.max()
        fuera.append(
            f"{int(sin_medir.sum())} de las {r.frecuencias.size} frecuencias no se "
            f"pudieron medir, las de {f_sin.min():.1f} a {f_sin.max():.1f} Hz: ni "
            f"ocupando el trial entero reúnen dos muestras independientes, y el PPC es "
            f"una media sobre pares. La más alta de ellas necesitaría trials de "
            f"{falta:.2f} s. Salen en blanco a propósito; MATLAB las devolvía "
            f"valiendo 1.")

    # --- Filas medidas, pero con menos respaldo del pedido
    flojas = (~sin_medir) & (r.n_muestras < r.n_objetivo)
    if flojas.any():
        f_flojas = r.frecuencias[flojas]
        peor = int(r.n_muestras[flojas].min())
        cuantos = (f"el único trial que hay" if r.n_trials == 1
                   else f"los {r.n_trials} que hay")
        texto = (
            f"{int(flojas.sum())} frecuencias se midieron con menos de "
            f"{r.n_objetivo} muestras independientes —las de {f_flojas.min():.1f} a "
            f"{f_flojas.max():.1f} Hz, con un mínimo de {peor}—. Ahí el valor es más "
            f"ruidoso y un número alto puede ser azar. Sube con más trials: el reparto "
            f"es {r.n_objetivo} entre {cuantos}.")
        if peor < 5:
            # Medido: con fases al azar, el PPC tiene desviacion 0,71 con N=2 y
            # 0,22 con N=5. Por debajo de 5 el valor no se puede leer.
            texto += (f" Con {peor} muestras el valor ni se puede leer: con fases al "
                      f"azar la desviación del PPC es de 0,7 para 2 muestras y 0,2 "
                      f"para 5, así que cualquier número es posible.")
        fuera.append(texto)

    # --- Los extremos: o salen en blanco, o salen con menos respaldo
    medibles = r.mapa[~sin_medir]
    if medibles.size and r.bordes == "descartar":
        blanco = float(np.mean(np.isnan(medibles)))
        if blanco > 0.05:
            fuera.append(
                f"El {blanco * 100:.0f} % del mapa queda en blanco en los extremos "
                f"izquierdo y derecho. Es el cono de influencia: la ventana de las "
                f"frecuencias bajas —hasta {r.ventanas_s.max():.2f} s— no cabe pegada "
                f"al borde del trial. No es un dato que falte, es que ahí no se puede "
                f"calcular.")
    elif medibles.size and r.bordes == "recortar":
        # El mapa sale lleno, y por eso hay que decir lo que esconde: en los
        # extremos la ventana se cortó contra el borde del trial y la celda se
        # calculó con menos muestras. No decirlo seria enseñar un borde con la
        # misma pinta de solido que el centro, que es la mentira que este
        # puerto le corrige a MATLAB.
        nominal = r.n_muestras[:, None].astype(np.float64)
        flojo = np.isfinite(r.n_por_celda) & (r.n_por_celda < 0.75 * nominal)
        if flojo.any():
            proporcion = float(np.mean(flojo[np.isfinite(r.n_por_celda)]))
            peor = float(np.nanmin(r.n_por_celda / nominal)) * 100
            fuera.append(
                f"El mapa llega hasta los extremos porque la ventana se recorta "
                f"contra el borde del trial, pero el {proporcion * 100:.0f} % de las "
                f"celdas se calculó con menos muestras de las previstas —la peor, con "
                f"el {peor:.0f} %—. Ahí el valor es correcto pero más ruidoso; "
                f"`n_por_celda` dice cuánto respalda a cada una. Con "
                f"`bordes='descartar'` esa zona sale en blanco en vez de recortada.")

    return fuera

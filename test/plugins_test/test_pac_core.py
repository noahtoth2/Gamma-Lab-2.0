"""Fase 1 de PAC: los filtros IIR y la transformada de Morse.

Portados del MATLAB de BOARD_FTD_PACC. El criterio es parecerse a la referencia,
así que varias pruebas fijan comportamientos que en abstracto serían discutibles
—como dejar que aparezca `NaN`— porque es lo que hace MATLAB y se decidió
replicarlo (ver `docs/Plan de Programación/plan-implementacion-pac.md`).

Las frecuencias se comprueban con tonos puros: si la transformada pone el máximo
en otra parte, el error es medible y no una opinión.
"""
import numpy as np
import pytest
from scipy.signal import find_peaks

from core.filters.iir import (bifiltro, envolvente, estado_de_la_cache,
                              fase_instantanea, filtro_iir, olvidar_filtros)
from plugins.analysis.time_frequency.pac.compute import (
    FILAS_POR_HZ_PSEL, NBINS, _recorte_por_valles, agrupar_por_fase,
    bordes_bins, centros_bins, cruces_por_cero, detectar_extremos, gabor_tf,
    morse_tf, pac_psel, promediar_bins, remuestrear_en_log,
    seleccionar_valles, vector_medio, ventanas_por_valle, zscore_por_fila)

FS = 1000.0
DUR = 4.0
T = np.arange(int(FS * DUR)) / FS
# Rebanada central, para no medir sobre los transitorios de los filtros
CENTRO = slice(len(T) // 4, 3 * len(T) // 4)


def tono(f_hz, fs=FS, t=None):
    tt = T if t is None else t
    return np.sin(2 * np.pi * f_hz * tt)


# ------------------------------------------------------------------ filtro_iir

@pytest.mark.parametrize("f1,f2,orden_esperado", [
    (3.0, 8.0, 26),        # la banda de fase por defecto de PAC
    (25.0, 250.0, 155),    # una banda de amplitud
])
def test_filtro_iir_calcula_el_orden_automaticamente(f1, f2, orden_esperado):
    """El orden no se elige: lo calcula `cheb2ord` con Rp=0,5 y Rs=100 dB, igual
    que `f_GetIIRFilter`."""
    sos, orden = filtro_iir(FS, f1, f2)
    assert orden == orden_esperado
    assert sos.shape[1] == 6, "debe venir en secciones de segundo orden"


def test_filtro_iir_usa_sos_y_no_coeficientes():
    """Con ordenes de 155 la forma b/a seria numericamente inestable; el MATLAB
    tambien usa secciones de segundo orden (`zp2sos` + `dfilt.df2sos`)."""
    sos, orden = filtro_iir(FS, 25.0, 250.0)
    assert sos.ndim == 2 and sos.shape[0] == orden


@pytest.mark.parametrize("fs,f1,f2,trozo", [
    (0.0, 3.0, 8.0, "muestreo"),
    (FS, 0.0, 8.0, "baja"),
    (FS, 8.0, 3.0, "alta"),
    (FS, 3.0, FS / 2, "Nyquist"),
])
def test_filtro_iir_rechaza_parametros_imposibles(fs, f1, f2, trozo):
    with pytest.raises(ValueError, match=trozo):
        filtro_iir(fs, f1, f2)


def test_filtro_iir_acepta_frecuencias_por_debajo_de_un_hercio():
    """El MATLAB escala la separacion hasta el borde de rechazo cuando la
    frecuencia es menor que 1 Hz; sin eso, el diseno fallaria."""
    sos, orden = filtro_iir(FS, 0.1, 2.0)
    assert orden > 0 and np.all(np.isfinite(sos))


# -------------------------------------------------------------------- bifiltro

def test_bifiltro_es_de_fase_cero():
    """Filtrar hacia adelante y hacia atras cancela el retardo. Si quedara
    desfase, la fase instantanea estaria corrida y PAC entero saldria mal."""
    sos, _ = filtro_iir(FS, 3.0, 8.0)
    entrada = tono(5.0)
    salida = bifiltro(sos, entrada)

    a, b = salida[CENTRO], entrada[CENTRO]
    corr = np.correlate(a, b, "same")
    desfase = int(np.argmax(corr)) - len(b) // 2
    assert desfase == 0, f"quedo un desfase de {desfase} muestras"


def test_bifiltro_deja_pasar_la_banda_y_quita_lo_demas():
    sos, _ = filtro_iir(FS, 3.0, 8.0)
    dentro = bifiltro(sos, tono(5.0))
    fuera = bifiltro(sos, tono(80.0))
    assert np.std(dentro[CENTRO]) > 0.5
    assert np.std(fuera[CENTRO]) < 0.01


def test_bifiltro_rechaza_matrices():
    sos, _ = filtro_iir(FS, 3.0, 8.0)
    with pytest.raises(ValueError, match="una dimensión"):
        bifiltro(sos, np.zeros((4, 10)))


# ----------------------------------------------------------- fase y envolvente

def test_fase_instantanea_da_una_vuelta_por_ciclo():
    """Un seno de 5 Hz tiene que dar 5 vueltas de -pi a pi por segundo."""
    fase = fase_instantanea(tono(5.0), FS, 3.0, 8.0)
    vueltas = int(np.sum(np.diff(fase[CENTRO]) < -np.pi))
    duracion = len(T[CENTRO]) / FS
    assert vueltas / duracion == pytest.approx(5.0, abs=0.1)


def test_fase_instantanea_queda_en_el_rango_correcto():
    fase = fase_instantanea(tono(5.0), FS, 3.0, 8.0)
    assert fase.min() >= -np.pi and fase.max() <= np.pi
    assert fase.shape == T.shape


def test_la_referencia_de_fase_es_el_seno():
    """Detalle que importa al interpretar el resultado: `hilbert(sin(x))` tiene
    angulo `x - pi/2`. Donde el coseno vale 1, la fase medida es -pi/2, no 0."""
    fase = fase_instantanea(tono(5.0), FS, 3.0, 8.0)
    donde_cos_es_maximo = [i for i in range(*CENTRO.indices(len(T)))
                           if abs(np.cos(2 * np.pi * 5 * T[i]) - 1) < 1e-3]
    assert np.mean(fase[donde_cos_es_maximo]) == pytest.approx(-np.pi / 2, abs=0.02)


def test_envolvente_de_un_tono_puro_es_casi_constante():
    env = envolvente(tono(60.0), FS, 40.0, 90.0)
    assert np.std(env[CENTRO]) / np.mean(env[CENTRO]) < 0.05


# -------------------------------------------------------------------- morse_tf

@pytest.mark.parametrize("f_tono", [12.0, 40.0, 90.0])
def test_morse_pone_el_maximo_en_la_frecuencia_del_tono(f_tono):
    tf, _, fr = morse_tf(tono(f_tono), FS, 5.0, 150.0, n_freq=4 * 145)
    pico = fr[int(np.argmax(tf.mean(axis=1)))]
    assert pico == pytest.approx(f_tono, rel=0.02)


def test_morse_devuelve_frecuencia_en_filas_y_tiempo_en_columnas():
    """La cabecera del .m dice lo contrario y esta equivocada: el codigo hace
    `zeros(numel(v_FreqAxis), numel(v_TimeAxis))`."""
    n_freq = 120
    tf, ti, fr = morse_tf(tono(30.0), FS, 10.0, 70.0, n_freq=n_freq)
    assert tf.shape == (n_freq, T.size)
    assert fr.size == n_freq
    assert ti.size == T.size


def test_morse_devuelve_el_eje_de_frecuencias_descendente():
    _, _, fr = morse_tf(tono(30.0), FS, 10.0, 70.0, n_freq=100)
    assert fr[0] > fr[-1]
    assert np.all(np.diff(fr) < 0)


@pytest.mark.parametrize("n", [2000, 2001])
def test_morse_conserva_el_largo_con_entradas_pares_e_impares(n):
    """Con largo par el MATLAB descarta la ultima muestra y despues duplica la
    ultima columna; el resultado tiene que medir lo mismo que la entrada."""
    t = np.arange(n) / FS
    tf, ti, _ = morse_tf(tono(20.0, t=t), FS, 5.0, 50.0, n_freq=90)
    assert tf.shape[1] == n
    assert ti.size == n


def test_morse_devuelve_magnitudes_finitas_y_no_negativas():
    tf, _, _ = morse_tf(tono(30.0), FS, 1.0, 100.0, n_freq=200)
    assert np.all(np.isfinite(tf)), "la primera muestra del eje angular es 0 y da log(0)"
    assert np.all(tf >= 0)


def test_morse_sin_magnitudes_devuelve_complejos():
    tf, _, _ = morse_tf(tono(30.0), FS, 10.0, 70.0, n_freq=60, magnitudes=False)
    assert np.iscomplexobj(tf)


@pytest.mark.parametrize("kwargs,trozo", [
    (dict(fs=0.0), "muestreo"),
    (dict(fmin=0.0), "baja"),
    (dict(fmin=50.0, fmax=10.0), "alta"),
    (dict(n_freq=1), "2 frecuencias"),
])
def test_morse_rechaza_parametros_imposibles(kwargs, trozo):
    base = dict(sig=tono(30.0), fs=FS, fmin=10.0, fmax=70.0, n_freq=60)
    base.update(kwargs)
    with pytest.raises(ValueError, match=trozo):
        morse_tf(**base)


def test_morse_rechaza_senales_muy_cortas():
    with pytest.raises(ValueError, match="al menos 4"):
        morse_tf(np.zeros(3), FS, 10.0, 70.0, n_freq=60)


# ------------------------------------------------------------ bins y agrupado

def test_los_bins_cubren_el_circulo_completo():
    bordes = bordes_bins(100)
    assert bordes.size == 101
    assert bordes[0] == pytest.approx(-np.pi)
    assert bordes[-1] == pytest.approx(np.pi)
    assert centros_bins(100).size == 100


def test_agrupar_cuenta_todas_las_muestras():
    tf = np.ones((5, 1000))
    fase = np.linspace(-np.pi, np.pi, 1000, endpoint=False)
    _, cuenta = agrupar_por_fase(tf, fase)
    assert cuenta.sum() == 1000, "ninguna muestra se puede perder"


def test_agrupar_manda_cada_muestra_al_bin_que_le_toca():
    """Una fase conocida tiene que caer en el bin esperado."""
    bordes = bordes_bins(100)
    objetivo = 30
    fase = np.full(50, (bordes[objetivo] + bordes[objetivo + 1]) / 2)
    tf = np.ones((2, 50))
    suma, cuenta = agrupar_por_fase(tf, fase)
    assert cuenta[objetivo] == 50
    assert cuenta.sum() == 50
    assert suma[0, objetivo] == 50


def test_agrupar_devuelve_suma_y_cuenta_sin_dividir():
    """Separadas a proposito, para poder acumular sobre varios trials antes de
    promediar — que es lo que hace f_Phase_PAC_Average."""
    tf = np.full((3, 200), 2.0)
    fase = np.linspace(-np.pi, np.pi, 200, endpoint=False)
    suma, cuenta = agrupar_por_fase(tf, fase)
    assert suma.shape == (3, 100)
    assert cuenta.shape == (100,)
    assert suma.sum() == pytest.approx(3 * 200 * 2.0)


def test_agrupar_rechaza_formas_que_no_casan():
    with pytest.raises(ValueError, match="deben coincidir"):
        agrupar_por_fase(np.ones((4, 100)), np.zeros(50))
    with pytest.raises(ValueError, match="frecuencia, tiempo"):
        agrupar_por_fase(np.ones(100), np.zeros(100))


# --------------------------------------- el NaN de MATLAB, replicado a proposito

def test_un_bin_vacio_da_nan_como_en_matlab():
    """MATLAB divide sin comprobar: a un bin vacio no se le sumo nada, asi que
    es 0/0 y da NaN —no infinito—. Se replica a proposito."""
    suma = np.zeros((3, 4))
    suma[:, 0] = 5.0
    suma[:, 2] = 7.0
    cuenta = np.array([5.0, 0.0, 7.0, 0.0])
    prom = promediar_bins(suma, cuenta)

    assert np.all(np.isnan(prom[:, 1])) and np.all(np.isnan(prom[:, 3]))
    assert np.all(prom[:, 0] == 1.0) and np.all(prom[:, 2] == 1.0)


def test_una_fila_constante_da_nan_en_el_zscore_como_en_matlab():
    """Mismo caso: el valor menos la media es 0 y la desviacion tambien, asi que
    es 0/0 y da NaN."""
    assert np.all(np.isnan(zscore_por_fila(np.full((2, 10), 3.0))))


def test_el_zscore_normaliza_bien_las_filas_con_variacion():
    m = np.vstack([np.arange(10.0), 5.0 * np.arange(10.0)])
    z = zscore_por_fila(m)
    assert np.allclose(z.mean(axis=1), 0.0, atol=1e-12)
    assert np.allclose(z[0], z[1]), "dos filas proporcionales deben dar el mismo z-score"


def test_el_zscore_normaliza_por_n_menos_1_como_matlab():
    """`std(m, [], 2)` de MATLAB usa N-1, no N.

    La diferencia es un factor `sqrt(N/(N-1))`: con los 100 bins de fase de PAC
    son 1,005, un 0,5 % en todo el mapa. Pasó desapercibido porque ninguna
    prueba comparaba contra MATLAB todavía.
    """
    m = np.vstack([np.arange(10.0), 5.0 * np.arange(10.0)])
    z = zscore_por_fila(m)
    assert np.allclose(z.std(axis=1, ddof=1), 1.0, atol=1e-12), "tiene que ser N-1"
    assert not np.allclose(z.std(axis=1, ddof=0), 1.0, atol=1e-6), "y no N"


# --------------------------------------------------------------- vector medio

def test_el_vector_medio_apunta_a_la_fase_del_maximo():
    bins = centros_bins(100)
    for fase_esperada in (0.0, np.pi / 2, -np.pi / 2, 2.0):
        hist = np.cos(bins - fase_esperada) + 1.0
        v = vector_medio(hist)
        assert np.angle(v) == pytest.approx(fase_esperada, abs=0.05)


def test_un_histograma_plano_da_vector_casi_nulo():
    """Sin acoplamiento, el vector medio tiene que ser corto."""
    assert abs(vector_medio(np.ones(100))) < 1e-12


# ----------------------------------------------------- acoplamiento sintetico

def test_detecta_un_acoplamiento_construido_a_proposito():
    """Prueba de punta a punta: se construye gamma de 60 Hz cuya amplitud es
    maxima en el pico del theta de 5 Hz, y PAC tiene que encontrarlo ahi."""
    lento = np.cos(2 * np.pi * 5 * T)              # con coseno, la fase medida es 2*pi*5*t
    modulador = (1.0 + lento) / 2.0                # maximo donde la fase medida es 0
    sig = lento + 0.4 * modulador * np.sin(2 * np.pi * 60 * T)

    fase = fase_instantanea(sig, FS, 3.0, 8.0)
    tf, _, _ = morse_tf(sig, FS, 30.0, 90.0, n_freq=4 * 60)
    suma, cuenta = agrupar_por_fase(tf, fase)
    prom = promediar_bins(suma, cuenta)
    hist = prom.sum(axis=0)
    v = vector_medio(hist)

    assert np.all(cuenta > 0), "con 4 s a 1 kHz no deberia quedar ningun bin vacio"
    assert not np.any(np.isnan(prom)), "sin bins vacios no deberia haber NaN"
    assert np.angle(v) == pytest.approx(0.0, abs=0.35), \
        f"el acoplamiento se construyo en fase 0 y salio en {np.angle(v):+.3f} rad"


def test_una_senal_sin_acoplamiento_da_un_vector_mucho_menor():
    rng = np.random.default_rng(0)
    lento = np.cos(2 * np.pi * 5 * T)
    sin_acople = lento + 0.4 * np.sin(2 * np.pi * 60 * T)     # gamma de amplitud fija
    modulador = (1.0 + lento) / 2.0
    con_acople = lento + 0.4 * modulador * np.sin(2 * np.pi * 60 * T)

    def fuerza(sig):
        fase = fase_instantanea(sig, FS, 3.0, 8.0)
        tf, _, _ = morse_tf(sig, FS, 30.0, 90.0, n_freq=4 * 60)
        prom = promediar_bins(*agrupar_por_fase(tf, fase))
        return abs(vector_medio(prom.sum(axis=0))) / np.nanmean(prom)

    assert fuerza(con_acople) > 2 * fuerza(sin_acople)


# ==========================================================================
# Fase 2: pac_un_trial y pac_promedio, los ocho pasos compuestos
# ==========================================================================

from plugins.analysis.time_frequency.pac.compute import (  # noqa: E402
    ResultadoPac, pac_promedio, pac_un_trial)

# Parámetros chicos, para que las pruebas corran rápido. Con los de la interfaz
# —1.900 frecuencias— cada trial toma cerca de un segundo.
FS_ARCHIVO = 1000.0
PAR = dict(fs_calculado=FS_ARCHIVO, fs=1000.0, p1=3.0, p2=8.0, a1=25.0, a2=100.0)


def _senal_acoplada(n=2000, fs=FS_ARCHIVO):
    """Gamma de 60 Hz cuya amplitud es máxima en el pico del theta de 5 Hz."""
    t = np.arange(n) / fs
    lento = np.cos(2 * np.pi * 5 * t)
    return lento + 0.4 * ((1.0 + lento) / 2.0) * np.sin(2 * np.pi * 60 * t)


def test_pac_un_trial_devuelve_todo_lo_que_el_dibujo_necesita():
    r = pac_un_trial(None, _senal_acoplada(), **PAR)
    assert isinstance(r, ResultadoPac)

    n_freq = int(round(4 * (PAR["a2"] - PAR["a1"])))
    assert r.mapa.shape == (n_freq, 100)
    assert r.mapa_crudo.shape == (n_freq, 100)
    assert r.frecuencias.size == n_freq and r.frecuencias[0] > r.frecuencias[-1]
    assert r.fases.size == 100
    assert r.histograma.size == 100
    assert r.cuenta_por_bin.size == 100
    assert isinstance(r.vector, complex)
    assert r.n_trials == 1


def test_pac_un_trial_devuelve_las_cuatro_senales_del_dibujo():
    r = pac_un_trial(None, _senal_acoplada(), **PAR)
    n = r.senal.size
    assert r.banda_fase.shape == (n,)
    assert r.fase.shape == (n,)
    assert r.banda_amplitud.shape == (n,)
    assert r.tiempo.size == n


def test_la_banda_de_amplitud_por_defecto_no_sale_en_nan():
    """Regresión. Con la banda por defecto [25, 500] a 2.000 Hz, el orden
    automático del Chebyshev II se dispara a 228, salen coeficientes no finitos
    y el filtrado devuelve NaN en todo. Por eso ese panel usa Butterworth de
    orden 8, igual que MATLAB."""
    t = np.arange(6000) / 2000.0
    sig = np.cos(2 * np.pi * 5 * t) + 0.3 * np.sin(2 * np.pi * 120 * t)
    r = pac_un_trial(None, sig, fs_calculado=2000.0, fs=2000.0,
                     p1=3.0, p2=8.0, a1=25.0, a2=500.0)
    assert np.all(np.isfinite(r.banda_amplitud)), "el filtro de amplitud devolvio NaN"
    assert np.std(r.banda_amplitud) > 0


def test_pac_encuentra_el_acoplamiento_donde_se_construyo():
    r = pac_un_trial(None, _senal_acoplada(), **PAR)
    assert np.all(r.cuenta_por_bin > 0), "no deberia quedar ningun bin vacio"
    assert not np.any(np.isnan(r.mapa_crudo))
    assert np.angle(r.vector) == pytest.approx(0.0, abs=0.4)


def test_el_submuestreo_usa_la_tasa_efectiva():
    """Pedir 300 Hz sobre 1.000 da factor 3 y deja la señal en 333,3 Hz."""
    r = pac_un_trial(None, _senal_acoplada(), fs_calculado=1000.0, fs=300.0,
                     p1=3.0, p2=8.0, a1=25.0, a2=100.0)
    assert r.fs_efectiva == pytest.approx(1000.0 / 3)
    assert r.senal.size == pytest.approx(2000 / 3, abs=1)


@pytest.mark.parametrize("cambio,trozo", [
    (dict(p1=0.0), "baja de fase"),
    (dict(p2=1.0), "alta de fase"),
    (dict(a1=0.0), "baja de amplitud"),
    (dict(a2=10.0), "alta de amplitud"),
    (dict(a2=600.0), "densidad efectiva"),
])
def test_pac_rechaza_parametros_imposibles(cambio, trozo):
    par = dict(PAR)
    par.update(cambio)
    with pytest.raises(ValueError, match=trozo):
        pac_un_trial(None, _senal_acoplada(), **par)


def test_pac_rechaza_una_senal_demasiado_corta():
    with pytest.raises(ValueError, match="al menos 4"):
        pac_un_trial(None, np.zeros(6), fs_calculado=1000.0, fs=100.0,
                     p1=3.0, p2=8.0, a1=25.0, a2=45.0)


# ------------------------------------------------------------- el acumulador

def test_el_promedio_de_un_trial_da_lo_mismo_que_el_individual():
    sig = _senal_acoplada()
    uno = pac_un_trial(None, sig, **PAR)
    prom = pac_promedio(None, sig[:, None], **PAR)

    assert np.array_equal(uno.mapa_crudo, prom.mapa_crudo)
    assert np.array_equal(uno.histograma, prom.histograma)
    assert uno.vector == prom.vector
    assert prom.n_trials == 1


def test_el_promedio_acumula_antes_de_dividir():
    """Dos trials idénticos tienen que dar el mismo mapa que uno solo: el
    acumulador suma y divide una vez al final, no promedia promedios."""
    sig = _senal_acoplada()
    uno = pac_un_trial(None, sig, **PAR)
    dos = pac_promedio(None, np.column_stack([sig, sig]), **PAR)

    assert dos.n_trials == 2
    assert np.allclose(dos.mapa_crudo, uno.mapa_crudo, equal_nan=True)
    assert dos.cuenta_por_bin.sum() == 2 * uno.cuenta_por_bin.sum()


def test_el_promedio_acepta_un_vector_de_una_dimension():
    sig = _senal_acoplada()
    assert pac_promedio(None, sig, **PAR).n_trials == 1


def test_el_promedio_rechaza_una_matriz_sin_trials():
    with pytest.raises(ValueError, match="No hay trials"):
        pac_promedio(None, np.zeros((2000, 0)), **PAR)


# -------------------------------------------------------- avance y cancelacion

class _Ctx:
    def __init__(self, cancelar_en=None):
        self.cancelar_en = cancelar_en
        self.avisos = []
        self._n = 0

    @property
    def cancelled(self):
        self._n += 1
        return self.cancelar_en is not None and self._n >= self.cancelar_en

    def progress(self, pct, msg=""):
        self.avisos.append((pct, msg))


def test_reporta_avance_en_espanol():
    ctx = _Ctx()
    pac_un_trial(ctx, _senal_acoplada(), **PAR)
    assert ctx.avisos, "deberia reportar avance"
    assert ctx.avisos[-1][0] == 100
    assert all(0 <= p <= 100 for p, _ in ctx.avisos)


def test_el_promedio_reporta_un_aviso_por_trial():
    sig = _senal_acoplada()
    ctx = _Ctx()
    pac_promedio(ctx, np.column_stack([sig] * 3), **PAR)
    mensajes = [m for _, m in ctx.avisos]
    assert "Trial 1/3" in mensajes and "Trial 3/3" in mensajes


def test_se_puede_cancelar_antes_de_empezar():
    ctx = _Ctx(cancelar_en=1)
    assert pac_un_trial(ctx, _senal_acoplada(), **PAR) is None
    assert pac_promedio(ctx, _senal_acoplada(), **PAR) is None


# ==================================================================== gabor_tf
# La transformada de PAC Psel (Fase 5). No es la Morse: `f_Phase_PAC_Pdetect`
# llama a `f_GaborAWTransformMatlab`, que es otra funcion entera.

def gabor_literal(sig, fs, fmin, fmax, nfreq, ciclos):
    """Traducción línea por línea de `f_GaborAWTransformMatlab`, sin optimizar.

    Sirve de oráculo: el porte de verdad reordena operaciones para no reservar
    memoria de más —escribe fila a fila, normaliza sobre el mismo arreglo— y
    conviene tener contra qué comprobar que esos atajos no cambian el número.
    """
    v = np.asarray(sig, float).ravel()
    paso = (fmax - fmin) / (nfreq - 1)
    eje = np.arange(fmin, fmax + paso / 2, paso)[:nfreq][::-1]      # fliplr
    if v.size % 2 == 0:
        v = v[:-1]
    t = np.arange(v.size) / fs
    largo = t.size
    mitad = largo // 2 + 1
    w = (2 * np.pi / largo) * np.arange(largo) * fs
    fft_sig = np.fft.fft(v, v.size)
    m = np.zeros((eje.size, t.size), complex)
    for k, f in enumerate(eje):
        sd = (1.0 / f) * ciclos
        win = np.zeros(largo)
        win[:mitad] = np.exp(-0.5 * np.power(w[:mitad] - 2 * np.pi * f, 2) * sd ** 2)
        win = win * np.sqrt(largo) / np.linalg.norm(win, 2)
        m[k, :] = np.fft.ifft(fft_sig * win) / np.sqrt(sd)
    return np.abs(m), t, eje


@pytest.mark.parametrize("n,fmin,fmax,nfreq,ciclos", [
    (1001, 25.0, 129.0, 208, 1.0),   # lo que usa PAC Psel: n_freq = 2*(129-25)
    (1000, 10.0, 100.0, 180, 1.0),   # largo PAR, que descarta una muestra
    (777, 5.0, 60.0, 50, 3.0),       # con los 3 ciclos que dice la cabecera del .m
])
def test_gabor_coincide_con_la_traduccion_literal(n, fmin, fmax, nfreq, ciclos):
    x = np.random.default_rng(0).standard_normal(n)
    a, ta, fa = gabor_tf(x, FS, fmin, fmax, nfreq, cycles=ciclos)
    b, tb, fb = gabor_literal(x, FS, fmin, fmax, nfreq, ciclos)
    assert a.shape == b.shape
    assert np.abs(a - b).max() < 1e-10, "el porte se separó de la referencia literal"
    assert np.allclose(fa, fb) and np.allclose(ta, tb)


@pytest.mark.parametrize("f0", [30.0, 55.0, 80.0, 120.0])
def test_gabor_pone_el_maximo_en_la_frecuencia_del_tono(f0):
    """Si la ventana estuviera mal centrada, el máximo saldría en otra parte."""
    t = np.arange(2001) / FS
    tf, _, fr = gabor_tf(np.sin(2 * np.pi * f0 * t), FS, 25.0, 129.0, 208)
    centro = tf[:, tf.shape[1] // 4: 3 * tf.shape[1] // 4]
    pico = fr[np.argmax(centro.mean(axis=1))]
    paso = (129.0 - 25.0) / 207
    assert abs(pico - f0) <= paso, f"máximo en {pico:.2f} Hz para un tono de {f0} Hz"


def test_gabor_devuelve_el_eje_de_frecuencias_descendente():
    _, _, fr = gabor_tf(np.random.default_rng(0).standard_normal(501), FS, 25.0, 129.0, 208)
    assert fr[0] > fr[-1] and np.all(np.diff(fr) < 0)
    assert fr[0] == pytest.approx(129.0) and fr[-1] == pytest.approx(25.0)


def test_gabor_con_largo_par_no_repone_la_columna_y_la_morse_si():
    """**La diferencia entre las dos transformadas, fijada a propósito.**

    Las dos descartan la última muestra si el largo es par, pero
    `f_MorseAWTransformMatlab` repone la columna al final (`horzcat`, línea 241)
    y `f_GaborAWTransformMatlab` no tiene ese bloque. Si alguien "uniformara"
    las dos, rompería la paridad con MATLAB en una de ellas.
    """
    x = np.random.default_rng(0).standard_normal(1000)
    g, tg, _ = gabor_tf(x, FS, 25.0, 129.0, 20)
    m, tm, _ = morse_tf(x, FS, 25.0, 129.0, 20)
    assert g.shape[1] == 999, "la Gabor entrega la señal recortada"
    assert m.shape[1] == 1000, "la Morse repone la columna"
    assert tg.size == 999 and tm.size == 1000


def test_gabor_avisa_en_vez_de_recortar_al_nyquist_como_matlab():
    """**Divergencia deliberada.** MATLAB recorta `ps_MaxFreqHz` al Nyquist sin
    decir nada, así que quien pide un análisis hasta 900 Hz sobre una señal de
    1.000 recibe uno hasta 500 y lo lee como si cubriera lo que pidió.

    `_preparar` ya se negaba para la Morse; dejar una transformada recortando y
    la otra avisando era lo peor de los dos mundos.
    """
    with pytest.raises(ValueError, match="Nyquist"):
        gabor_tf(np.random.default_rng(0).standard_normal(501), FS, 25.0, 900.0, 10)


def test_gabor_rechaza_la_frecuencia_baja_en_cero():
    """MATLAB la sube de 0 a 0,1 en silencio; aquí se avisa, como en la Morse."""
    with pytest.raises(ValueError, match="mayor que cero"):
        gabor_tf(np.random.default_rng(0).standard_normal(501), FS, 0.0, 50.0, 10)


def test_gabor_puede_devolver_los_coeficientes_complejos():
    x = np.random.default_rng(0).standard_normal(501)
    comp, _, _ = gabor_tf(x, FS, 25.0, 129.0, 20, magnitudes=False)
    mag, _, _ = gabor_tf(x, FS, 25.0, 129.0, 20)
    assert np.iscomplexobj(comp) and not np.iscomplexobj(mag)
    assert np.allclose(np.abs(comp), mag)


@pytest.mark.parametrize("kwargs,trozo", [
    (dict(sig=np.zeros(2)), "al menos 4"),
    (dict(fs=0.0), "muestreo"),
    (dict(fmin=-1.0), "mayor que cero"),
    (dict(fmin=200.0, fmax=100.0), "debe ser mayor"),
    (dict(n_freq=1), "al menos 2"),
    (dict(cycles=0.0), "ciclos"),
])
def test_gabor_valida_sus_parametros_en_espanol(kwargs, trozo):
    args = dict(sig=np.random.default_rng(0).standard_normal(501), fs=FS,
                fmin=25.0, fmax=129.0, n_freq=20)
    args.update(kwargs)
    with pytest.raises(ValueError, match=trozo):
        gabor_tf(**args)


# ========================================================= deteccion de ciclos
# Lo propio de PAC Psel: en vez de recorrer la señal entera, busca ciclos
# completos del ritmo lento y promedia ventanas centradas en sus valles.

FS_PSEL = 2000.0       # el muestreo por defecto de PAC
P1_PSEL, P2_PSEL = 3.0, 8.0
SEMIANCHO = int(np.floor(2 * (0.5 / P1_PSEL) * FS_PSEL))


def ritmo_lento(f_hz=5.0, dur=6.0, fs=FS_PSEL):
    """Un seno limpio dentro de la banda de fase 3-8 Hz, con sus ciclos contados."""
    t = np.arange(int(fs * dur)) / fs
    return t, np.sin(2 * np.pi * f_hz * t)


def valles_elegidos(y, t, p1=P1_PSEL, p2=P2_PSEL):
    picos, valles = detectar_extremos(y)
    return seleccionar_valles(y, t, picos, valles, cruces_por_cero(y), 0.5 / p2, 0.5 / p1)


def test_detectar_extremos_encuentra_un_pico_y_un_valle_por_ciclo():
    t, y = ritmo_lento(f_hz=5.0, dur=6.0)      # 30 ciclos
    picos, valles = detectar_extremos(y)
    assert picos.size == 30 and valles.size == 30
    assert np.all(y[picos] > 0.99) and np.all(y[valles] < -0.99)


def test_cruces_por_cero_da_dos_por_ciclo():
    t, y = ritmo_lento(f_hz=5.0, dur=6.0)
    # 30 ciclos -> 60 cruces, mas el que anade el circshift al dar la vuelta
    assert cruces_por_cero(y).size == 61


def test_cruces_por_cero_replica_el_circshift_circular():
    """**No es una errata del porte: es lo que hace el MATLAB.**

    `circshift(v, [-1 0])` mueve el primer elemento al final, así que la última
    muestra se compara con la primera y puede salir marcada por casualidad.
    """
    assert cruces_por_cero(np.array([1.0, 2.0, 3.0, -1.0])).tolist() == [2, 3]
    assert cruces_por_cero(np.array([1.0, 2.0, 3.0, 4.0])).tolist() == []


def test_los_valles_elegidos_van_separados_un_periodo():
    t, y = ritmo_lento(f_hz=5.0, dur=6.0)
    sel = valles_elegidos(y, t)
    assert sel.size >= 25, f"solo se eligieron {sel.size} de 30 ciclos"
    separacion = np.diff(sel) / FS_PSEL
    assert np.allclose(separacion, 1 / 5.0, atol=1e-3), "deberían ir a un periodo exacto"


def test_descarta_los_ciclos_fuera_del_rango_de_periodos():
    """Un ritmo de 1 Hz no cabe en la banda 3-8: su semiperiodo pasa de `max_t`."""
    t, y = ritmo_lento(f_hz=1.0, dur=6.0)
    assert valles_elegidos(y, t).size == 0


def test_el_primero_y_los_dos_ultimos_valles_nunca_se_eligen():
    """`v_sel(1)=0`, `v_sel(end-1)=0` y `v_sel(end)=0` en el MATLAB."""
    t, y = ritmo_lento(f_hz=5.0, dur=6.0)
    _, valles = detectar_extremos(y)
    sel = valles_elegidos(y, t)
    assert valles[0] not in sel
    assert valles[-1] not in sel and valles[-2] not in sel


def test_las_ventanas_quedan_centradas_en_el_valle():
    t, y = ritmo_lento(f_hz=5.0, dur=6.0)
    sel = valles_elegidos(y, t)
    mats, fuera = ventanas_por_valle({"theta": y}, sel, SEMIANCHO)
    m = mats["theta"]
    assert m.shape[0] == 2 * SEMIANCHO + 1
    assert fuera == 0
    assert np.allclose(m[SEMIANCHO, :], -1.0, atol=1e-6), "el centro tiene que ser el valle"


def test_las_ventanas_se_saltan_los_dos_primeros_valles():
    """El `for count=3:size(v_sel_lws,1)` del original."""
    t, y = ritmo_lento(f_hz=5.0, dur=6.0)
    sel = valles_elegidos(y, t)
    mats, _ = ventanas_por_valle({"theta": y}, sel, SEMIANCHO)
    assert mats["theta"].shape[1] == sel.size - 2


def test_los_ciclos_pegados_al_borde_se_omiten_en_vez_de_reventar():
    """**Desviación deliberada.** MATLAB recorta sin mirar los bordes y se cae
    con un error de índice; aquí se omiten y se informa de cuántos."""
    y = np.zeros(1000)
    valles = np.array([10, 20, 500, 995])       # los dos primeros se saltan igual
    mats, fuera = ventanas_por_valle({"a": y}, valles, 100)
    assert mats["a"].shape[1] == 1, "solo el de la muestra 500 cabe entero"
    assert fuera == 1, "el de la 995 se omite"


def test_ventanas_por_valle_exige_que_las_senales_midan_lo_mismo():
    with pytest.raises(ValueError, match="largos distintos"):
        ventanas_por_valle({"a": np.zeros(100), "b": np.zeros(90)}, np.array([10, 20, 50]), 5)


def test_sin_suficientes_valles_no_se_elige_ninguno():
    t = np.arange(100) / FS_PSEL
    assert seleccionar_valles(np.zeros(100), t, np.array([]), np.array([]),
                              np.array([]), 0.0625, 0.167).size == 0


# ================================================================== pac_psel
# Fase 5. Concatena los trials, busca ciclos completos del ritmo lento y
# promedia ventanas centradas en sus valles. Usa Gabor, no Morse.

FR_PSEL = 45.0          # la portadora rapida: dentro de la banda 25-60 que usan
                        # las pruebas, que es estrecha a proposito para correr rapido
FL_PSEL = 5.0           # el ritmo lento, dentro de la banda de fase 3-8


def senal_psel(acoplada=True, n_trials=6, dur=3.0, fs=FS_PSEL, semilla=0):
    """Trials con la amplitud de 70 Hz enganchada al **valle** del ritmo lento.

    El valle importa: las ventanas se centran ahi, asi que un acoplamiento en
    el valle tiene que salir con el vector medio apuntando a ±pi.
    """
    t = np.arange(int(fs * dur)) / fs
    lento = np.sin(2 * np.pi * FL_PSEL * t)
    env = (1 - lento) / 2 if acoplada else np.full_like(t, 0.5)
    rng = np.random.default_rng(semilla)
    return np.column_stack([
        lento + 0.6 * env * np.sin(2 * np.pi * FR_PSEL * t)
        + 0.05 * rng.standard_normal(t.size) for _ in range(n_trials)])


@pytest.fixture(scope="module")
def psel():
    """Un unico calculo para todas las comprobaciones: es el mas caro de la suite."""
    return pac_psel(CtxPsel(), senal_psel(), FS_PSEL, FS_PSEL,
                    p1=3.0, p2=8.0, a1=25.0, a2=60.0)


@pytest.fixture(scope="module")
def psel_control():
    """Lo mismo pero sin acoplamiento, para comparar contra algo."""
    return pac_psel(CtxPsel(), senal_psel(acoplada=False), FS_PSEL, FS_PSEL,
                    p1=3.0, p2=8.0, a1=25.0, a2=60.0)


class CtxPsel:
    cancelled = False

    def __init__(self):
        self.avances = []

    def progress(self, pct, msg=""):
        self.avances.append((pct, msg))


def test_psel_detecta_el_acoplamiento_y_el_control_no(psel, psel_control):
    """**La prueba que de verdad discrimina.**

    El mapa en z no sirve para esto: normaliza cada fila a desviacion 1, asi que
    todas acaban pareciendose. Lo que separa los dos casos es el vector medio,
    que es ademas la salida que el algoritmo reporta.
    """
    assert abs(psel.vector) > 0.5, f"con acoplamiento salio {abs(psel.vector):.4f}"
    assert abs(psel_control.vector) < 0.1, f"sin acoplamiento salio {abs(psel_control.vector):.4f}"
    assert abs(psel.vector) > 10 * abs(psel_control.vector)


def test_psel_apunta_a_la_fase_donde_se_construyo(psel):
    """El gamma se puso en el valle del ritmo lento, que es la fase ±pi."""
    assert abs(abs(np.angle(psel.vector)) - np.pi) < 0.4, \
        f"el vector apunta a {np.angle(psel.vector):+.3f} rad"


def test_psel_devuelve_el_mapa_con_la_forma_correcta(psel):
    assert psel.mapa.shape == (psel.frecuencias.size, NBINS)
    assert psel.histograma.shape == (NBINS,)
    assert psel.fases.shape == (NBINS,)


def test_psel_usa_dos_filas_por_hz_y_no_cuatro_como_pac(psel):
    """`ps_FreqSeg = 2*(A2-A1)` en Pdetect, contra `4*` en f_Phase_PAC."""
    assert psel.frecuencias.size == int(FILAS_POR_HZ_PSEL * (60.0 - 25.0)) == 70


def test_psel_devuelve_el_eje_de_frecuencias_descendente(psel):
    assert psel.frecuencias[0] > psel.frecuencias[-1]
    assert psel.frecuencias[0] == pytest.approx(60.0)
    assert psel.frecuencias[-1] == pytest.approx(25.0)


def test_psel_agrupa_los_vectores_de_seis_en_seis_dejando_cuatro_bins_fuera(psel):
    """El bucle del MATLAB avanza de 6 en 6 mientras el indice sea <= 95, asi
    que cubre 96 de los 100 bins y los 4 ultimos no entran en ningun grupo."""
    assert psel.vectores_por_grupo.shape == (16,)
    esperado = (psel.histograma * np.exp(1j * psel.fases))[0:6].mean()
    assert psel.vectores_por_grupo[0] == pytest.approx(esperado)


def test_psel_concatena_los_trials_en_vez_de_promediarlos(psel):
    """Con mas trials salen mas ciclos: si los promediara, saldrian los mismos."""
    pocos = pac_psel(CtxPsel(), senal_psel(n_trials=3), FS_PSEL, FS_PSEL,
                     p1=3.0, p2=8.0, a1=25.0, a2=60.0)
    assert psel.n_ciclos > pocos.n_ciclos * 1.5


def test_psel_informa_de_las_medidas_resumen(psel):
    assert psel.vpp > 0 and psel.vpp_full > 0 and psel.vrms > 0
    assert psel.n_ciclos > 10
    assert psel.ciclos_descartados >= 0


def test_psel_devuelve_las_tres_pilas_de_ciclos(psel):
    """`m_lows_full`, `m_lows_theta` y `m_lows_gamma`. El MATLAB **no recorta**
    la de gamma, asi que es mas alta que las otras dos."""
    assert psel.ciclos_full.shape == psel.ciclos_theta.shape
    assert psel.ciclos_full.shape[1] == psel.n_ciclos
    assert psel.ciclos_gamma.shape[0] > psel.ciclos_theta.shape[0]


def test_psel_devuelve_el_mapa_tiempo_frecuencia_promedio(psel):
    assert psel.mapa_tf.shape[0] == psel.frecuencias.size
    assert psel.mapa_tf.shape[1] == psel.tiempo_tf.size
    assert psel.promedio_theta.size == psel.tiempo_tf.size


def test_psel_informa_del_avance_y_termina_en_cien():
    ctx = CtxPsel()
    pac_psel(ctx, senal_psel(), FS_PSEL, FS_PSEL, p1=3.0, p2=8.0, a1=25.0, a2=60.0)
    pcts = [p for p, _ in ctx.avances]
    assert pcts == sorted(pcts) and pcts[-1] == 100
    assert any(m.startswith("Ciclo") for _, m in ctx.avances)


def test_psel_cancelado_devuelve_none():
    ctx = CtxPsel()
    ctx.cancelled = True
    assert pac_psel(ctx, senal_psel(), FS_PSEL, FS_PSEL,
                    p1=3.0, p2=8.0, a1=25.0, a2=60.0) is None


def test_psel_avisa_en_espanol_si_no_hay_ciclos_suficientes():
    """Un ritmo de 1 Hz no cabe en la banda 3-8, asi que no hay ciclos validos."""
    t = np.arange(int(FS_PSEL * 2)) / FS_PSEL
    plano = np.column_stack([np.sin(2 * np.pi * 1.0 * t)] * 2)
    with pytest.raises(ValueError, match="ciclos utilizables"):
        pac_psel(CtxPsel(), plano, FS_PSEL, FS_PSEL, p1=3.0, p2=8.0, a1=25.0, a2=60.0)


def test_psel_avisa_si_no_hay_trials():
    with pytest.raises(ValueError, match="No hay trials"):
        pac_psel(CtxPsel(), np.empty((0, 0)), FS_PSEL, FS_PSEL,
                 p1=3.0, p2=8.0, a1=25.0, a2=60.0)


# ------------------------------------------------- el recorte por valles

@pytest.mark.parametrize("n_valles,esperado", [
    (3, "primero_a_tercero"),
    (5, "segundo_a_cuarto"),
    (1, "entero"),
    (2, "entero"),
    (0, "entero"),
])
def test_el_recorte_sigue_la_tabla_del_matlab(n_valles, esperado):
    """Lineas 303-315. Con 0 valles MATLAB deja `ct1`/`ct2` sin asignar y se
    cae; aqui se devuelve el tramo entero, como ya hace con 1 y con 2."""
    t = np.linspace(0, n_valles + 0.5, 400) if n_valles else np.linspace(0, 0.4, 400)
    av = np.cos(2 * np.pi * t) if n_valles else np.linspace(0.0, 1.0, 400)
    valles, _ = find_peaks(-av)
    if valles.size != n_valles:
        pytest.skip(f"la señal de prueba dio {valles.size} valles y no {n_valles}")
    ct1, ct2 = _recorte_por_valles(av)
    if esperado == "entero":
        assert (ct1, ct2) == (0, len(av) - 1)
    elif esperado == "primero_a_tercero":
        assert (ct1, ct2) == (int(valles[0]), int(valles[2]))
    else:
        assert (ct1, ct2) == (int(valles[1]), int(valles[3]))


# ======================================================== remuestrear_en_log
# El eje del mapa de PAC Psel. `f_Phase_PAC` llama a f_ImageMatrix con 6
# argumentos (rama de imagesc, eje lineal); Pdetect llama con 10 (rama de
# pcolor) y ademas pasa el eje por log10, asi que las filas van a alturas
# desiguales y hay que remuestrear antes de dibujarlas con una imagen uniforme.

def test_el_remuestreo_deja_el_eje_ascendente_y_en_logaritmo():
    fr = np.linspace(25.0, 129.0, 208)[::-1]        # como sale de la Gabor
    m = np.arange(208.0)[:, None] * np.ones((1, 5))
    out, lmin, lmax = remuestrear_en_log(m, fr)
    assert out.shape == m.shape
    assert lmin == pytest.approx(np.log10(25.0)) and lmax == pytest.approx(np.log10(129.0))
    # la fila 0 de la salida es la frecuencia mas BAJA, que en la entrada
    # descendente era la ultima
    assert out[0, 0] == pytest.approx(207.0)
    assert out[-1, 0] == pytest.approx(0.0)


def test_el_remuestreo_comprime_de_verdad_las_frecuencias_altas():
    """Si esto saliera lineal, el eje mentiría: las etiquetas dirían logaritmo
    y las filas estarían repartidas a intervalos iguales."""
    fr = np.linspace(25.0, 129.0, 208)[::-1]
    _, lmin, lmax = remuestrear_en_log(np.zeros((208, 3)), fr)
    medio = 10 ** ((lmin + lmax) / 2)
    assert medio == pytest.approx(np.sqrt(25.0 * 129.0), rel=1e-9), "la media geométrica"
    assert medio < (25.0 + 129.0) / 2, "y por debajo de la media aritmética"


def test_el_remuestreo_usa_el_vecino_mas_cercano_y_no_interpola():
    """`pcolor` con `shading flat` pinta cada celda de un color plano, así que
    interpolar inventaría valores que la referencia no muestra."""
    fr = np.array([100.0, 10.0])
    m = np.array([[5.0], [1.0]])          # 100 Hz -> 5, 10 Hz -> 1
    out, _, _ = remuestrear_en_log(m, fr, n_filas=5)
    assert set(np.unique(out)) <= {1.0, 5.0}, "no deben aparecer valores intermedios"
    assert out[0, 0] == 1.0 and out[-1, 0] == 5.0


def test_el_remuestreo_puede_cambiar_el_numero_de_filas():
    fr = np.linspace(25.0, 129.0, 50)[::-1]
    out, _, _ = remuestrear_en_log(np.random.default_rng(0).standard_normal((50, 4)), fr,
                                   n_filas=300)
    assert out.shape == (300, 4)


@pytest.mark.parametrize("mapa,frecs,trozo", [
    (np.zeros(10), np.arange(10.0) + 1, "dos dimensiones"),
    (np.zeros((5, 3)), np.arange(4.0) + 1, "5 filas"),
    (np.zeros((1, 3)), np.array([10.0]), "al menos 2 frecuencias"),
    (np.zeros((2, 3)), np.array([0.0, 10.0]), "logaritmo"),
])
def test_el_remuestreo_valida_en_espanol(mapa, frecs, trozo):
    with pytest.raises(ValueError, match=trozo):
        remuestrear_en_log(mapa, frecs)


# ============================================== la cache de diseños de filtro
# El diseño no depende de la señal, solo de (fs, f1, f2), y es lo caro: medido
# sobre las 178 bandas de amplitud de MI, el 86 % del tiempo se va en diseñar y
# solo el 14 % en aplicar. Con el selector de trial, cada flecha los rediseñaba.

def test_el_diseno_se_recuerda_entre_llamadas():
    olvidar_filtros()
    filtro_iir(FS, 10.0, 20.0)
    assert estado_de_la_cache().misses == 1 and estado_de_la_cache().hits == 0
    filtro_iir(FS, 10.0, 20.0)
    assert estado_de_la_cache().hits == 1, "la segunda llamada debería salir de la caché"


def test_una_banda_distinta_no_reusa_el_diseno():
    olvidar_filtros()
    filtro_iir(FS, 10.0, 20.0)
    filtro_iir(FS, 11.0, 21.0)
    assert estado_de_la_cache().misses == 2


def test_el_muestreo_forma_parte_de_la_clave():
    """Un mismo par de frecuencias a otra tasa es otro filtro: si se reutilizara,
    el resultado sería silenciosamente incorrecto."""
    olvidar_filtros()
    sos_a, _ = filtro_iir(1000.0, 10.0, 20.0)
    sos_b, _ = filtro_iir(2000.0, 10.0, 20.0)
    assert estado_de_la_cache().misses == 2
    assert not np.allclose(sos_a, sos_b), "son filtros distintos"


def test_la_cache_devuelve_el_mismo_filtro_que_sin_cache():
    olvidar_filtros()
    primero, orden1 = filtro_iir(FS, 3.0, 8.0)
    segundo, orden2 = filtro_iir(FS, 3.0, 8.0)
    assert np.array_equal(primero, segundo) and orden1 == orden2


def test_se_devuelve_una_copia_para_que_nadie_envenene_la_cache():
    """**La razón de devolver copia.** Si saliera la matriz guardada, a quien la
    modificara le cambiaría el filtro a todos los que vinieran después, y el
    fallo aparecería en otro plugin y en otro momento."""
    olvidar_filtros()
    sos, _ = filtro_iir(FS, 10.0, 20.0)
    original = float(sos[0, 0])
    sos[0, 0] = 999.0
    otra, _ = filtro_iir(FS, 10.0, 20.0)
    assert otra[0, 0] == pytest.approx(original)
    assert otra[0, 0] != 999.0


def test_los_errores_no_se_cachean():
    """`lru_cache` no guarda excepciones, así que un parámetro inválido tiene que
    avisar **siempre**, no solo la primera vez."""
    olvidar_filtros()
    for _ in range(3):
        with pytest.raises(ValueError, match="Nyquist"):
            filtro_iir(FS, 400.0, 600.0)
    assert estado_de_la_cache().currsize == 0, "un diseño fallido no debe ocupar sitio"


def test_olvidar_filtros_vacia_la_cache():
    filtro_iir(FS, 10.0, 20.0)
    assert estado_de_la_cache().currsize >= 1
    olvidar_filtros()
    assert estado_de_la_cache().currsize == 0


def test_el_comodulograma_reutiliza_los_filtros_entre_trials():
    """La prueba de que la ganancia es real y no una medición de laboratorio:
    el segundo trial no debe diseñar ni un filtro nuevo."""
    from plugins.analysis.time_frequency.modulation_index.compute import comodulograma

    class Ctx:
        cancelled = False

        def progress(self, *a, **k):
            pass

    t = np.arange(3000) / FS
    args = dict(p_ini=2.0, p_fin=6.0, pstep=1.0, a_ini=30.0, a_fin=120.0, astep=0.5)
    olvidar_filtros()
    comodulograma(Ctx(), np.sin(2 * np.pi * 5 * t), FS, FS, limite_matlab=True, **args)
    tras_el_primero = estado_de_la_cache().misses
    comodulograma(Ctx(), np.cos(2 * np.pi * 5 * t), FS, FS, limite_matlab=True, **args)
    assert estado_de_la_cache().misses == tras_el_primero, \
        "el segundo trial diseñó filtros que ya existían"
    assert estado_de_la_cache().hits >= tras_el_primero

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

from core.filters.iir import bifiltro, envolvente, fase_instantanea, filtro_iir
from plugins.analysis.time_frequency.pac.compute import (
    agrupar_por_fase, bordes_bins, centros_bins, morse_tf, promediar_bins,
    vector_medio, zscore_por_fila)

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
    assert np.allclose(z.std(axis=1), 1.0, atol=1e-12)
    assert np.allclose(z[0], z[1]), "dos filas proporcionales deben dar el mismo z-score"


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

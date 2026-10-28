"""El núcleo de PPC, contra verdad conocida.

No se compara contra MATLAB: `f_phase_coherence` da 1 donde no hay nada, así
que parecerse a él sería el fallo. Se compara contra señales construidas a
mano, donde se sabe de antemano qué tiene que salir.

Las tres que más importan, porque son las que el original no pasa:

- ruido independiente en los dos canales → **0 en toda la banda**, incluidas
  las frecuencias bajas que MATLAB clava en 1,000000;
- una senoidal contra ruido puro → **0 también en su frecuencia**, donde
  MATLAB da 0,99993;
- y que el valor no dependa de cuántas muestras entraron, que es justo lo que
  el PPC corrige del PLV.
"""
import numpy as np
import pytest

from plugins.analysis.connectivity.ppc import compute as pc

FS = 500.0
DUR = 2.0
N = int(FS * DUR)
N_TR = 10
BANDA = (8.0, 200.0)
N_FREQ = 40
T = np.arange(N) / FS


def mapa(x1, x2, **kw):
    kw.setdefault("n_freq", N_FREQ)
    return pc.ppc_mapa(None, x1, x2, FS, FS, *BANDA, **kw)


def fila(r, f):
    """El valor medio de la fila más cercana a `f`."""
    i = int(np.argmin(np.abs(r.frecuencias - f)))
    return float(np.nanmean(r.mapa[i]))


def ruido(semilla, n_tr=N_TR):
    return np.random.default_rng(semilla).normal(size=(N, n_tr))


def fases_iniciales(semilla, n_tr=N_TR):
    """Una fase de arranque distinta por trial, compartida por los dos canales.

    Es lo que hace que el acoplamiento esté en la **diferencia** y no en la fase
    absoluta, que es como se comporta una señal de verdad.
    """
    return np.random.default_rng(semilla).uniform(-np.pi, np.pi, n_tr)


def tono(f, fase0, desfase=0.0, semilla_ruido=0, amp_ruido=0.1):
    """Un tono con esas fases de arranque, más ruido **propio de este canal**.

    El ruido no es decorativo y la semilla propia tampoco. El PPC solo mira
    fase: si los dos canales llevan el mismo ruido, ese ruido está perfectamente
    acoplado y el mapa sale en 1 a todas las frecuencias. Y sin nada de ruido
    manda la fuga espectral del tono, que también va coherente. Un 1 % ya basta
    para dejar solo la banda real; aquí va 10 %, que es realista.
    """
    rng = np.random.default_rng(semilla_ruido)
    return np.stack([np.sin(2 * np.pi * f * T + p + desfase) + amp_ruido * rng.normal(size=N)
                     for p in fase0], axis=1)


@pytest.fixture(scope="module")
def con_ruido():
    return mapa(ruido(1), ruido(2))


# ============================================================
#   Lo que MATLAB no consigue
# ============================================================
def test_ruido_independiente_da_cero_en_toda_la_banda(con_ruido):
    valores = con_ruido.mapa[~np.isnan(con_ruido.mapa)]
    assert abs(valores.mean()) < 0.05
    por_fila = np.nanmean(con_ruido.mapa, axis=1)
    assert np.all(np.abs(por_fila) < 0.25), (
        f"alguna fila se despega: máximo {np.nanmax(np.abs(por_fila)):.3f}")


def test_las_frecuencias_bajas_ya_no_salen_clavadas_en_uno(con_ruido):
    """Con los valores por omisión de MATLAB, 25 de sus 500 filas dan
    1,000000 exacto con dos ruidos sin relación."""
    bajas = con_ruido.frecuencias <= 50.0
    assert bajas.any()
    assert not np.any(np.isclose(con_ruido.mapa[bajas], 1.0, atol=1e-6))
    assert np.nanmax(np.abs(con_ruido.mapa[bajas])) < 0.5


def test_una_senoidal_contra_ruido_no_inventa_acoplamiento():
    """El caso donde MATLAB da 0,99993 a 40 Hz."""
    r = mapa(tono(40.0, fases_iniciales(3), semilla_ruido=30), ruido(4))
    assert abs(fila(r, 40.0)) < 0.15


def test_el_valor_no_depende_de_cuantas_muestras_entraron():
    """El sesgo del PLV: con fases al azar baja al crecer N. El PPC no."""
    a, b = ruido(5), ruido(6)
    estrecha = mapa(a, b, wd=0.05)
    ancha = mapa(a, b, wd=0.40)

    # `wd` es un piso: toca las frecuencias altas, donde la ventana que pide
    # la fórmula es más corta que él. Abajo manda la frecuencia y las dos
    # coinciden, así que la comparación va sobre el mínimo, no sobre el máximo.
    assert estrecha.ventanas_s.min() < ancha.ventanas_s.min()
    assert estrecha.n_muestras.max() < ancha.n_muestras.max(), "la N tiene que cambiar"
    assert abs(np.nanmean(estrecha.mapa) - np.nanmean(ancha.mapa)) < 0.1


# ============================================================
#   Que sí encuentra lo que hay
# ============================================================
def test_dos_senoidales_con_desfase_fijo():
    fase0 = fases_iniciales(7)
    r = mapa(tono(40.0, fase0, semilla_ruido=70),
             tono(40.0, fase0, desfase=1.0, semilla_ruido=71))
    assert fila(r, 40.0) > 0.9
    for f in (10.0, 100.0, 200.0):
        assert abs(fila(r, f)) < 0.2, f"fuga a {f} Hz"


def test_canales_identicos_dan_uno():
    a = ruido(8)
    r = mapa(a, a.copy())
    assert np.allclose(r.mapa[~np.isnan(r.mapa)], 1.0)


def test_el_mapa_situa_en_el_tiempo_un_desfase_que_cambia():
    """La primera mitad acoplada y la segunda no: tiene que notarse dónde."""
    rng = np.random.default_rng(11)
    fase0 = rng.uniform(-np.pi, np.pi, N_TR)
    mitad = N // 2
    a = np.stack([np.sin(2 * np.pi * 60 * T + p) + 0.1 * rng.normal(size=N)
                  for p in fase0], axis=1)
    b = np.empty_like(a)
    for k, p in enumerate(fase0):
        copia = np.sin(2 * np.pi * 60 * T + p + 0.8) + 0.1 * rng.normal(size=N)
        copia[mitad:] = rng.normal(size=N - mitad)       # se rompe a la mitad
        b[:, k] = copia

    r = mapa(a, b)
    i = int(np.argmin(np.abs(r.frecuencias - 60.0)))
    antes = np.nanmean(r.mapa[i][r.tiempos < DUR * 0.4])
    despues = np.nanmean(r.mapa[i][r.tiempos > DUR * 0.6])
    assert antes > 0.8 and abs(despues) < 0.2


# ============================================================
#   La geometría
# ============================================================
def test_la_forma_y_los_ejes(con_ruido):
    r = con_ruido
    assert r.mapa.shape == (N_FREQ, r.tiempos.size)
    assert r.frecuencias.size == N_FREQ
    assert r.frecuencias[0] > r.frecuencias[-1], "el eje va descendente, como MATLAB"
    assert r.frecuencias[0] == pytest.approx(BANDA[1])
    assert r.frecuencias[-1] == pytest.approx(BANDA[0])
    assert np.all(np.diff(r.tiempos) > 0)
    assert r.n_trials == N_TR


def test_ninguna_columna_queda_vacia(con_ruido):
    """MATLAB reserva una columna de más y la deja en cero: una franja negra en
    el borde derecho del mapa. Y pierde los últimos 50 ms."""
    assert not np.any(np.all(con_ruido.mapa == 0.0, axis=0))
    ultima = con_ruido.mapa[:, -1]
    assert np.any(~np.isnan(ultima)), "la última columna tiene que tener datos"


def test_la_cola_de_la_senal_se_cubre(con_ruido):
    """El último centro no puede quedar a más de una ventana mínima del final."""
    sobra = DUR - con_ruido.tiempos[-1]
    assert sobra <= con_ruido.ventana_min_s + 1.0 / FS


def test_la_ventana_de_cada_fila_sigue_la_formula(con_ruido):
    r = con_ruido
    n_ind = int(np.ceil(r.n_objetivo / r.n_trials))
    pedida = 2.0 * r.ciclos * n_ind / r.frecuencias
    esperada = np.clip(pedida, r.ventana_min_s, DUR)
    # el redondeo a un número impar de muestras mueve la ventana media muestra
    assert np.allclose(r.ventanas_s, esperada, atol=2.0 / FS)


def test_la_ventana_crece_al_bajar_la_frecuencia(con_ruido):
    """Es el punto de la decisión 10: resolución fina arriba, ancha abajo."""
    r = con_ruido
    assert np.all(np.diff(r.ventanas_s) >= 0), "frecuencias descendentes → ventanas crecientes"
    assert r.ventanas_s[0] < r.ventanas_s[-1]


def test_n_muestras_alcanza_el_objetivo_donde_hay_dato(con_ruido):
    r = con_ruido
    vivas = ~np.all(np.isnan(r.mapa), axis=1)
    assert np.all(r.n_muestras[vivas] >= r.n_objetivo)


def test_las_filas_lentas_pierden_los_bordes_y_no_el_centro():
    """El cono de influencia, que es lo que se ve con `bordes='descartar'`:
    una ventana ancha no cabe pegada al borde."""
    r = mapa(ruido(1), ruido(2), bordes="descartar")
    lenta = r.mapa[-1]      # la frecuencia más baja, la de ventana más ancha
    rapida = r.mapa[0]
    assert np.sum(np.isnan(lenta)) > np.sum(np.isnan(rapida))
    assert not np.isnan(lenta[lenta.size // 2]), "el centro siempre tiene que caber"


# ============================================================
#   El rango
# ============================================================
def test_el_ppc_vive_entre_menos_uno_y_uno(con_ruido):
    v = con_ruido.mapa[~np.isnan(con_ruido.mapa)]
    assert v.max() <= 1.0 + 1e-12
    assert v.min() >= -1.0


def test_la_cota_inferior_es_la_teorica(con_ruido):
    """`(N·PLV²−1)/(N−1)` no puede bajar de `−1/(N−1)`.

    Con la ventana recortada la N baja en los extremos, así que la cota se
    calcula **por celda**: una celda con media ventana tiene media N y puede
    bajar más que las del centro.
    """
    r = con_ruido
    with np.errstate(divide="ignore", invalid="ignore"):
        cota = -1.0 / (r.n_por_celda - 1.0)
    vivas = ~np.isnan(r.mapa)
    assert np.all(r.mapa[vivas] >= cota[vivas] - 1e-9)


# ============================================================
#   Un solo trial
# ============================================================
def test_con_un_trial_sigue_habiendo_mapa():
    """La ventana se ensancha para compensar; no es un NaN plano."""
    r = mapa(ruido(12, n_tr=1), ruido(13, n_tr=1))
    vivas = ~np.all(np.isnan(r.mapa), axis=1)
    assert vivas.sum() > r.frecuencias.size // 2
    assert r.n_trials == 1


def test_con_un_trial_las_ventanas_son_mas_anchas():
    uno = mapa(ruido(12, n_tr=1), ruido(13, n_tr=1))
    muchos = mapa(ruido(12), ruido(13))
    assert uno.ventanas_s[-1] > muchos.ventanas_s[-1]


# ============================================================
#   El eje de frecuencias
# ============================================================
def test_el_eje_logaritmico_esta_repartido_en_logaritmo():
    eje = pc.eje_frecuencias(1.0, 1000.0, n_freq=10, log=True)
    assert eje[0] > eje[-1]
    assert np.allclose(np.diff(np.log10(eje)), np.diff(np.log10(eje))[0])


def test_el_eje_lineal_es_el_de_matlab():
    eje = pc.eje_frecuencias(0.1, 500.0, log=False)
    assert eje.size == 500                      # ps_FreqSeg = round(fmax - fmin)
    assert np.allclose(np.diff(eje), np.diff(eje)[0])


def test_las_filas_por_decada_salen_del_ancho_del_wavelet():
    """σ_f/f vale 1/(2π·ciclos); media σ_f entre filas da este número."""
    assert pc.filas_por_decada(3.0) == pytest.approx(4 * np.pi * 3 * np.log(10))
    assert pc.filas_por_decada(6.0) == pytest.approx(2 * pc.filas_por_decada(3.0))


def test_mas_ciclos_piden_mas_filas():
    pocas = pc.eje_frecuencias(10.0, 100.0, ciclos=1.0)
    muchas = pc.eje_frecuencias(10.0, 100.0, ciclos=6.0)
    assert muchas.size > pocas.size


# ============================================================
#   Cancelación y validaciones
# ============================================================
class _Cancelado:
    cancelled = True

    def progress(self, *a, **k):
        pass


def test_cancelar_devuelve_none():
    assert pc.ppc_mapa(_Cancelado(), ruido(1), ruido(2), FS, FS, *BANDA) is None


def test_avisa_del_avance_y_termina_en_cien():
    pasos = []

    class Ctx:
        cancelled = False

        def progress(self, pct, txt):
            pasos.append((pct, txt))

    pc.ppc_mapa(Ctx(), ruido(1, n_tr=3), ruido(2, n_tr=3), FS, FS, *BANDA, n_freq=10)
    assert pasos and pasos[-1][0] == 100
    assert any("Trial" in t for _, t in pasos)


@pytest.mark.parametrize("kwargs,trozo", [
    (dict(wd=0.0), "ventana mínima"),
    (dict(solape=1.0), "solapamiento"),
    (dict(ciclos=0.0), "ciclos"),
    (dict(n_objetivo=1), "al menos 2"),
    (dict(fmax=10000.0), "Nyquist"),
    (dict(fmin=0.0), "mayor que cero"),
])
def test_valida_sus_parametros_en_espanol(kwargs, trozo):
    args = dict(fmin=BANDA[0], fmax=BANDA[1], n_freq=10)
    args.update(kwargs)
    with pytest.raises(ValueError, match=trozo):
        pc.ppc_mapa(None, ruido(1, n_tr=2), ruido(2, n_tr=2), FS, FS, **args)


def test_rechaza_canales_de_distinto_tamano():
    with pytest.raises(ValueError, match="misma matriz"):
        pc.ppc_mapa(None, ruido(1, n_tr=2), ruido(2, n_tr=3), FS, FS, *BANDA)


def test_avisa_cuando_ninguna_frecuencia_cabe_en_el_trial():
    corto = np.random.default_rng(0).normal(size=(200, 1))
    with pytest.raises(ValueError, match="Ninguna frecuencia de la banda"):
        pc.ppc_mapa(None, corto, corto.copy(), FS, FS, 0.2, 0.5, n_freq=5)


# ============================================================
#   El alineamiento de los dos canales
# ============================================================
class _TD:
    """Lo justo de un TrialDataset para `validar_alineacion`."""
    def __init__(self, canal, ns=100, t=4, onsets=None, fs=FS, t0=-0.1, t1=0.4):
        self.channel_name = canal
        self.trials = np.zeros((ns, t))
        self.onsets_s = list(onsets if onsets is not None else range(t))
        self.sampling_rate = fs
        self.t0, self.t1 = t0, t1


def test_dos_cortes_iguales_pasan():
    pc.validar_alineacion(_TD("CA1"), _TD("IN 7"))


@pytest.mark.parametrize("cambio,trozo", [
    (dict(ns=50), "misma forma"),
    (dict(t=3), "misma forma"),
    (dict(onsets=[9, 9, 9, 9]), "instantes distintos"),
    (dict(fs=250.0), "frecuencias de muestreo distintas"),
    (dict(t1=0.9), "ventanas de recorte"),
])
def test_los_cortes_distintos_se_rechazan_diciendo_por_que(cambio, trozo):
    with pytest.raises(ValueError, match=trozo):
        pc.validar_alineacion(_TD("CA1"), _TD("IN 7", **cambio))


def test_el_error_nombra_los_dos_canales():
    with pytest.raises(ValueError) as e:
        pc.validar_alineacion(_TD("CA1"), _TD("IN 7", ns=50))
    assert "CA1" in str(e.value) and "IN 7" in str(e.value)


# ============================================================
#   Una propiedad del PPC que conviene tener fijada
# ============================================================
def test_sin_nada_de_ruido_manda_la_fuga_espectral():
    """El PPC solo mira fase, nunca amplitud.

    Con dos tonos de 40 Hz **perfectamente limpios**, las filas de fuera de
    banda también salen altas: la fuga espectral del tono vale 3·10⁻⁴ de su
    amplitud, pero lleva la misma diferencia de fase, y al PPC la amplitud le
    da igual. No es un defecto del cálculo, es lo que significa medir fase.

    Se fija aquí para que nadie lo lea como un error al ver un mapa de prueba,
    y para dejar escrito que **basta un 1 % de ruido** para que desaparezca.
    """
    fase0 = fases_iniciales(21)
    limpio = mapa(tono(40.0, fase0, amp_ruido=0.0),
                  tono(40.0, fase0, desfase=1.0, amp_ruido=0.0))
    sucio = mapa(tono(40.0, fase0, semilla_ruido=22, amp_ruido=0.01),
                 tono(40.0, fase0, desfase=1.0, semilla_ruido=23, amp_ruido=0.01))

    assert np.nanmax(limpio.mapa[int(np.argmin(np.abs(limpio.frecuencias - 40.0)))]) > 0.99
    assert fila(limpio, 100.0) > 0.3, "sin ruido, la fuga manda fuera de banda"

    assert fila(sucio, 40.0) > 0.99, "el tono sigue ahí"
    assert abs(fila(sucio, 100.0)) < 0.2, "con 1 % de ruido la fuga desaparece"


# ============================================================
#   Fase 4 — los avisos
# ============================================================
# No son adorno: cada uno existe porque sin él alguien leería mal el mapa.
# Y ninguno abre un diálogo (nº 24 de `problemas-encontrados.md`): son texto
# que el plugin registra y, si quiere, pone bajo el gráfico.

def junto(r):
    return " || ".join(pc.avisos(r))


def test_lo_normal_no_genera_avisos_ruidosos(con_ruido):
    """Con una corrida sana no puede salir una parrafada: si avisa de todo,
    nadie lee los avisos que importan."""
    assert len(pc.avisos(con_ruido)) <= 1


def test_avisa_si_los_dos_canales_son_el_mismo():
    a = ruido(31)
    r = mapa(a, a.copy(), canal_1="CA1", canal_2="CA1")
    texto = junto(r)
    assert "el mismo" in texto and "CA1" in texto
    assert "1 en todo el mapa" in texto


def test_no_avisa_de_canales_iguales_cuando_son_distintos(con_ruido):
    assert "el mismo" not in junto(con_ruido)


def test_avisa_cuando_el_remuestreo_pedido_no_se_alcanza():
    """El problema nº 18: el factor es entero, así que pedir 300 sobre 1.000
    deja la señal en 333,3 Hz y **todo** el eje de frecuencias con ella."""
    a, b = ruido(32), ruido(33)
    r = pc.ppc_mapa(None, a, b, 1000.0, 300.0, 20.0, 120.0, n_freq=20)
    assert r.fs_pedida == 300.0
    assert r.fs_efectiva == pytest.approx(1000.0 / 3)
    texto = junto(r)
    assert "333.3" in texto and "300" in texto


def test_no_avisa_del_remuestreo_cuando_si_se_alcanza(con_ruido):
    assert con_ruido.fs_efectiva == con_ruido.fs_pedida
    assert "remuestrear" not in junto(con_ruido)


def test_avisa_de_las_frecuencias_que_no_se_pudieron_medir():
    """Las filas enteras en NaN. Es el caso que MATLAB devolvía valiendo 1."""
    rng = np.random.default_rng(34)
    uno, otro = rng.normal(size=(300, 1)), rng.normal(size=(300, 1))
    r = pc.ppc_mapa(None, uno, otro, FS, FS, 2.0, 200.0, n_freq=30)
    sin_medir = np.all(np.isnan(r.mapa), axis=1)
    assert sin_medir.any(), "este caso tiene que dejar filas sin medir"
    texto = junto(r)
    assert "no se pudieron medir" in texto
    assert "MATLAB" in texto, "conviene decir que antes salían valiendo 1"


def test_avisa_de_las_frecuencias_con_poco_respaldo():
    r = pc.ppc_mapa(None, ruido(36, n_tr=2), ruido(37, n_tr=2),
                    FS, FS, 2.0, 200.0, n_freq=30)
    flojas = r.n_muestras < r.n_objetivo
    assert flojas.any()
    texto = junto(r)
    assert "muestras independientes" in texto
    assert "más trials" in texto


def test_el_aviso_dice_que_con_pocas_muestras_el_valor_no_se_lee():
    """N=2 no es «más ruidoso»: la desviación del PPC con fases al azar es 0,7,
    o sea que cualquier número es posible. Hay que decirlo con el número."""
    r = pc.ppc_mapa(None, ruido(38, n_tr=2), ruido(39, n_tr=2),
                    FS, FS, 2.0, 200.0, n_freq=30)
    assert r.n_muestras.min() < 5
    assert "ni se puede leer" in junto(r)


def test_la_concordancia_con_un_solo_trial():
    """«los 1 que hay» no se puede mostrar a nadie."""
    r = pc.ppc_mapa(None, ruido(40, n_tr=1), ruido(41, n_tr=1),
                    FS, FS, 20.0, 200.0, n_freq=20)
    texto = junto(r)
    assert "los 1 " not in texto
    if "reparto" in texto:
        assert "el único trial" in texto


def test_avisa_del_cono_de_influencia():
    """El blanco de los bordes no es un dato que falte, y quien mire el mapa
    por primera vez lo va a leer como si lo fuera."""
    r = pc.ppc_mapa(None, ruido(42, n_tr=4), ruido(43, n_tr=4),
                    FS, FS, 3.0, 200.0, n_freq=30, bordes="descartar")
    texto = junto(r)
    assert "cono de influencia" in texto
    assert "no es un dato que falte" in texto.lower()


def test_los_avisos_estan_todos_en_espanol():
    """La regla del proyecto. Se mira que no se haya colado inglés de copiar
    y pegar en ninguna de las ramas."""
    casos = [
        pc.ppc_mapa(None, ruido(44), ruido(44), FS, FS, 20.0, 200.0, n_freq=20,
                    canal_1="CA1", canal_2="CA1"),
        pc.ppc_mapa(None, ruido(45, n_tr=1), ruido(46, n_tr=1), FS, FS, 3.0, 200.0,
                    n_freq=20),
        pc.ppc_mapa(None, ruido(47), ruido(48), 1000.0, 300.0, 20.0, 120.0, n_freq=20),
    ]
    prohibidas = ("channel", "warning", "trials are", "samples", "window of",
                  "frequency", "the ")
    for r in casos:
        for a in pc.avisos(r):
            bajo = a.lower()
            for p in prohibidas:
                assert p not in bajo, f"se coló inglés en: {a}"


def test_los_avisos_no_lanzan_con_un_resultado_cualquiera(con_ruido):
    """Es texto para la interfaz: no puede ser el que rompa el dibujo."""
    assert isinstance(pc.avisos(con_ruido), list)
    assert all(isinstance(a, str) and a for a in pc.avisos(con_ruido))


# ============================================================
#   Auditoría del 25 de octubre: lo que las pruebas no cogían
# ============================================================
def test_un_canal_plano_no_devuelve_acoplamiento_perfecto():
    """El falso positivo peor de todos, y el más fácil de enseñar como
    hallazgo: dos canales constantes daban **PPC = 1,0000 en todo el mapa**.

    El PPC normaliza la amplitud, así que da igual que el coeficiente valga 4 o
    10⁻²⁵; con una señal constante es polvo numérico, pero repetible, y al
    normalizarlo sale una fase perfecta. Ahora se rechaza a la entrada.
    """
    plano = np.ones((N, 4))
    with pytest.raises(ValueError, match="sin ninguna variación"):
        pc.ppc_mapa(None, plano, plano * 2.0, FS, FS, *BANDA, n_freq=10)


def test_el_error_del_canal_plano_dice_cual_es_y_que_trials():
    vivo = np.random.default_rng(60).normal(size=(N, 3))
    malo = vivo.copy()
    malo[:, 1] = 7.0
    with pytest.raises(ValueError) as e:
        pc.ppc_mapa(None, vivo, malo, FS, FS, *BANDA, n_freq=10,
                    canal_1="CA1", canal_2="IN 7")
    texto = str(e.value)
    assert "IN 7" in texto, "tiene que nombrar el canal culpable"
    assert "2" in texto, "y qué trial, contando desde 1"


def test_un_canal_vivo_no_se_rechaza(con_ruido):
    assert con_ruido.mapa.size > 0


def test_no_corrige_en_silencio_un_n_freq_imposible():
    """Subir 1 a 2 sin decirlo es la misma clase de cosa que hace MATLAB al
    subir fmin de 0 a 0,1, y es lo que este puerto decidió no replicar."""
    with pytest.raises(ValueError, match="al menos 2 frecuencias"):
        pc.ppc_mapa(None, ruido(61, n_tr=2), ruido(62, n_tr=2), FS, FS, *BANDA, n_freq=1)


def test_una_banda_estrecha_sin_n_freq_si_se_ajusta():
    """Sin `n_freq` el número lo decide el cálculo, y ahí sí puede subirlo a 2:
    nadie pidió otra cosa."""
    eje = pc.eje_frecuencias(100.0, 101.0, log=False)
    assert eje.size == 2


def test_el_error_de_nyquist_no_imprime_el_mismo_numero_dos_veces():
    """Con fmax = 250,0001 y Nyquist 250, el `:g` de seis cifras imprimía
    «250 Hz pasa del Nyquist (250 Hz)», que no se entiende."""
    with pytest.raises(ValueError) as e:
        pc.ppc_mapa(None, ruido(63, n_tr=2), ruido(64, n_tr=2),
                    FS, FS, 20.0, FS / 2 + 1e-4, n_freq=10)
    assert "250.0001" in str(e.value)


def test_fmax_justo_en_el_nyquist_se_acepta():
    r = pc.ppc_mapa(None, ruido(65, n_tr=2), ruido(66, n_tr=2),
                    FS, FS, 20.0, FS / 2, n_freq=10)
    assert r.frecuencias[0] == pytest.approx(FS / 2)


def test_el_orden_de_los_trials_no_cambia_el_resultado():
    """El acumulador es una suma, así que tiene que conmutar. Si dejara de
    conmutar sería señal de que se cuela un estado entre trials."""
    a, b = ruido(67, n_tr=4), ruido(68, n_tr=4)
    orden = [3, 1, 0, 2]
    r1 = mapa(a, b)
    r2 = mapa(a[:, orden], b[:, orden])
    assert np.nanmax(np.abs(r1.mapa - r2.mapa)) < 1e-12


def test_trocear_por_tandas_no_cambia_el_resultado():
    """`FILAS_POR_TANDA` es una decisión de memoria, no de cálculo. Medido: 7
    tandas cuestan un 4 % más que una sola, porque cada llamada repite la FFT
    de la señal; el resultado tiene que ser el mismo."""
    a, b = ruido(69, n_tr=3), ruido(70, n_tr=3)
    original = pc.FILAS_POR_TANDA
    try:
        pc.FILAS_POR_TANDA = 4
        pocas = mapa(a, b)
        pc.FILAS_POR_TANDA = 1000
        todas = mapa(a, b)
    finally:
        pc.FILAS_POR_TANDA = original
    assert np.nanmax(np.abs(pocas.mapa - todas.mapa)) < 1e-12


def test_el_sesgo_residual_es_pequeno_y_va_hacia_abajo():
    """Lo único aproximado del cálculo, y por eso se fija aquí.

    `n_ind` supone que 2σ bastan para que dos puntos sean independientes.
    Medido, la N efectiva real es 2,3 donde contamos 2, así que la corrección
    se pasa y el mapa queda sesgado **hacia abajo**: −0,009 con N=20.

    Esta prueba no pide que el sesgo sea cero —no lo es—, sino que siga siendo
    chico y siga yendo hacia abajo. Un cambio que lo volviera **positivo**
    haría que la medida empezara a inventar acoplamiento, que es justo el
    defecto de MATLAB que vinimos a arreglar.
    """
    medias = []
    for k in range(12):
        rng = np.random.default_rng(2000 + k)
        r = pc.ppc_mapa(None, rng.normal(size=(N, N_TR)), rng.normal(size=(N, N_TR)),
                        FS, FS, 20.0, 200.0, n_freq=15)
        medias.append(np.nanmean(r.mapa))
    sesgo = float(np.mean(medias))

    assert abs(sesgo) < 0.03, f"el sesgo creció a {sesgo:+.4f}"
    assert sesgo < 0.01, (
        f"el sesgo se volvió positivo ({sesgo:+.4f}): la medida estaría "
        f"inventando acoplamiento donde no hay")


# ============================================================
#   Fase 5 — el reparto de los trials entre hilos
# ============================================================
# Gana de 1,8x a 2,7x según los trials que haya, medido. Lo que estas pruebas
# cuidan no es la velocidad —esa se mide aparte— sino que repartir no cambie
# ni el resultado ni el comportamiento.

def test_el_reparto_da_identico_bit_a_bit():
    """Cada trial es independiente y `map_ordenado` devuelve en orden, así que
    la suma no puede depender de quién acabe primero. Si esto empezara a dar
    diferencias de redondeo, sería señal de que el acumulado se comparte."""
    a, b = ruido(80, n_tr=6), ruido(81, n_tr=6)
    serie = mapa(a, b, hilos=1)
    paralelo = mapa(a, b, hilos=4)

    uno = np.nan_to_num(serie.mapa, nan=-9.0)
    cuatro = np.nan_to_num(paralelo.mapa, nan=-9.0)
    assert np.array_equal(uno, cuatro)


@pytest.mark.parametrize("hilos", [1, 2, 3, 4, 8])
def test_cualquier_numero_de_hilos_da_lo_mismo(hilos):
    a, b = ruido(82, n_tr=5), ruido(83, n_tr=5)
    esperado = np.nan_to_num(mapa(a, b, hilos=1).mapa, nan=-9.0)
    obtenido = np.nan_to_num(mapa(a, b, hilos=hilos).mapa, nan=-9.0)
    assert np.array_equal(esperado, obtenido)


def test_mas_hilos_que_trials_no_rompe():
    a, b = ruido(84, n_tr=2), ruido(85, n_tr=2)
    assert mapa(a, b, hilos=16) is not None


def test_un_hilo_no_pasa_por_el_pool():
    """`hilos=1` tiene que correr en el hilo que llama. Es lo que permite usar
    este `compute` desde una prueba o un script sin levantar nada."""
    import threading
    visto = []
    original = pc.gabor_en

    def espia(*a, **k):
        visto.append(threading.current_thread().name)
        return original(*a, **k)

    pc.gabor_en = espia
    try:
        mapa(ruido(86, n_tr=3), ruido(87, n_tr=3), hilos=1)
    finally:
        pc.gabor_en = original
    assert visto and set(visto) == {threading.current_thread().name}


def test_con_hilos_el_calculo_sale_del_hilo_que_llama():
    import threading
    visto = set()
    original = pc.gabor_en

    def espia(*a, **k):
        visto.add(threading.current_thread().name)
        return original(*a, **k)

    pc.gabor_en = espia
    try:
        mapa(ruido(88, n_tr=6), ruido(89, n_tr=6), hilos=4)
    finally:
        pc.gabor_en = original
    assert len(visto) > 1, "con cuatro hilos el trabajo tiene que repartirse"


def test_cancelar_a_media_corrida_con_hilos_devuelve_none():
    """No puede devolver un mapa a medio sumar: o está completo o es None."""
    class CtxQueCancela:
        def __init__(self):
            self.cancelled = False
            self.vueltas = 0

        def progress(self, pct, txt):
            self.vueltas += 1
            if self.vueltas >= 2:
                self.cancelled = True

    ctx = CtxQueCancela()
    salida = pc.ppc_mapa(ctx, ruido(90, n_tr=8), ruido(91, n_tr=8),
                         FS, FS, *BANDA, n_freq=N_FREQ, hilos=4)
    assert salida is None


def test_el_avance_sigue_diciendo_trial_n_de_n_con_hilos():
    pasos = []

    class Ctx:
        cancelled = False

        def progress(self, pct, txt):
            pasos.append((pct, txt))

    pc.ppc_mapa(Ctx(), ruido(92, n_tr=6), ruido(93, n_tr=6),
                FS, FS, *BANDA, n_freq=10, hilos=4)
    assert pasos, "sin avance la espera es ciega"
    assert any("Trial" in t for _, t in pasos)
    assert max(p for p, _ in pasos) == 100


def test_el_valor_por_omision_de_hilos_es_el_del_proyecto():
    """No se inventa un número: sale de `core/utils/parallel.py`, que ya acota
    por núcleos y por memoria."""
    from core.utils.parallel import MAX_HILOS
    assert pc.HILOS == MAX_HILOS


def test_el_defecto_de_matlab_no_vuelve_con_fmin_muy_bajo():
    """La prueba central del puerto, con los valores por omisión del panel.

    A 0,1 Hz con trials de 3 s la ventana contiene **0,3 ciclos**: dentro de
    ella el wavelet colapsa al bin de continua y la diferencia de fase sale
    constante, que es exactamente el mecanismo por el que `f_phase_coherence`
    devuelve 1,000000 con los datos que sean.

    Aquí no vuelve, y el motivo importa: esa constante cambia al azar de trial
    en trial, así que el promedio **entre trials** la deshace. La independencia
    viene de los trials, no de las muestras de dentro de la ventana; por eso
    `N = n_ind × n_trials` es la cantidad correcta y por eso MATLAB fallaba
    contando 101 muestras de tiempo.
    """
    fs, n_tr = 2000.0, 20
    n = int(fs * 3.0)
    rng = np.random.default_rng(3)
    r = pc.ppc_mapa(None, rng.normal(size=(n, n_tr)), rng.normal(size=(n, n_tr)),
                    fs, fs, 0.1, 500.0)

    i = int(np.argmin(np.abs(r.frecuencias - 0.1)))
    assert r.ventanas_s[i] * r.frecuencias[i] < 1.0, "la ventana no llega a un ciclo"
    assert abs(np.nanmean(r.mapa[i])) < 0.15, "ahí es donde MATLAB daba 1,000000"

    # y ninguna fila de todo el mapa se despega
    por_fila = np.nanmean(r.mapa, axis=1)
    assert np.nanmax(np.abs(por_fila)) < 0.25
    assert not np.any(np.isclose(r.mapa[~np.isnan(r.mapa)], 1.0, atol=1e-6))


def test_dos_senoidales_sin_relacion_se_quedan_en_el_suelo():
    """Tonos puros a frecuencias distintas y fases al azar: no hay nada que
    medir en ninguna fila, y además no hay ruido que ayude."""
    fs, n_tr = 2000.0, 20
    n = int(fs * 3.0)
    t = np.arange(n) / fs
    rng = np.random.default_rng(4)
    u = np.stack([np.sin(2 * np.pi * 77 * t + p) for p in rng.uniform(0, 7, n_tr)], 1)
    v = np.stack([np.sin(2 * np.pi * 123 * t + p) for p in rng.uniform(0, 7, n_tr)], 1)

    r = pc.ppc_mapa(None, u, v, fs, fs, 0.1, 500.0)
    bajas = r.frecuencias <= 20.0
    assert np.nanmax(np.abs(np.nanmean(r.mapa[bajas], axis=1))) < 0.1


# ============================================================
#   Los dos modos de borde
# ============================================================
# `descartar` deja el cono en blanco; `recortar` corta la ventana contra el
# borde y llena el mapa. Lo segundo es legítimo —el enrollado revuelve la fase
# de los dos canales por separado, así que su diferencia sigue siendo
# aleatoria— pero solo si la N de esas celdas se cuenta de verdad.

def test_recortar_llena_el_mapa():
    a, b = ruido(100), ruido(101)
    lleno = mapa(a, b, bordes="recortar")
    cono = mapa(a, b, bordes="descartar")
    assert np.mean(np.isnan(cono.mapa)) > 0.05
    assert np.mean(np.isnan(lleno.mapa)) == 0.0


def test_recortar_no_inventa_acoplamiento():
    """Lo que no puede pasar: que al llenar el mapa aparezca sincronía donde
    solo hay ruido. Es el defecto de MATLAB por otra puerta."""
    a, b = ruido(102), ruido(103)
    lleno = mapa(a, b, bordes="recortar")
    cono = mapa(a, b, bordes="descartar")

    assert abs(np.nanmean(lleno.mapa)) < 0.05
    # y los extremos no se despegan del centro
    borde = lleno.mapa[:, :4]
    centro = lleno.mapa[:, lleno.tiempos.size // 2 - 2:lleno.tiempos.size // 2 + 2]
    assert abs(np.nanmean(borde) - np.nanmean(centro)) < 0.1
    assert abs(np.nanmean(lleno.mapa) - np.nanmean(cono.mapa)) < 0.05


def test_la_n_por_celda_baja_en_los_extremos():
    """Es lo que hace honesto al modo lleno. Sin esto, una celda de media
    ventana se declararía tan respaldada como una entera: exactamente la N
    inflada que este puerto le corrige a MATLAB."""
    r = mapa(ruido(104), ruido(105), bordes="recortar")
    nominal = r.n_muestras[:, None]

    assert np.nanmin(r.n_por_celda) < np.nanmax(r.n_por_celda)
    # el centro conserva la ventana entera
    medio = r.tiempos.size // 2
    assert np.allclose(r.n_por_celda[:, medio], r.n_muestras)
    # y la primera columna no puede declarar mas de lo que promedio
    assert np.all(r.n_por_celda[:, 0] <= nominal[:, 0] + 1e-9)


def test_con_descartar_la_n_por_celda_es_la_de_la_fila():
    """Si la ventana cabe entera, todas las celdas de la fila valen lo mismo."""
    r = mapa(ruido(106), ruido(107), bordes="descartar")
    for i in range(r.frecuencias.size):
        vivas = ~np.isnan(r.mapa[i])
        if vivas.any():
            assert np.allclose(r.n_por_celda[i, vivas], r.n_muestras[i])


def test_recortar_avisa_de_que_los_extremos_van_mas_flojos():
    r = mapa(ruido(108), ruido(109), bordes="recortar")
    texto = " || ".join(pc.avisos(r))
    assert "recorta" in texto
    assert "n_por_celda" in texto
    assert "cono de influencia" not in texto, "ese aviso es del otro modo"


def test_recortar_recupera_un_acoplamiento_real_del_borde():
    """Lo que el cono dejaba en blanco y la reflexion borraba."""
    fase0 = fases_iniciales(110)
    r = mapa(tono(40.0, fase0, semilla_ruido=111),
             tono(40.0, fase0, desfase=1.0, semilla_ruido=112),
             bordes="recortar")
    i = int(np.argmin(np.abs(r.frecuencias - 40.0)))
    assert r.mapa[i, 0] > 0.8, "el acoplamiento esta ahi desde el primer instante"
    assert r.mapa[i, -1] > 0.8


def test_el_centro_del_mapa_no_depende_del_modo():
    """Las celdas cuya ventana cabe entera tienen que dar lo mismo en los dos.

    Los dos modos no comparten el eje de tiempo —`descartar` quita las columnas
    que no le sirven a ninguna fila— así que se emparejan por instante.
    """
    a, b = ruido(113), ruido(114)
    cono = mapa(a, b, bordes="descartar")
    lleno = mapa(a, b, bordes="recortar")

    comunes = 0
    for k, t in enumerate(cono.tiempos):
        j = int(np.argmin(np.abs(lleno.tiempos - t)))
        assert abs(lleno.tiempos[j] - t) < 1e-9, "los instantes tienen que coincidir"
        vivas = ~np.isnan(cono.mapa[:, k])
        if vivas.any():
            assert np.allclose(cono.mapa[vivas, k], lleno.mapa[vivas, j])
            comunes += int(vivas.sum())
    assert comunes > 100, "se esperaban muchas celdas en común"


def test_un_modo_de_bordes_inventado_se_rechaza():
    with pytest.raises(ValueError, match="recortar"):
        mapa(ruido(115, n_tr=2), ruido(116, n_tr=2), bordes="rellenar")

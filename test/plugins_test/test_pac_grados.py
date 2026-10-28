"""El eje de fase de PAC, dibujado en grados de 0 a 360.

El cálculo sigue en radianes; esto comprueba solo la conversión del dibujo y,
sobre todo, que **rotar los bins no mueve ningún dato**: cada valor tiene que
seguir pegado a su fase, y la lectura que da la brújula tiene que coincidir con
la barra más alta del histograma. Antes de este cambio la brújula decía 280,6°
y el histograma −79,4°, que son el mismo ángulo escrito de dos formas.
"""
import numpy as np
import pytest

from plugins.analysis.time_frequency.pac import compute as cp
from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin

grados_de = Pac_plugin._fase_en_grados


# ============================================================
#   El eje
# ============================================================
def test_el_eje_queda_entre_0_y_360_y_en_orden():
    (g,) = grados_de(cp.centros_bins())
    assert g.size == cp.NBINS
    assert g[0] == pytest.approx(0.0)
    assert 0.0 <= g.min() and g.max() < 360.0
    assert np.all(np.diff(g) > 0), "el eje tiene que ir creciendo, sin saltos"


def test_el_primer_bin_es_un_cero_clavado():
    """`% 360` sobre −π deja 2,5e−14 en vez de 0. En la pantalla da igual; en el
    CSV se lee, así que se redondea."""
    (g,) = grados_de(cp.centros_bins())
    assert g[0] == 0.0


def test_el_paso_es_el_mismo_que_en_radianes():
    fases = cp.centros_bins()
    (g,) = grados_de(fases)
    paso_rad = np.rad2deg(np.diff(fases)[0])
    assert np.allclose(np.diff(g), paso_rad)


def test_no_se_pierde_ni_se_repite_ninguna_fase():
    fases = cp.centros_bins()
    (g,) = grados_de(fases)
    esperado = np.sort(np.rad2deg(fases) % 360.0)
    assert np.allclose(np.sort(g), esperado)
    assert np.unique(g).size == g.size


# ============================================================
#   Los datos viajan con su fase
# ============================================================
def test_cada_valor_sigue_en_su_fase():
    fases = cp.centros_bins()
    valores = np.arange(fases.size, dtype=np.float64)   # etiqueta única por bin
    g, v = grados_de(fases, valores)

    for grado, valor in zip(g, v):
        original = int(valor)
        assert np.rad2deg(fases[original]) % 360.0 == pytest.approx(grado)


def test_el_pico_del_histograma_no_se_mueve():
    fases = cp.centros_bins()
    hist = np.zeros(fases.size)
    hist[17] = 1.0
    g, h = grados_de(fases, hist)

    assert g[int(np.argmax(h))] == pytest.approx(np.rad2deg(fases[17]) % 360.0)


def test_el_mapa_rota_por_columnas_y_no_por_filas():
    fases = cp.centros_bins()
    mapa = np.arange(5 * fases.size, dtype=np.float64).reshape(5, fases.size)
    g, m = grados_de(fases, mapa)

    assert m.shape == mapa.shape
    # cada fila conserva sus propios valores: rotar no mezcla frecuencias
    for antes, despues in zip(mapa, m):
        assert np.array_equal(np.sort(antes), np.sort(despues))
    # y las filas rotan todas igual
    corte = int(np.argmin(np.rad2deg(fases) % 360.0))
    assert np.array_equal(m, np.roll(mapa, -corte, axis=-1))


def test_varias_matrices_a_la_vez_rotan_igual():
    fases = cp.centros_bins()
    a = np.random.default_rng(0).normal(size=fases.size)
    b = np.random.default_rng(1).normal(size=(3, fases.size))
    g, ra, rb = grados_de(fases, a, b)

    corte = int(np.argmin(np.rad2deg(fases) % 360.0))
    assert np.array_equal(ra, np.roll(a, -corte))
    assert np.array_equal(rb, np.roll(b, -corte, axis=-1))


# ============================================================
#   La brújula y el histograma dicen lo mismo
# ============================================================
def test_la_brujula_y_el_histograma_coinciden():
    """Un acoplamiento metido a mano en un bin: la fase del vector medio y la
    barra más alta tienen que caer en el mismo grado."""
    fases = cp.centros_bins()
    hist = np.zeros(fases.size)
    hist[72] = 1.0                      # un solo bin con energía

    vector = cp.vector_medio(hist)
    de_la_brujula = np.rad2deg(np.angle(vector)) % 360.0

    g, h = grados_de(fases, hist)
    del_histograma = g[int(np.argmax(h))]

    assert del_histograma == pytest.approx(de_la_brujula, abs=1e-9)


def test_con_datos_de_verdad_la_brujula_cae_sobre_el_maximo():
    """Lo mismo pero con una señal acoplada: el pico del histograma tiene que
    quedar a menos de un bin del ángulo que marca la brújula."""
    fs = 1000.0
    t = np.arange(int(fs * 4)) / fs
    lento = np.sin(2 * np.pi * 6.0 * t)
    sig = lento + 0.4 * ((1 + lento) / 2) * np.sin(2 * np.pi * 80 * t)

    r = cp.pac_un_trial(None, sig, fs, fs, 4, 8, 60, 100)
    fases = r.fases
    paso = np.rad2deg(np.diff(fases)[0])

    de_la_brujula = np.rad2deg(np.angle(r.vector)) % 360.0
    g, h = grados_de(fases, np.nan_to_num(r.histograma))
    del_histograma = g[int(np.argmax(h))]

    distancia = abs((del_histograma - de_la_brujula + 180.0) % 360.0 - 180.0)
    assert distancia <= paso, (
        f"la brújula dice {de_la_brujula:.1f}° y el histograma {del_histograma:.1f}°")


# ============================================================
#   La casilla de unidades
# ============================================================
# Marcada: grados de 0 a 360. Sin marcar: radianes de −π a π, que es lo que
# dibuja el `bar(index_pi, ...)` del MATLAB. Lo que no puede pasar es que
# queden mezcladas, que era el problema original: la brújula en 280,6° y el
# histograma en −79,4°, el mismo ángulo escrito de dos formas.

class _Casilla:
    def __init__(self, marcada=True):
        self._v = marcada

    def isChecked(self):
        return self._v

    def setChecked(self, v):
        self._v = bool(v)


class _UiMinima:
    def __init__(self, marcada=True):
        self.degreesCheckBox = _Casilla(marcada)


def plugin_con_casilla(marcada):
    p = object.__new__(Pac_plugin)
    p.ui = _UiMinima(marcada)
    return p


def test_marcada_da_grados_y_sin_marcar_radianes():
    fases = cp.centros_bins()
    grados = plugin_con_casilla(True)._eje_de_fase(fases)[0]
    radianes = plugin_con_casilla(False)._eje_de_fase(fases)[0]

    assert grados[0] == 0.0 and grados.max() < 360.0
    assert np.allclose(radianes, fases), "en radianes se devuelve tal cual"
    assert radianes.min() < 0, "de −π a π, como MATLAB"


def test_sin_marcar_no_rota_los_datos():
    """En grados hay que rotar para que el eje empiece en 0. En radianes el eje
    ya va en orden de −π a π, así que rotar sería alejarse de MATLAB sin ganar
    nada."""
    fases = cp.centros_bins()
    hist = np.arange(fases.size, dtype=np.float64)
    eje, valores = plugin_con_casilla(False)._eje_de_fase(fases, hist)
    assert np.array_equal(valores, hist)
    assert np.array_equal(eje, fases)


def test_la_unidad_del_rotulo_sigue_a_la_casilla():
    assert plugin_con_casilla(True)._unidad_de_fase() == "°"
    assert plugin_con_casilla(False)._unidad_de_fase() == "rad"


def test_el_vector_medio_se_escribe_en_la_unidad_elegida():
    v = np.exp(1j * np.deg2rad(280.6))
    assert "280.6°" in plugin_con_casilla(True)._fase_legible(v)
    texto = plugin_con_casilla(False)._fase_legible(v)
    assert "rad" in texto and texto.startswith("4.89")


def test_el_vector_medio_nunca_sale_negativo():
    """Era el problema de partida: la brújula decía 280,6° y el histograma
    −79,4°. En las dos unidades el ángulo va de 0 a una vuelta entera."""
    for ang in (-3.0, -0.5, 0.5, 3.0):
        v = np.exp(1j * ang)
        assert not plugin_con_casilla(True)._fase_legible(v).startswith("-")
        assert not plugin_con_casilla(False)._fase_legible(v).startswith("-")


def test_los_rotulos_de_la_brujula_cambian_de_unidad():
    from plugins.analysis.time_frequency.pac.pac_plugin import etiquetas_del_circulo

    grados = etiquetas_del_circulo(True)
    radianes = etiquetas_del_circulo(False)
    assert len(grados) == len(radianes) == 12
    assert grados[:3] == ["0", "30", "60"]
    assert radianes[:3] == ["0", "π/6", "π/3"]
    assert radianes[6] == "π", "media vuelta tiene que ser π"


def test_el_titulo_de_la_brujula_sigue_a_la_casilla():
    from plugins.analysis.time_frequency.pac.pac_plugin import titulo_de

    v = np.exp(1j * np.deg2rad(90.0))
    assert "90.0°" in titulo_de(v, en_grados=True)
    assert "1.571 rad" in titulo_de(v, en_grados=False)


def test_en_grados_la_brujula_y_el_histograma_siguen_coincidiendo():
    """La comprobación de siempre, pero ahora con la casilla de por medio."""
    fases = cp.centros_bins()
    hist = np.zeros(fases.size)
    hist[72] = 1.0
    p = plugin_con_casilla(True)

    eje, h = p._eje_de_fase(fases, hist)
    del_histograma = eje[int(np.argmax(h))]
    de_la_brujula = float(p._fase_legible(cp.vector_medio(hist)).rstrip("°"))
    assert del_histograma == pytest.approx(de_la_brujula, abs=0.05)


def test_sin_interfaz_se_asume_grados():
    """`_en_grados` se consulta desde sitios que pueden correr sin interfaz
    montada —una prueba, un script—, y ahí no puede reventar."""
    p = object.__new__(Pac_plugin)
    p.ui = None
    assert p._en_grados() is True
    p.ui = object()          # una interfaz sin la casilla
    assert p._en_grados() is True

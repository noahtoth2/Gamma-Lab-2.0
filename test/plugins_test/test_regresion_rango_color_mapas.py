"""El rango de color (R33) en Wavelet, Wavelet Average, PAC y PPC.

Lo que se revisó del rango de Wavelet y Wavelet Average, y se corrigió para todos:

1. El rango automático se redondeaba a dos decimales. Con un registro en voltios
   (un escalograma de 1e-10 a 1,5e-4) quedaba en (0,0, 0,0) y el mapa salía de
   un solo color.
2. Los cuadros Min y Max tenían 4 decimales fijos: un rango de 1e-5 se veía como
   0,0000 y no se podía escribir.
3. Cambiar el rango rehacía el gráfico entero y se perdía el zoom.
4. Un máximo que no superaba al mínimo se ignoraba sin avisar.

PAC y PPC no tenían rango de color. Ahora tienen el mismo control. Sin él, PAC
usa el mínimo y el máximo del mapa (el `[]` de f_Phase_PAC) y PPC usa 0-0,5 (el
`[0 0.5]` de f_phase_coherence), como antes.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
import vtk
from PyQt5.QtWidgets import QApplication, QWidget

from core.utils.rango_color import (agregar_rango_color, leer_rango, limites_color,
                                    mostrar_rango_automatico, restaurar_rango)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _vista():
    vista = vtk.vtkContextView()
    vista.GetRenderWindow().SetOffScreenRendering(1)
    vista.GetRenderWindow().SetSize(700, 400)
    return vista


def _rango_lut(chart):
    return tuple(round(v, 9) for v in chart.emf_color.GetRange())


# ============================================================
#   El rango automático y los cuadros
# ============================================================
def test_un_registro_en_voltios_no_queda_en_un_solo_color():
    Z = np.linspace(2.7e-10, 1.49e-4, 1000).reshape(10, 100)
    lo, hi = limites_color(Z)
    assert (lo, hi) == (float(Z.min()), float(Z.max())), "antes daba (0.0, 0.0)"


def test_el_maximo_automatico_no_se_recorta():
    """Redondear 0,0749 daba 0,07: todo lo de arriba salía del mismo color."""
    Z = np.array([[0.0, 0.0749]])
    assert limites_color(Z) == (0.0, 0.0749)


def test_casos_borde_del_rango_automatico():
    assert limites_color(np.full((3, 3), np.nan)) == (0.0, 1.0)
    lo, hi = limites_color(np.full((3, 3), 2.0))
    assert lo < 2.0 < hi, "un mapa plano igual tiene una escala con largo"
    con_nan = np.array([[np.nan, 1.0], [3.0, np.nan]])
    assert limites_color(con_nan) == (1.0, 3.0), "los NaN (celdas sin medida) no cuentan"


def test_el_rango_fijo_de_un_plugin_y_el_manual():
    Z = np.array([[0.0, 0.9]])
    assert limites_color(Z, por_defecto=(0.0, 0.5)) == (0.0, 0.5)
    assert limites_color(Z, True, 0.1, 0.3, por_defecto=(0.0, 0.5)) == (0.1, 0.3)
    assert limites_color(Z, True, 0.3, 0.3, por_defecto=(0.0, 0.5)) == (0.0, 0.5), "inválido: el fijo"


def _ui_con_rango():
    w = QWidget()
    from PyQt5.QtWidgets import QVBoxLayout
    ui = SimpleNamespace()
    agregar_rango_color(ui, w, QVBoxLayout(w))
    ui._w = w
    return ui


def test_los_cuadros_muestran_rangos_chicos(app):
    ui = _ui_con_rango()
    mostrar_rango_automatico(ui, 2.7e-10, 1.49e-4)
    assert ui.colorMaxSpinBox.value() == pytest.approx(1.49e-4, rel=1e-3), "antes se veía 0,0000"
    ui.colorRangeCheckBox.setChecked(True)
    ui.colorMinSpinBox.setValue(5e-5)
    assert leer_rango(ui)[1] == pytest.approx(5e-5), "y se puede escribir a mano"


def test_restaurar_un_rango_chico_no_lo_pierde(app):
    ui = _ui_con_rango()
    restaurar_rango(ui, {"color_manual": True, "color_min": 1e-6, "color_max": 3e-5})
    assert leer_rango(ui) == (True, pytest.approx(1e-6), pytest.approx(3e-5))


# ============================================================
#   PPC
# ============================================================
def _ppc(app):
    from core.plugins.meta import PluginMeta
    from plugins.analysis.time_frequency.ppc.ppc_plugin import Ppc_plugin
    from plugins.analysis.time_frequency.ppc.ppc_plugin_ui import Ui_Ppc
    p = Ppc_plugin(PluginMeta(id="ppc", name="PPC", category="Analysis", subcategory="Time-Frequency",
                              version="1", icon="x.png", logic_class="Ppc_plugin"))
    p.widget = QWidget()
    p.ui = Ui_Ppc()
    p.ui.setupUi(p.widget)
    p.alerts = MagicMock()
    p._context_view = _vista()
    return p


def _resultado_ppc():
    rng = np.random.default_rng(0)
    frec = np.geomspace(2, 100, 40)
    mapa = rng.uniform(0.0, 0.9, size=(40, 60))
    mapa[:3, :5] = np.nan
    return SimpleNamespace(mapa=mapa, frecuencias=frec, tiempos=np.linspace(0, 3, 60))


def test_ppc_sin_rango_manual_usa_0_a_05_como_matlab(app):
    p = _ppc(app)
    p.render_resultado(_resultado_ppc())
    assert _rango_lut(p._chart) == (0.0, 0.5)
    assert (p.ui.colorMinSpinBox.value(), p.ui.colorMaxSpinBox.value()) == (0.0, 0.5)


def test_ppc_con_rango_manual_recolorea_sin_perder_el_zoom(app):
    p = _ppc(app)
    p.render_resultado(_resultado_ppc())
    chart = p._chart
    eje = chart.GetAxis(vtk.vtkAxis.BOTTOM)
    eje.SetRange(1.0, 1.5)                                   # zoom
    p.ui.colorRangeCheckBox.setChecked(True)
    p.ui.colorMinSpinBox.setValue(0.2)
    p.ui.colorMaxSpinBox.setValue(0.8)
    p._redibujar_color()
    assert p._chart is chart, "el mismo gráfico: no se rehízo"
    assert (eje.GetMinimum(), eje.GetMaximum()) == (1.0, 1.5), "el zoom sigue"
    assert _rango_lut(chart) == (0.2, 0.8)


def test_ppc_avisa_un_rango_invalido_y_guarda_el_rango_en_el_proyecto(app):
    p = _ppc(app)
    p.render_resultado(_resultado_ppc())
    p.ui.colorRangeCheckBox.setChecked(True)
    p.ui.colorMinSpinBox.setValue(0.6)
    p.ui.colorMaxSpinBox.setValue(0.4)
    p._redibujar_color()
    p.alerts.warning.assert_called()
    assert _rango_lut(p._chart) == (0.0, 0.5)
    params = p.get_analysis_params()
    assert (params["color_manual"], params["color_min"], params["color_max"]) == (True, 0.6, 0.4)


# ============================================================
#   PAC
# ============================================================
def _pac(app):
    from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin
    from plugins.analysis.time_frequency.pac.pac_plugin_ui import Ui_Pac
    p = object.__new__(Pac_plugin)
    p.widget = QWidget()
    p.ui = Ui_Pac()
    p.ui.setupUi(p.widget)
    p.alerts = MagicMock()
    p._context_view = _vista()
    p._mapas = []
    return p


def _mapa_pac(p):
    from plugins.analysis.time_frequency.pac import compute as cp
    mapa = np.random.default_rng(1).normal(size=(80, cp.NBINS))
    r = SimpleNamespace(fases=cp.centros_bins(), mapa=mapa, frecuencias=np.linspace(500, 25, 80))
    chart = p._grafico_mapa(r, "PAC")
    p._context_view.GetScene().AddItem(chart)
    p._context_view.GetRenderWindow().Render()
    return chart, mapa


def test_pac_sin_rango_manual_usa_el_minimo_y_maximo_del_mapa(app):
    p = _pac(app)
    chart, mapa = _mapa_pac(p)
    # el mapa se dibuja en float32: se compara con esa precisión
    assert _rango_lut(chart) == pytest.approx((mapa.min(), mapa.max()), rel=1e-6)
    assert p.ui.colorMaxSpinBox.value() == pytest.approx(mapa.max(), abs=1e-4)


def test_pac_con_rango_manual_recolorea_sin_perder_el_zoom(app):
    p = _pac(app)
    chart, _ = _mapa_pac(p)
    eje = chart.GetAxis(vtk.vtkAxis.BOTTOM)
    eje.SetRange(120.0, 240.0)
    p.ui.colorRangeCheckBox.setChecked(True)
    p.ui.colorMinSpinBox.setValue(-2.0)
    p.ui.colorMaxSpinBox.setValue(2.0)
    p._redibujar_color()
    assert (eje.GetMinimum(), eje.GetMaximum()) == (120.0, 240.0)
    assert _rango_lut(chart) == (-2.0, 2.0)


def test_pac_guarda_y_restaura_el_rango(app):
    from core.utils.rango_color import guardar_rango
    p = _pac(app)
    p.ui.colorRangeCheckBox.setChecked(True)
    p.ui.colorMinSpinBox.setValue(-1.5)
    p.ui.colorMaxSpinBox.setValue(2.5)
    guardado = guardar_rango(p.ui)
    q = _pac(app)
    restaurar_rango(q.ui, guardado)
    assert leer_rango(q.ui) == (True, -1.5, 2.5)
    from plugins.analysis.time_frequency.pac import pac_plugin
    import inspect
    fuente = inspect.getsource(pac_plugin.Pac_plugin.get_analysis_params)
    assert "guardar_rango" in fuente, "el rango va en los parámetros del proyecto"


# ============================================================
#   Wavelet: cambiar el color ya no pierde el zoom
# ============================================================
def test_wavelet_cambiar_el_rango_conserva_el_zoom(app):
    from core.plugins.meta import PluginMeta
    from plugins.analysis.time_frequency.wavelet.wavelet_plugin import Wavelet_plugin
    from plugins.analysis.time_frequency.wavelet.wavelet_plugin_ui import Ui_Wavelet
    p = Wavelet_plugin(PluginMeta(id="w", name="Wavelet", category="Analysis", subcategory="Time-Frequency",
                                  version="1", icon="x.png", logic_class="Wavelet_plugin"))
    p.widget = QWidget()
    p.ui = Ui_Wavelet()
    p.ui.setupUi(p.widget)
    p.alerts = MagicMock()
    p._context_view = _vista()
    p.vtk_widget = SimpleNamespace()        # el menú contextual no hace falta aquí
    T, F = np.linspace(0, 1, 200), np.linspace(2, 40, 20)
    Z = np.random.default_rng(2).random((20, 200))
    p.render_scalogram(T, F, Z)
    p._ultimo = {"tiempos": T, "frecuencias": F, "matriz": Z, "titulo": "t", "logaritmica": False}
    chart = p._context_view.GetScene().GetItem(0)
    eje = chart.GetAxis(vtk.vtkAxis.BOTTOM)
    eje.SetRange(0.2, 0.4)
    p.ui.colorRangeCheckBox.setChecked(True)
    p.ui.colorMinSpinBox.setValue(0.25)
    p.ui.colorMaxSpinBox.setValue(0.75)
    p._redibujar_color()
    assert p._context_view.GetScene().GetItem(0) is chart, "antes se rehacía el gráfico"
    assert (eje.GetMinimum(), eje.GetMaximum()) == (0.2, 0.4)
    assert _rango_lut(chart) == (0.25, 0.75)

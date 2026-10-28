"""R33: el rango de valores del color del escalograma se puede fijar a mano."""
import numpy as np
import pytest
import vtk
from PyQt5.QtWidgets import QApplication, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from core.plugins.meta import PluginMeta
from core.utils.rango_color import limites_color
from plugins.analysis.time_frequency.wavelet.wavelet_plugin import Wavelet_plugin
from plugins.analysis.time_frequency.wavelet.wavelet_plugin_ui import Ui_Wavelet
from plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin import Wavelet_average_plugin
from plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin_ui import Ui_Wavelet_Average

Z = np.linspace(0.0, 10.0, 40).reshape(5, 8)
T = np.linspace(0, 1, 8)
F = np.linspace(2, 40, 5)


def test_limites_automaticos_y_manuales():
    assert limites_color(Z) == (0.0, 10.0)
    assert limites_color(Z, True, 2.0, 6.0) == (2.0, 6.0)
    assert limites_color(Z, True, 6.0, 6.0) == (0.0, 10.0), "rango inválido: vuelve al automático"
    assert limites_color(Z, True, 7.0, 3.0) == (0.0, 10.0)


@pytest.fixture(params=[(Wavelet_plugin, Ui_Wavelet, "wavelet"),
                        (Wavelet_average_plugin, Ui_Wavelet_Average, "wavelet_average")])
def plug(request):
    clase, clase_ui, nombre = request.param
    app = QApplication.instance() or QApplication([])
    if app.platformName() in ("offscreen", "minimal"):
        pytest.skip("VTK necesita OpenGL de una ventana real")
    meta = PluginMeta(id=nombre, name=nombre, category="analysis", subcategory="time_frequency",
                      version="0", icon="", logic_class=clase.__name__)
    p = clase(meta)
    p.widget = QWidget()
    p.ui = clase_ui()
    p.ui.setupUi(p.widget)
    p.vtk_widget = QVTKRenderWindowInteractor(p.widget)
    p.widget.show()
    app.processEvents()
    p._context_view = vtk.vtkContextView()
    p._context_view.SetRenderWindow(p.vtk_widget.GetRenderWindow())
    p._contexto = {"señal": "s", "canal": "c"}
    yield p
    p.vtk_widget.Finalize()


def _rango_lut(p):
    chart = p._context_view.GetScene().GetItem(0)
    return tuple(chart.emf_color.GetRange())


def test_por_defecto_el_rango_sale_de_los_datos_y_se_muestra(plug):
    plug.render_scalogram(T, F, Z)
    assert _rango_lut(plug) == (0.0, 10.0)
    assert (plug.ui.colorMinSpinBox.value(), plug.ui.colorMaxSpinBox.value()) == (0.0, 10.0)
    assert not plug.ui.colorMinSpinBox.isEnabled()


def test_con_rango_manual_el_color_usa_ese_rango(plug):
    plug.render_scalogram(T, F, Z)
    plug.ui.colorRangeCheckBox.setChecked(True)
    assert plug.ui.colorMinSpinBox.isEnabled() and plug.ui.colorMaxSpinBox.isEnabled()
    plug.ui.colorMinSpinBox.setValue(2.0)
    plug.ui.colorMaxSpinBox.setValue(6.0)
    plug._ultimo = {"tiempos": T, "frecuencias": F, "matriz": Z, "titulo": "t", "logaritmica": False}
    plug._redibujar_color()
    assert _rango_lut(plug) == (2.0, 6.0)
    plug.ui.colorRangeCheckBox.setChecked(False)
    plug._redibujar_color()
    assert _rango_lut(plug) == (0.0, 10.0)


def test_el_rango_se_guarda_y_se_restaura(plug):
    plug.ui.colorRangeCheckBox.setChecked(True)
    plug.ui.colorMinSpinBox.setValue(-1.5)
    plug.ui.colorMaxSpinBox.setValue(3.25)
    params = plug.get_analysis_params()
    assert params["color_manual"] is True and params["color_min"] == -1.5 and params["color_max"] == 3.25
    from core.utils.rango_color import restaurar_rango
    plug.ui.colorRangeCheckBox.setChecked(False)
    plug.ui.colorMinSpinBox.setValue(0.0)
    restaurar_rango(plug.ui, params)
    assert plug.ui.colorRangeCheckBox.isChecked() and plug.ui.colorMinSpinBox.value() == -1.5

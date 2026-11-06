"""Correcciones de navegación e interacción: R07, R10, R12, R25, R26, R27, R30, R32, R73, R76, R78.

Cada prueba fija un comportamiento que la revisión encontró sin cumplir.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import vtk
from PyQt5 import QtWidgets

from core.model.signal_dataset import SignalDataset
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.services.project_service import ProjectService
from core.utils.cursor_readout import punto_mas_cercano
from core.utils.selector_trials import SelectorDeTrials, columnas_elegidas
from core.utils.vtk_context_menu import EJE_X, EJE_Y, VTKContextMenu


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _grafico_con_curvas(n_curvas=2, n=100):
    from core.utils.adapters import trials_matrix_to_vtk_table
    from core.utils.submuestreo import agregar_columna
    t = np.linspace(0.0, 1.0, n)
    M = np.column_stack([np.sin(5 * t) + k for k in range(n_curvas)])
    tabla = trials_matrix_to_vtk_table(t, M)
    chart = vtk.vtkChartXY()
    for c in range(1, tabla.GetNumberOfColumns()):
        agregar_columna(chart, tabla, c)
    return chart, t, M


# ---------------- R30: los ejes del zoom ----------------
def test_los_ejes_del_zoom_son_los_de_vtk():
    assert EJE_X == vtk.vtkAxis.BOTTOM and EJE_Y == vtk.vtkAxis.LEFT


@pytest.mark.parametrize("modo,x,y", [("x", True, False), ("y", False, True), ("xy", True, True)])
def test_set_zoom_mode_amplia_el_eje_que_dice_su_nombre(modo, x, y):
    chart = vtk.vtkChartXY()
    menu = VTKContextMenu.__new__(VTKContextMenu)
    menu.chart = chart
    menu.set_zoom_mode(modo)
    assert bool(chart.GetAxisZoom(EJE_X)) is x and bool(chart.GetAxisZoom(EJE_Y)) is y


# ---------------- R32 y R73: el butterfly del ERP ----------------
def _erp(n_trials):
    from plugins.analysis.time.erp.erp_plugin import Erp_plugin
    p = Erp_plugin.__new__(Erp_plugin)
    p.meta = PluginMeta(id="erp", name="ERP", category="Analysis", subcategory="Time", version="1", icon="i",
                        logic_class="Erp_plugin")
    p.view_top = vtk.vtkContextView()
    p.vtk_top = None
    p.alerts = Mock()
    p.active_signal = SimpleNamespace(name="s")
    p.ch_name = "c"
    p.widget = None
    p.vtk_menu = None
    t = np.linspace(0, 1, 50)
    return p, t, np.random.default_rng(0).standard_normal((n_trials, 50))


def _grafico_del_erp(p):
    return p.view_top.GetScene().GetItem(0)


def test_el_butterfly_se_llama_butterfly_en_pantalla():
    p, t, sel = _erp(5)
    p._render_butterfly(t, sel, title="ERP — c — todos (5)")
    titulo = _grafico_del_erp(p).GetTitle()
    assert "Butterfly" in titulo and "ERP — c" in titulo


def test_el_butterfly_dibuja_a_lo_sumo_200_curvas_sin_tocar_los_datos():
    p, t, sel = _erp(250)
    antes = sel.copy()
    p._render_butterfly(t, sel, title="x")
    assert _grafico_del_erp(p).GetNumberOfPlots() == 200
    assert np.array_equal(sel, antes) and sel.shape[0] == 250


# ---------------- R26: el valor es el de la muestra ----------------
def test_la_lectura_del_cursor_cae_en_un_punto_de_la_senal():
    chart, t, M = _grafico_con_curvas(1)
    x, y = punto_mas_cercano(chart, 0.5013, 5.0)
    j = int(np.argmin(np.abs(t - 0.5013)))
    assert x == pytest.approx(t[j]) and y == pytest.approx(M[j, 0])


def test_con_varias_curvas_toma_la_mas_cercana_en_y():
    chart, t, M = _grafico_con_curvas(3)
    j = int(np.argmin(np.abs(t - 0.5)))
    x, y = punto_mas_cercano(chart, 0.5, M[j, 2] + 0.01)
    assert y == pytest.approx(M[j, 2])


def test_sin_curvas_no_inventa_un_punto():
    assert punto_mas_cercano(vtk.vtkChartXY(), 0.0, 0.0) is None


# ---------------- R27: elegir los trials de un análisis ----------------
def test_el_selector_devuelve_las_posiciones_marcadas(app):
    s = SelectorDeTrials()
    s.establecer_total(5)
    assert s.posiciones() == [1, 2, 3, 4, 5]
    s.lista.item(1).setCheckState(0)
    s.lista.item(3).setCheckState(0)
    assert s.posiciones() == [1, 3, 5]
    s._marcar(False)
    assert s.posiciones() == []


def test_columnas_elegidas_usa_posiciones_base_1():
    X = np.arange(12).reshape(3, 4)
    assert np.array_equal(columnas_elegidas(X, [2, 4]), X[:, [1, 3]])
    assert columnas_elegidas(X, [1, 2, 3, 4]) is X
    assert columnas_elegidas(X, None) is X


class _Modulo(IPlugin):
    def process(self, data): pass
    def stop(self): pass
    def get_widget(self, parent=None): return None


def _modulo(app):
    meta = PluginMeta(id="m", name="M", category="Analysis", subcategory="s", version="1", icon="i", logic_class="C")
    m = _Modulo(meta)
    m.alerts = Mock()
    m.ui = SimpleNamespace(layoutWidget=QtWidgets.QWidget())
    m.ui.paramsLayout = QtWidgets.QVBoxLayout(m.ui.layoutWidget)
    m.ui.paramsLayout.addStretch(1)
    return m


def test_elegir_trials_sin_selector_deja_pasar_todo(app):
    m = _modulo(app)
    X = np.ones((10, 4))
    assert m.elegir_trials(X) == (X, None, 4) or m.elegir_trials(X)[1] is None


def test_elegir_trials_aplica_la_seleccion_y_avisa_si_no_hay_ninguno(app):
    m = _modulo(app)
    m.crear_selector_de_trials()
    X = np.arange(40, dtype=float).reshape(10, 4)
    Xs, pos, total = m.elegir_trials(X)
    assert Xs.shape == (10, 4) and pos is None and total == 4
    m.selector_trials.lista.item(0).setCheckState(0)
    m.selector_trials.lista.item(2).setCheckState(0)
    Xs, pos, total = m.elegir_trials(X)
    assert pos == [2, 4] and np.array_equal(Xs, X[:, [1, 3]]) and total == 4
    m.selector_trials._marcar(False)
    assert m.elegir_trials(X)[0] is None
    m.alerts.warning.assert_called()


# ---------------- R76: lo que ofrece el filtro funciona ----------------
def test_el_combo_del_filtro_solo_ofrece_lo_implementado(app):
    from core.filters.bandpass import filtrar_banda
    from plugins.preprocessing.prepare.filter import filter_plugin
    fuente = Path(filter_plugin.__file__).read_text(encoding="utf-8")
    assert 'addItems(["Butterworth"])' in fuente
    x = np.random.default_rng(0).standard_normal(2000)
    assert filtrar_banda(x, 5, 40, 4, 1000.0, "butterworth").shape == x.shape


# ---------------- R12: cargar otra señal cierra el proyecto abierto ----------------
def _ventana(abierto, confirma, sucio=False):
    from app.view.main_window import MainWindow
    servicio = SimpleNamespace(is_open=abierto, project_name="mio", dirty=sucio,
                               close=Mock(side_effect=lambda: setattr(servicio, "is_open", False)))
    barra = Mock()
    v = SimpleNamespace(project_service=servicio, _confirm_discard_unsaved_changes=Mock(return_value=confirma),
                        _update_title_bar_signal_name=Mock(), statusBar=lambda: barra)
    return MainWindow.cerrar_proyecto_para_nueva_senal, v, barra


def test_sin_proyecto_abierto_no_pregunta_ni_cierra_nada():
    f, v, barra = _ventana(abierto=False, confirma=True)
    assert f(v) is True
    v._confirm_discard_unsaved_changes.assert_not_called()
    v.project_service.close.assert_not_called()


def test_si_el_usuario_cancela_el_proyecto_sigue_abierto():
    f, v, barra = _ventana(abierto=True, confirma=False, sucio=True)
    assert f(v) is False
    v.project_service.close.assert_not_called()
    assert v.project_service.is_open


def test_al_confirmar_se_cierra_el_proyecto_y_se_comunica():
    f, v, barra = _ventana(abierto=True, confirma=True)
    assert f(v) is True
    v.project_service.close.assert_called_once()
    assert not v.project_service.is_open, "guardar después ya no escribe sobre el proyecto anterior"
    assert "mio" in barra.showMessage.call_args[0][0]


# ---------------- R78 y R07: la señal que falta y la ruta registrada ----------------
class _FileIO:
    def load_abf(self, ruta):
        t = np.arange(100) / 100.0
        return SignalDataset(name=Path(ruta).name, format="abf", source_path=str(ruta), sampling_rate=100.0,
                             time=t, signals=np.vstack([t, t]), channel_names=["a", "b"], units=["mV", "mV"])


def _servicio():
    from core.kernel import Kernel
    from core.services.data_store import DataStore
    k = Kernel()
    k.register_service("DataStore", DataStore())
    k.register_service("FileIO", _FileIO())
    return ProjectService(k)


def _escribir(glab, firma):
    glab.write_text(json.dumps({"schema_version": 1, "project_name": "p", "signal": firma,
                                "measurements": [], "trials": [], "analysis": {}}), encoding="utf-8")


def test_senal_faltante_nombra_el_archivo_que_no_se_encontro(tmp_path):
    ps = _servicio()
    _escribir(tmp_path / "p.glab", {"filename": "s.abf", "format": "abf"})
    manifiesto, ds = ps.preparar_apertura(str(tmp_path / "p.glab"))
    assert ds is None and ps.senal_faltante(manifiesto, ds) == "s.abf"


def test_si_la_senal_se_encuentra_no_hay_aviso(tmp_path):
    ps = _servicio()
    (tmp_path / "s.abf").write_bytes(b"x")
    _escribir(tmp_path / "p.glab", {"filename": "s.abf", "format": "abf"})
    manifiesto, ds = ps.preparar_apertura(str(tmp_path / "p.glab"))
    assert ds is not None and ps.senal_faltante(manifiesto, ds) is None


def test_sin_copia_junto_al_proyecto_se_usa_la_ruta_de_origen(tmp_path):
    origen = tmp_path / "datos"
    origen.mkdir()
    (origen / "s.abf").write_bytes(b"x")
    carpeta = tmp_path / "proyecto"
    carpeta.mkdir()
    _escribir(carpeta / "p.glab", {"filename": "s.abf", "source_path": str(origen / "s.abf"), "format": "abf"})
    manifiesto, ds = _servicio().preparar_apertura(str(carpeta / "p.glab"))
    assert ds is not None and Path(ds.source_path) == origen / "s.abf"


def test_el_manifiesto_registra_la_ruta_y_el_nombre_de_la_senal(tmp_path):
    ps = _servicio()
    origen = tmp_path / "s.abf"
    origen.write_bytes(b"x")
    ds = _FileIO().load_abf(origen)
    ps.project_dir = tmp_path / "proy"
    ps.glab_path = ps.project_dir / "p.glab"
    ps.project_name = "p"
    ps._write_manifest(ds, copiar=False)
    firma = json.loads(ps.glab_path.read_text(encoding="utf-8"))["signal"]
    assert firma["filename"] == "s.abf" and Path(firma["source_path"]) == origen.resolve()


# ---------------- R25 y R10 ----------------
def test_clear_de_trials_devuelve_tambien_los_selectores(app):
    from plugins.preprocessing.trials.trials_plugin import TrialsPlugin
    from plugins.preprocessing.trials.trial_plugin_ui import Ui_Trials
    p = TrialsPlugin.__new__(TrialsPlugin)
    p.meta = PluginMeta(id="t", name="Trials", category="Preprocessing", subcategory="Trials", version="1", icon="i",
                        logic_class="TrialsPlugin")
    p.ui = Ui_Trials()
    p.ui.setupUi()
    p.params = {"threshold": 0.7, "t0": -0.05, "t1": 4.0, "stim_count": 1, "inter_stim_time": 0.1}
    for nombre in ("a", "b", "c"):
        p.ui.channelComboBox.addItem(nombre)
        p.ui.stimChannelComboBox.addItem(nombre)
    p.ui.channelComboBox.setCurrentIndex(2)
    p.ui.stimChannelComboBox.setCurrentIndex(0)
    p.ui.endModeCombo.setCurrentIndex(1)
    p._on_clear_params_clicked()
    assert p.ui.channelComboBox.currentIndex() == 0
    assert p.ui.stimChannelComboBox.currentIndex() == 2
    assert p.ui.endModeCombo.currentIndex() == 0


def _ventana_bienvenida(vista):
    from app.view.main_window import MainWindow
    ajustes = {"bienvenida_mostrada": vista}
    servicio = SimpleNamespace(get=lambda k, d=None: ajustes.get(k, d), set=lambda k, v: ajustes.update({k: v}))
    kernel = SimpleNamespace(get_service=lambda nombre: servicio)
    ventana = SimpleNamespace(kernel=kernel, PASOS_BIENVENIDA=MainWindow.PASOS_BIENVENIDA)
    return MainWindow.mostrar_bienvenida_inicial, ventana, ajustes


def test_la_bienvenida_solo_sale_la_primera_vez(app, monkeypatch):
    f, ventana, ajustes = _ventana_bienvenida(vista=False)
    llamadas = []

    class DialogoFalso:
        def __init__(self, pasos, parent=None):
            llamadas.append(" ".join(titulo for titulo, _ in pasos))

        def exec_(self):
            return 0

    monkeypatch.setattr("app.view.main_window.DialogoBienvenida", DialogoFalso)
    assert f(ventana) is True
    assert ajustes["bienvenida_mostrada"] is True and "Home" in llamadas[0] and "Analysis" in llamadas[0]
    assert f(ventana) is False and len(llamadas) == 1


# ---------------- R27: Wavelet de un trial usa el trial elegido ----------------
def test_el_selector_de_un_trial_deja_marcado_uno_solo(app):
    s = SelectorDeTrials(unico=True)
    s.establecer_total(5)
    assert s.posiciones() == [1]
    s.lista.item(3).setCheckState(2)
    assert s.posiciones() == [4]
    s.lista.item(1).setCheckState(2)
    assert s.posiciones() == [2]


def test_crear_el_selector_de_un_trial_en_un_modulo(app):
    m = _modulo(app)
    m.crear_selector_de_trials(unico=True)
    assert m.selector_trials.unico is True
    m.selector_trials.establecer_total(3)
    assert m.selector_trials.posiciones() == [1]

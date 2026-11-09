"""Regresiones de cerrar y abrir proyectos.

- Cerrar con un cálculo en curso: «Cerrar de todos modos» cerraba sin ofrecer
  guardar los cambios.
- Cerrar (o cargar otra señal) mientras se abría un proyecto no cancelaba la
  apertura, y al terminar el proyecto se abría igual.
- Reabrir un proyecto lo dejaba marcado como modificado: los análisis que se
  recalculan al abrirlo llamaban a mark_project_dirty.

La ventana no se crea: bajo la QCoreApplication de la suite crear widgets aborta
el proceso. Se llaman los métodos de MainWindow sobre un doble, como hace
test_instalacion_rutas.py.
"""
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt5.QtCore import QCoreApplication

import app.view.main_window as modulo_ventana
from app.view.main_window import MainWindow
from core.kernel import Kernel
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.services.data_store import DataStore
from core.services.project_service import ProjectService
from core.services.task_service import TaskService


@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


def esperar(condicion, ms=10000):
    app = QCoreApplication.instance()
    limite = time.monotonic() + ms / 1000.0
    while time.monotonic() < limite:
        app.processEvents()
        if condicion():
            return True
        time.sleep(0.005)
    app.processEvents()
    return condicion()


# ============================================================
#   Cerrar con un cálculo en curso
# ============================================================
class _CajaFalsa:
    """Lo que `_confirm_discard_unsaved_changes` usa de QMessageBox. Pulsa, en orden,
    los botones de `guion` y anota el título de cada caja que se mostró."""
    Warning, DestructiveRole, RejectRole, AcceptRole = range(4)
    guion, mostradas = [], []

    def __init__(self, parent=None):
        self._botones, self._titulo, self._pulsado = [], "", None

    def setIcon(self, *_):
        pass

    def setWindowTitle(self, titulo):
        self._titulo = titulo

    def setText(self, *_):
        pass

    def addButton(self, texto, rol):
        boton = SimpleNamespace(texto=texto)
        self._botones.append(boton)
        return boton

    def setDefaultButton(self, *_):
        pass

    def exec_(self):
        _CajaFalsa.mostradas.append(self._titulo)
        quiero = _CajaFalsa.guion.pop(0)
        self._pulsado = next(b for b in self._botones if b.texto == quiero)

    def clickedButton(self):
        return self._pulsado


@pytest.fixture
def ventana(monkeypatch):
    monkeypatch.setattr(modulo_ventana, "QMessageBox", _CajaFalsa)
    _CajaFalsa.guion, _CajaFalsa.mostradas = [], []
    return SimpleNamespace(
        _project_busy=False, _guardando=False,
        _any_background_worker_running=lambda: True,
        _stop_all_background_workers=Mock(),
        project_service=SimpleNamespace(dirty=True, save=Mock(return_value="p.glab")),
        alerts=Mock())


def confirmar(v, *botones):
    _CajaFalsa.guion = list(botones)
    return MainWindow._confirm_discard_unsaved_changes(v)


def test_tras_cancelar_el_calculo_se_ofrece_guardar(ventana):
    assert confirmar(ventana, "Cerrar de todos modos", "Save") is True
    assert _CajaFalsa.mostradas == ["Cálculo en curso", "Unsaved Changes"]
    ventana._stop_all_background_workers.assert_called_once()
    ventana.project_service.save.assert_called_once()


def test_se_puede_arrepentir_en_la_pregunta_de_guardar(ventana):
    assert confirmar(ventana, "Cerrar de todos modos", "Cancel") is False


def test_sin_cambios_basta_con_aceptar_la_cancelacion(ventana):
    ventana.project_service.dirty = False
    assert confirmar(ventana, "Cerrar de todos modos") is True
    assert _CajaFalsa.mostradas == ["Cálculo en curso"]


def test_quedarse_no_cancela_nada(ventana):
    assert confirmar(ventana, "Quedarme") is False
    ventana._stop_all_background_workers.assert_not_called()


def test_mientras_se_guarda_no_se_deja_cerrar(ventana):
    ventana._guardando = True
    assert confirmar(ventana) is False
    assert _CajaFalsa.mostradas == []
    ventana.alerts.warning.assert_called_once()
    ventana._stop_all_background_workers.assert_not_called()


# ============================================================
#   Cerrar mientras se abre un proyecto
# ============================================================
def test_cancelar_todo_cancela_tambien_la_apertura_del_proyecto(qt_app):
    tareas = TaskService()
    eventos = []

    def leer_proyecto(ctx):
        for _ in range(400):
            if ctx.cancelled:
                return None
            time.sleep(0.005)
        return "proyecto"

    h = tareas.submit(leer_proyecto, owner="project")
    h.finished.connect(lambda r: eventos.append("abierto"))
    h.cancelled.connect(lambda: eventos.append("cancelado"))
    v = SimpleNamespace(kernel=SimpleNamespace(
        get_service=lambda clave: tareas if clave == "TaskService" else None,
        get_plugins=lambda: [], get_plugin=lambda nombre: None))
    MainWindow._cancel_all_tasks(v)
    assert esperar(lambda: eventos)
    assert eventos == ["cancelado"]


# ============================================================
#   Reabrir un proyecto no lo marca como modificado
# ============================================================
class _Analisis(IPlugin):
    """Un análisis mínimo que, como los de verdad, recalcula al restaurarse y marca
    el proyecto cuando le llega el resultado."""

    def __init__(self):
        super().__init__(PluginMeta(id="falso", name="Falso", category="Analysis",
                                    subcategory="Time", version="1.0", icon="x.png",
                                    logic_class="_Analisis"))
        self.started = True
        self.resultados = []

    def stop(self):
        pass

    def get_widget(self, parent=None):
        return None

    def process(self, data):
        pass

    def apply_analysis_params(self, params):
        self.calcular()

    def calcular(self):
        self.run_task(lambda: 42, self._listo)

    def _listo(self, resultado):
        self.resultados.append(resultado)
        self.mark_project_dirty()


def proyecto_con(plugin, con_tareas=True):
    kernel, store = Kernel(), DataStore()
    kernel.register_service("DataStore", store)
    if con_tareas:
        kernel.register_service("TaskService", TaskService())
    kernel.register_plugin("falso", plugin)
    plugin.kernel = kernel
    ps = ProjectService(kernel)
    store.set("_project_service", ps)
    return ps


def test_el_recalculo_al_abrir_no_marca_el_proyecto(qt_app):
    plugin = _Analisis()
    ps = proyecto_con(plugin)
    ps._restore_analysis({"falso": {}})
    assert esperar(lambda: plugin.resultados)
    assert not ps.dirty


def test_lo_que_el_usuario_calcula_despues_si_lo_marca(qt_app):
    plugin = _Analisis()
    ps = proyecto_con(plugin)
    ps._restore_analysis({"falso": {}})
    assert esperar(lambda: plugin.resultados)
    plugin.calcular()
    assert esperar(lambda: len(plugin.resultados) == 2)
    assert ps.dirty


def test_sin_servicio_de_tareas_tampoco_marca(qt_app):
    plugin = _Analisis()
    ps = proyecto_con(plugin, con_tareas=False)
    ps._restore_analysis({"falso": {}})
    assert plugin.resultados == [42]
    assert not ps.dirty


class _Handle:
    pass


def plugin_sin_run_task(clase, ps):
    """Los que envían su tarea por su cuenta: se anota el handle como lo hacen ellos."""
    p = object.__new__(clase)
    store = DataStore()
    store.set("_project_service", ps)
    p.kernel = SimpleNamespace(get_service=lambda clave: store if clave == "DataStore" else None)
    p.mainwin = None
    p.ui = object()
    p._handle = h = _Handle()
    p._restaurando_proyecto = True
    p._anotar_si_restaura(h)
    p._restaurando_proyecto = False
    for nombre in ("ensure_vtk", "render_resultado", "_avisar_de_los_limites", "render_scalogram",
                   "publish_current_trial", "_notify", "_log", "_terminar_calculo", "process"):
        setattr(p, nombre, lambda *a, **k: None)
    p.get_analysis_params = lambda: {}
    p._contexto = {}
    p._trials_en_curso = None
    return p, h


@pytest.mark.parametrize("ruta,clase", [
    ("plugins.analysis.time_frequency.modulation_index.modulation_index_plugin", "Modulation_index_plugin"),
    ("plugins.analysis.time_frequency.wavelet.wavelet_plugin", "Wavelet_plugin"),
    ("plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin", "Wavelet_average_plugin"),
])
def test_los_plugins_sin_run_task_tampoco_marcan_al_restaurar(ruta, clase):
    import importlib
    ps = ProjectService(Kernel())
    p, h = plugin_sin_run_task(getattr(importlib.import_module(ruta), clase), ps)
    if clase == "Modulation_index_plugin":
        p._on_mi_done(h, 0, object())
    else:
        p._on_wavelet_done(h, ([0.0], [1.0], [[0.0]], False))
    assert not ps.dirty
    # Y una tarea que el usuario pide después sí marca
    p._handle = otro = _Handle()
    if clase == "Modulation_index_plugin":
        p._on_mi_done(otro, 0, object())
    else:
        p._on_wavelet_done(otro, ([0.0], [1.0], [[0.0]], False))
    assert ps.dirty

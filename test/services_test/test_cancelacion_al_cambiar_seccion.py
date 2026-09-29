import time

import pytest
from PyQt5.QtCore import QCoreApplication

from core.kernel import Kernel
from core.services.data_store import DataStore
from core.services.task_service import TaskService


@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


def wait_for(predicate, timeout_ms=5000):
    app = QCoreApplication.instance()
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return predicate()


class _MetaFalso:
    def __init__(self, id_):
        self.id = id_


class _PluginFalso:
    def __init__(self, id_):
        self.meta = _MetaFalso(id_)
        self.detenido = False

    def stop(self):
        self.detenido = True


class _VentanaFalsa:
    """Reproduce solo lo que hace MainWindow.clear_plugin_area con las tareas."""

    def __init__(self, kernel):
        self.kernel = kernel

    def _cancel_tasks_of(self, plugin):
        try:
            tasks = self.kernel.get_service("TaskService")
            if tasks is not None and getattr(plugin, "meta", None) is not None:
                tasks.cancel_all_from(plugin.meta.id)
        except Exception as e:
            print("cancel_tasks_of error:", e)

    def clear_plugin_area(self, plugin):
        self._cancel_tasks_of(plugin)
        plugin.stop()


def calculo_largo(ctx, vueltas=400):
    for _ in range(vueltas):
        if ctx.cancelled:
            return "cancelado"
        ctx.progress(-1, "trabajando")
        time.sleep(0.005)
    return "completado"


def test_cambiar_de_seccion_cancela_las_tareas_del_plugin(qt_app):
    kernel = Kernel()
    kernel.register_service("DataStore", DataStore())
    kernel.register_service("TaskService", TaskService())
    tasks = kernel.get_service("TaskService")

    ventana = _VentanaFalsa(kernel)
    plugin = _PluginFalso("wavelet_average")

    resultados = {"finished": 0, "cancelled": 0}
    handle = tasks.submit(calculo_largo, owner=plugin.meta.id, vueltas=400)
    handle.finished.connect(lambda _: resultados.__setitem__("finished",
                                                             resultados["finished"] + 1))
    handle.cancelled.connect(lambda: resultados.__setitem__("cancelled",
                                                            resultados["cancelled"] + 1))

    assert wait_for(lambda: tasks.has_active_tasks(), timeout_ms=2000)

    ventana.clear_plugin_area(plugin)

    assert wait_for(lambda: resultados["cancelled"] == 1)
    assert plugin.detenido
    assert resultados["finished"] == 0, "la tarea abandonada no debe entregar resultado"
    assert not tasks.has_active_tasks(), "quedaron tareas vivas tras cambiar de seccion"


def test_cambiar_de_seccion_no_toca_a_otros_plugins(qt_app):
    kernel = Kernel()
    kernel.register_service("TaskService", TaskService())
    tasks = kernel.get_service("TaskService")

    ventana = _VentanaFalsa(kernel)
    que_sale = _PluginFalso("wavelet_average")
    que_queda = _PluginFalso("trials")

    estado = {"sale": None, "queda": None}
    h1 = tasks.submit(calculo_largo, owner=que_sale.meta.id, vueltas=400)
    h1.cancelled.connect(lambda: estado.__setitem__("sale", "cancelled"))
    h1.finished.connect(lambda _: estado.__setitem__("sale", "finished"))

    h2 = tasks.submit(calculo_largo, owner=que_queda.meta.id, vueltas=3)
    h2.cancelled.connect(lambda: estado.__setitem__("queda", "cancelled"))
    h2.finished.connect(lambda _: estado.__setitem__("queda", "finished"))

    assert wait_for(lambda: tasks.has_active_tasks(), timeout_ms=2000)

    ventana.clear_plugin_area(que_sale)

    assert wait_for(lambda: estado["sale"] is not None and estado["queda"] is not None)
    assert estado["sale"] == "cancelled"
    assert estado["queda"] == "finished", "la tarea del otro plugin debio completarse"

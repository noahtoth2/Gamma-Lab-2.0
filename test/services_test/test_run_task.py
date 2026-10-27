"""`IPlugin.run_task`: el patrón único para despachar un cómputo al orquestador (R70/R71)."""
import threading
import time

import pytest
from PyQt5.QtCore import QCoreApplication

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.services.task_service import TaskService


class _Kernel:
    def __init__(self, servicios):
        self._s = servicios

    def get_service(self, clave):
        return self._s.get(clave)


class _Plugin(IPlugin):
    def start(self, kernel): ...
    def stop(self): ...
    def process(self, data): ...
    def get_widget(self, parent=None): ...
    def on_kernel_event(self, topic, payload): ...

    def _notify(self, msg):
        self.avisos = getattr(self, "avisos", []) + [msg]


def _plugin(tareas):
    meta = PluginMeta(id="demo", name="Demo", category="Analysis", subcategory="X",
                      version="1.0", icon="i.png", logic_class="_Plugin")
    p = _Plugin(meta)
    p.kernel = _Kernel({"TaskService": tareas} if tareas else {})
    p.alerts.error = lambda m, *a, **k: setattr(p, "error", m)
    return p


@pytest.fixture
def app():
    return QCoreApplication.instance() or QCoreApplication([])


def esperar(app, cond, s=10):
    limite = time.monotonic() + s
    while time.monotonic() < limite:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    return cond()


def test_el_calculo_corre_fuera_del_hilo_de_la_interfaz_y_el_resultado_vuelve_a_ella(app):
    hilos = {}
    p = _plugin(TaskService())

    def trabajo(x, ctx=None):
        hilos["trabajo"] = threading.current_thread()
        return x * 2

    p.run_task(trabajo, lambda r: hilos.update(llego=r, ui=threading.current_thread()), x=21)
    assert esperar(app, lambda: "llego" in hilos)
    assert hilos["llego"] == 42
    assert hilos["trabajo"] is not threading.main_thread()
    assert hilos["ui"] is threading.main_thread()


def test_sin_orquestador_corre_en_linea_con_los_mismos_callbacks():
    p = _plugin(None)
    visto, fin = [], []
    p.run_task(lambda x, ctx=None: x + 1, visto.append, on_finished=lambda: fin.append(1), x=1)
    assert visto == [2] and fin == [1]


def test_un_fallo_llega_a_on_failed_y_no_a_on_done(app):
    p = _plugin(TaskService())
    hecho, fallos, fin = [], [], []

    def malo(ctx=None):
        raise ValueError("rango inválido")

    p.run_task(malo, hecho.append, on_failed=fallos.append, on_finished=lambda: fin.append(1))
    assert esperar(app, lambda: fin)
    assert len(fallos) == 1 and "rango inválido" in fallos[0] and hecho == []


def test_sin_on_failed_el_error_sale_por_las_alertas(app):
    p = _plugin(TaskService())
    fin = []

    def malo(ctx=None):
        raise ValueError("boom")

    p.run_task(malo, lambda r: None, on_finished=lambda: fin.append(1))
    assert esperar(app, lambda: fin)
    assert "boom" in p.error


def test_una_tarea_nueva_descarta_el_resultado_de_la_anterior(app):
    p = _plugin(TaskService())
    llegaron = []
    soltar = threading.Event()

    def lenta(ctx=None):
        soltar.wait(5)
        return "vieja"

    p.run_task(lenta, llegaron.append)
    p.run_task(lambda ctx=None: "nueva", llegaron.append)
    soltar.set()
    assert esperar(app, lambda: llegaron)
    time.sleep(0.1)
    app.processEvents()
    assert llegaron == ["nueva"]


def test_el_progreso_de_la_tarea_llega_al_plugin(app):
    p = _plugin(TaskService())
    fin = []

    def con_progreso(ctx=None):
        ctx.progress(50, "mitad")
        return 1

    p.run_task(con_progreso, lambda r: None, on_finished=lambda: fin.append(1))
    assert esperar(app, lambda: fin)
    assert any("mitad" in a for a in getattr(p, "avisos", []))

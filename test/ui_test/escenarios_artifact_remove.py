"""Escenarios de interfaz de Remove Artifact con el orquestador (Fase 3).

Se ejecuta en un proceso aparte desde test_plugins_con_orquestador.py, porque
necesita una QApplication con widgets y el resto de la suite usa QCoreApplication.
Imprime una línea "CASO|OK|nombre|detalle" (o "CASO|FALLA|...") por comprobación.
El dibujo de VTK se sustituye: sin pantalla no hay OpenGL.
"""
import contextlib
import copy
import io
import os
import sys
import time
import traceback
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.chdir(REPO)

import numpy as np
from PyQt5.QtWidgets import QApplication

app = QApplication([])
ERRORES = []
sys.excepthook = lambda t, v, tb: ERRORES.append("".join(traceback.format_exception(t, v, tb)))

from core.kernel import Kernel
from core.filters import trials as tr
from core.plugins.meta import PluginMeta
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService
from core.services.task_service import TaskService
from app.view.main_window import MainWindow
import plugins.preprocessing.prepare.artifact_remove.artifact_remove_plugin as modulo
from plugins.preprocessing.prepare.artifact_remove.artifact_logic import apply_modification_to_all_valid
from plugins.preprocessing.prepare.artifact_remove.artifact_remove_plugin import ArtifactRemovePlugin

with contextlib.redirect_stdout(io.StringIO()):
    SD0 = FileIOService().load_abf(str(REPO / "test" / "data" / "17308005.abf"))
SD0.signals = SD0.signals.astype(np.float64, copy=False)
SD0.time = SD0.time.astype(np.float64, copy=False)


def caso(nombre, ok, detalle=""):
    print(f"CASO|{'OK' if ok else 'FALLA'}|{nombre}|{detalle}".replace("\n", " "), flush=True)


def esperar(pred, t=30):
    fin = time.monotonic() + t
    while time.monotonic() < fin:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.002)
    app.processEvents()
    return pred()


# En la aplicación cada plugin vive toda la sesión. Aquí se crean varios, así que se
# conservan todos: si el recolector de basura vaciara uno descartado, Qt todavía podría
# mandarle eventos a su widget y el filtro de visibilidad fallaría (no pasa en la app).
VIVOS = []


class Entorno:
    """Kernel, DataStore y TaskService reales, la señal real y el plugin con VTK sustituido."""

    def __init__(self, descartes=()):
        VIVOS.append(self)
        self.sd = copy.deepcopy(SD0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.td = tr.cut_trials_single_channel(
                ds=self.sd, channel=0, stim_channel=1, threshold=0.7, t0=-0.05, t1=4.00,
                end_mode="until_next_onset", stim_expected=1, inter_stim_time=0.0, pad_value=0.0, debug=False)
            self.sd.add_trial_dataset(self.td)
            for i in descartes:
                self.sd.discard_trial(Path(self.td.source).name, self.td.channel_name, i)
        self.kernel = Kernel()
        self.store = DataStore()
        self.tasks = TaskService()
        self.kernel.register_service("DataStore", self.store)
        self.kernel.register_service("TaskService", self.tasks)
        self.store.set_active_signal(self.store.add_signal(self.sd))
        self.eventos = []
        self.kernel.event.connect(lambda topic, payload: self.eventos.append(topic))
        meta = PluginMeta(id="artifact_remove", name="Remove Artifact", category="preprocessing",
                          subcategory="prepare", version="0", icon="", logic_class="ArtifactRemovePlugin")
        p = ArtifactRemovePlugin(meta)
        with contextlib.redirect_stdout(io.StringIO()):
            self.kernel.register_plugin(meta.name, p)
            p.start(self.kernel)
        self.avisos, self.estado, self.dibujos = [], [], []
        for tipo in ("info", "error", "warning"):
            setattr(p.alerts, tipo, lambda msg, *a, _t=tipo: self.avisos.append((_t, str(msg))))
        p._notify = lambda msg: self.estado.append(msg)
        p._ensure_vtk = lambda: None
        p._clear_render = lambda *a, **k: None
        p._force_render = lambda: None
        p._plot_curve = lambda t, y, title="", ch="": self.dibujos.append(title)
        with contextlib.redirect_stdout(io.StringIO()):
            p.get_widget(None)
            p.widget.show()
            app.processEvents()
        self.p = p

    def aplicar(self, modo, a, b=""):
        self.p.ui.mode_combo.setCurrentText(modo)
        self.p.ui.point_a.setText(str(a))
        self.p.ui.point_b.setText(str(b))
        self.avisos.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            self.p._on_apply_changes()

    def en_reposo(self):
        ui = self.p.ui
        return (self.p._apply_handle is None and not self.tasks.has_active_tasks()
                and ui.mode_combo.isEnabled() and ui.prev_button.isEnabled() and ui.next_button.isEnabled())

    def quieto(self, t=30):
        with contextlib.redirect_stdout(io.StringIO()):
            return esperar(self.en_reposo, t)

    def controles(self):
        ui = self.p.ui
        return tuple(w.isEnabled() for w in (ui.apply_button, ui.mode_combo, ui.prev_button, ui.next_button))


def referencia(modo, a, b=0.0, descartes=()):
    """Los mismos trials modificados con la versión síncrona, sin orquestador ni interfaz."""
    e = Entorno(descartes)
    mode = "blank" if modo == "Cut From The Start" else "interpolate"
    with contextlib.redirect_stdout(io.StringIO()):
        apply_modification_to_all_valid(e.kernel, mode=mode, point_a=a, point_b=b or 0.0)
    return e.td.trials


real = modulo.calcular_modificacion


def lento(t, trials, *, mode, point_a, point_b=0.0, ctx=None):
    fin = time.monotonic() + 1.0
    while time.monotonic() < fin:
        if ctx is not None and ctx.cancelled:
            return None
        ctx.progress(10, "esperando")
        time.sleep(0.01)
    return real(t, trials, mode=mode, point_a=point_a, point_b=point_b, ctx=ctx)


def otra_tarea_lenta(ctx):
    fin = time.monotonic() + 1.0
    while time.monotonic() < fin and not ctx.cancelled:
        time.sleep(0.01)
    return "otra"


# A. Mismo resultado que sin orquestador, controles y avisos
for nombre, modo, a, b, desc in (("cortar desde el inicio", "Cut From The Start", 0.10, "", ()),
                                 ("interpolar con descartes", "Interpolate Interval", 1.00, 1.20, (3, 10, 25))):
    e = Entorno(desc)
    e.aplicar(modo, a, b)
    ocupado = e.controles()
    e.quieto()
    caso(f"A. {nombre}: mismos trials que sin orquestador",
         np.array_equal(e.td.trials, referencia(modo, a, b, desc), equal_nan=True)
         and e.eventos.count("trials_generated") == 1, f"eventos {e.eventos}")
    caso(f"A. {nombre}: controles bloqueados mientras calcula y liberados al terminar",
         ocupado == (False, False, False, False) and e.controles() == (True, True, True, True),
         f"durante {ocupado} · después {e.controles()}")
    caso(f"A. {nombre}: aviso en español y la vista se vuelve a dibujar",
         ("info", "Cambios aplicados a todos los trials válidos.") in e.avisos and bool(e.dibujos), str(e.avisos))

# B. Nada que modificar
e = Entorno()
antes = e.td.trials.copy()
e.aplicar("Cut From The Start", -1.0)
e.quieto()
caso("B. cortar antes del inicio: no modifica nada y lo avisa",
     np.array_equal(antes, e.td.trials) and ("info", "No se aplicó ninguna modificación.") in e.avisos
     and not e.eventos, str(e.avisos))

# C. Validaciones antes de encolar
for etiqueta, modo, a, b, esperado in (
        ("punto A vacío", "Cut From The Start", "", "", "El punto A no puede estar vacío."),
        ("punto A no numérico", "Cut From The Start", "abc", "", "El punto A debe ser un número"),
        ("punto B vacío al interpolar", "Interpolate Interval", 0.5, "", "El punto B no puede estar vacío"),
        ("A igual a B", "Interpolate Interval", 0.5, 0.5, "Los puntos A y B no pueden ser iguales.")):
    e.aplicar(modo, a, b)
    caso(f"C. {etiqueta}: aviso en español y no se encola nada",
         any(t == "error" and esperado in m for t, m in e.avisos) and e.p._apply_handle is None
         and not e.tasks.has_active_tasks(), str(e.avisos[:1]))

# D. Sin señal activa
e = Entorno()
e.store.clear_active_signal()
e.aplicar("Cut From The Start", 0.1)
caso("D. sin señal activa: aviso en español y no se encola nada",
     any(t == "error" and "No hay una señal activa." in m for t, m in e.avisos) and e.p._apply_handle is None,
     str(e.avisos[:1]))

# E. Un segundo Apply mientras calcula
modulo.calcular_modificacion = lento
e = Entorno()
e.aplicar("Interpolate Interval", 0.5, 0.7)
primero = e.p._apply_handle
with contextlib.redirect_stdout(io.StringIO()):
    e.p._load_and_display_trials()  # como si llegara un evento de datos a mitad del cálculo
boton_tras_refresco = e.p.ui.apply_button.isEnabled()
e.aplicar("Cut From The Start", 0.1)
caso("E. un segundo Apply mientras calcula: se rechaza con aviso y no se encola otra tarea",
     e.p._apply_handle is primero and e.tasks.pending_count() == 0
     and any("Ya se está aplicando" in m for _, m in e.avisos) and not boton_tras_refresco,
     f"botón tras refresco habilitado={boton_tras_refresco}")
e.quieto()
caso("E. el avance llega a la barra de estado", any("Aplicando la modificación" in m for m in e.estado),
     str(e.estado[:1]))

# F. Cancelar a mitad (como al cambiar de sección)
e = Entorno()
antes = e.td.trials.copy()
e.aplicar("Interpolate Interval", 0.5, 0.7)
esperar(lambda: e.tasks.has_active_tasks(), 5)
time.sleep(0.2)
e.tasks.cancel_all_from(e.p.meta.id)
with contextlib.redirect_stdout(io.StringIO()):
    e.p.stop()
e.p.widget.hide()
e.quieto()
caso("F. cancelar a mitad: no escribe, no avisa a los plugins y los controles vuelven",
     np.array_equal(antes, e.td.trials) and not e.eventos and e.controles()[1:] == (True, True, True)
     and any("se canceló" in m for m in e.estado), f"estado {e.estado[-1:]}")

# G. Los trials cambian mientras calcula
e = Entorno()
antes = e.td.trials.copy()
e.aplicar("Interpolate Interval", 0.5, 0.7)
with contextlib.redirect_stdout(io.StringIO()):
    e.sd.discard_trial(Path(e.td.source).name, e.td.channel_name, 7)
e.quieto()
caso("G. si se descarta un trial a mitad del cálculo, no se escribe nada y se avisa",
     np.array_equal(antes, e.td.trials) and not e.eventos
     and any(t == "error" and "Los trials cambiaron" in m for t, m in e.avisos), str(e.avisos[:1]))


# H. Falla el cálculo
def revienta(t, trials, *, mode, point_a, point_b=0.0, ctx=None):
    raise MemoryError("Unable to allocate 119. GiB")


modulo.calcular_modificacion = revienta
e = Entorno()
antes = e.td.trials.copy()
e.aplicar("Interpolate Interval", 0.5, 0.7)
e.quieto()
caso("H. si el cálculo falla: aviso en español, trials intactos y controles de vuelta",
     np.array_equal(antes, e.td.trials) and e.controles() == (True, True, True, True)
     and any(t == "error" and m.startswith("No se pudo aplicar la modificación: MemoryError: ")
             for t, m in e.avisos),
     str(e.avisos[:1]))

# I. MainWindow ve el cálculo al cerrar
modulo.calcular_modificacion = lento
e = Entorno()
e.aplicar("Interpolate Interval", 0.5, 0.7)
ventana = types.SimpleNamespace(kernel=e.kernel)
ventana._cancel_all_tasks = types.MethodType(MainWindow._cancel_all_tasks, ventana)
detecta = MainWindow._any_background_worker_running(ventana)
antes = e.td.trials.copy()
MainWindow._stop_all_background_workers(ventana)
e.p.widget = None
e.p.ui = None
with contextlib.redirect_stdout(io.StringIO()):
    esperar(lambda: e.p._apply_handle is None and not e.tasks.has_active_tasks(), 30)
caso("I. al cerrar a mitad, MainWindow detecta el cálculo", detecta is True)
caso("I. tras cancelar no queda nada corriendo ni se escribe nada",
     not e.tasks.has_active_tasks() and np.array_equal(antes, e.td.trials)
     and MainWindow._any_background_worker_running(ventana) is False)
modulo.calcular_modificacion = real

# J. La cola es compartida con los demás plugins
e = Entorno()
otra = e.tasks.submit(otra_tarea_lenta, owner="wavelet_average")
de_la_otra = []
otra.finished.connect(de_la_otra.append)
e.aplicar("Interpolate Interval", 0.5, 0.7)
en_cola = e.tasks.pending_count() == 1 and e.controles() == (False, False, False, False)
e.quieto()
caso("J. detrás de la tarea de otro plugin: espera en cola y después aplica igual",
     en_cola and de_la_otra == ["otra"]
     and np.array_equal(e.td.trials, referencia("Interpolate Interval", 0.5, 0.7), equal_nan=True),
     f"en cola={en_cola}")

e = Entorno()
antes = e.td.trials.copy()
otra = e.tasks.submit(otra_tarea_lenta, owner="wavelet_average")
de_la_otra = []
otra.finished.connect(de_la_otra.append)
e.aplicar("Interpolate Interval", 0.5, 0.7)
e.tasks.cancel_all_from(e.p.meta.id)  # lo que hace MainWindow al cambiar de sección
liberado_ya = e.p._apply_handle is None
esperar(lambda: de_la_otra, 10)
e.quieto()
caso("J. salir de la sección con la modificación en cola: se descarta al instante y la otra tarea sigue",
     liberado_ya and np.array_equal(antes, e.td.trials) and not e.eventos and de_la_otra == ["otra"],
     f"liberado al instante={liberado_ya}")

caso("sin excepciones en los slots", not ERRORES, " | ".join(ERRORES)[:500])

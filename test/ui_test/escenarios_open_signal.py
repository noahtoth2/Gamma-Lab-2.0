"""Escenarios de interfaz de Open Signal con el orquestador.

El Escenario de Calidad 2 del SAD exige que «la lectura corre en el servicio de
tareas, fuera del hilo de la UI». Antes no era así: `open_file_dialog` llamaba a
`load_abf` directo y la interfaz quedaba bloqueada durante la lectura. Estos
escenarios verifican la migración.

Se ejecuta en un proceso aparte desde test_plugins_con_orquestador.py, porque
necesita una QApplication con widgets y el resto de la suite usa QCoreApplication.
Imprime una línea "CASO|OK|nombre|detalle" por comprobación.
"""
import os
import sys
import threading
import time
import traceback
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.chdir(REPO)

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication

app = QApplication([])
ERRORES = []
sys.excepthook = lambda t, v, tb: ERRORES.append("".join(traceback.format_exception(t, v, tb)))

from core.kernel import Kernel
from core.plugins.meta import PluginMeta
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService
from core.services.task_service import TaskService
from plugins.io.open_signal import compute as co
from plugins.io.open_signal.open_signal_plugin import OpenSignalPlugin

ABF = REPO / "test" / "data" / "17308005.abf"


def caso(nombre, ok, detalle=""):
    print(f"CASO|{'OK' if ok else 'FALLA'}|{nombre}|{detalle}".replace("\n", " "), flush=True)


def esperar(pred, t=60):
    fin = time.monotonic() + t
    while time.monotonic() < fin:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.005)
    app.processEvents()
    return pred()


kernel = Kernel()
store = DataStore()
tasks = TaskService()
kernel.register_service("DataStore", store)
kernel.register_service("FileIO", FileIOService())
kernel.register_service("TaskService", tasks)

meta = PluginMeta(id="open_signal", name="Open Signal", category="io", subcategory="signal",
                  version="0", icon="", logic_class="OpenSignalPlugin")
plug = OpenSignalPlugin(meta)
kernel.register_plugin(meta.name, plug)

# Sin pantalla no hay OpenGL: se sustituye todo el dibujo.
plug._ensure_vtk = lambda: None
DATASETS, AVISOS = [], []
plug._set_dataset = lambda ds: DATASETS.append(ds)
plug.vtk_menu = types.SimpleNamespace(set_signal_name=lambda *_: None)
for tipo in ("info", "error", "warning"):
    setattr(plug.alerts, tipo, lambda msg, *a, _t=tipo: AVISOS.append((_t, msg)))
plug.get_widget(None)

# El dialogo de archivos no se puede abrir sin usuario: se sustituye por la ruta.
ruta_elegida = [str(ABF)]
QtWidgets.QFileDialog.getOpenFileName = staticmethod(
    lambda *a, **k: (ruta_elegida[0], ""))

# Se anota en que hilo corre la lectura.
HILOS = []
lectura_real = co.cargar_senal


def lectura_anotada(ctx, ruta, fileio=None):
    HILOS.append(threading.current_thread().name)
    return lectura_real(ctx, ruta, fileio=fileio)


co.cargar_senal = lectura_anotada


def reposo():
    return (not plug._cargando and plug._load_handle is None
            and not tasks.has_active_tasks())


# A. Carga normal
caso("A. arranca en reposo", reposo())
plug.open_file_dialog()
caso("A. queda marcado como cargando en cuanto encola", plug._cargando is True)
ok_fin = esperar(lambda: len(DATASETS) == 1 and reposo())
caso("A. carga el archivo y vuelve a reposo", ok_fin, f"datasets={len(DATASETS)}")
caso("A. la senal quedo en el DataStore",
     store.get_active_signal() is not None and store.has("17308005.abf"))
caso("A. la senal tiene la forma esperada",
     DATASETS and DATASETS[0].signals.shape == (2, 1800000),
     str(DATASETS[0].signals.shape) if DATASETS else "sin dataset")

# B. Lo que pide el SAD: la lectura no corre en el hilo de la interfaz
caso("B. la lectura corre fuera del hilo principal",
     bool(HILOS) and all(h != "MainThread" for h in HILOS), str(HILOS))

# C. Formato no soportado: ni siquiera encola
ruta_elegida[0] = str(REPO / "test" / "data" / "wavelet_data_matlab.csv")
antes = len(DATASETS)
plug.open_file_dialog()
caso("C. un formato no soportado no encola nada",
     reposo() and len(DATASETS) == antes and len(HILOS) == 1, f"hilos={HILOS}")

# D. Archivo inexistente: el fallo llega por `failed` y no tumba nada
ruta_elegida[0] = str(REPO / "test" / "data" / "no_existe.abf")
mensajes = []
QtWidgets.QMessageBox.warning = staticmethod(
    lambda *a, **k: mensajes.append(a[2] if len(a) > 2 else ""))
plug.open_file_dialog()
caso("D. un archivo ilegible avisa y vuelve a reposo",
     esperar(lambda: bool(mensajes) and reposo()) and len(DATASETS) == antes,
     str(mensajes[:1]))

# E. Cancelar a mitad no deja nada a medias
ruta_elegida[0] = str(ABF)
antes = len(DATASETS)
plug.open_file_dialog()
tasks.cancel_all_from(meta.id)
caso("E. cancelar vuelve a reposo", esperar(reposo))

# F. La interfaz desaparece antes de que llegue el resultado
ruta_elegida[0] = str(ABF)
antes = len(DATASETS)
plug.open_file_dialog()
esperar(lambda: plug._cargando)
plug.ui = None
caso("F. resultado tardio sin interfaz: se descarta sin errores",
     esperar(reposo) and len(DATASETS) == antes and not ERRORES)

caso("sin excepciones en los slots", not ERRORES, " | ".join(ERRORES)[:400])

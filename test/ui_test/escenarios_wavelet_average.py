"""Escenarios de interfaz de Wavelet Average con el orquestador (Fase 3).

Se ejecuta en un proceso aparte desde test_plugins_con_orquestador.py, porque
necesita una QApplication con widgets y el resto de la suite usa QCoreApplication.
Imprime una línea "CASO|OK|nombre|detalle" (o "CASO|FALLA|...") por comprobación.
El dibujo de VTK se sustituye: sin pantalla no hay OpenGL.
"""
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
from core.model.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService
from core.services.task_service import TaskService
from app.view.main_window import MainWindow
from plugins.analysis.time_frequency.wavelet_average import compute as cw
from plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin import Wavelet_average_plugin

N_TRIALS = 3


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


sd = FileIOService().load_abf(str(REPO / "test" / "data" / "17308005.abf"))
td_real = tr.cut_trials_single_channel(
    ds=sd, channel=0, stim_channel=1, threshold=0.7, t0=-0.05, t1=4.00,
    end_mode="until_next_onset", stim_expected=1, inter_stim_time=0.0, pad_value=0.0, debug=False)
X = np.nan_to_num(np.asarray(td_real.trials, dtype=np.float64))
t_rel = np.asarray(td_real.time_rel, dtype=np.float64)
td = TrialDataset(source="17308005.abf", sampling_rate=td_real.sampling_rate, channel_index=0, channel_name="CA1",
                  unit="mV", t0=-0.05, t1=3.0, time_rel=t_rel, trials=np.ascontiguousarray(X[:, :N_TRIALS]),
                  onsets_s=[])
senal = types.SimpleNamespace(name="17308005.abf")

kernel = Kernel()
kernel.register_service("DataStore", DataStore())
tasks = TaskService()
kernel.register_service("TaskService", tasks)
meta = PluginMeta(id="wavelet_average", name="Wavelet Average", category="analysis", subcategory="time_frequency",
                  version="0", icon="", logic_class="Wavelet_average_plugin")
plug = Wavelet_average_plugin(meta)
kernel.register_plugin(meta.name, plug)

RENDERS, AVISOS = [], []
plug._create_vtk_container = lambda: None
plug.ensure_vtk = lambda: None
plug.render_scalogram = lambda t, f, S, titulo, esc: RENDERS.append(S.shape)
for tipo in ("info", "error", "warning"):
    setattr(plug.alerts, tipo, lambda msg, *a, _t=tipo: AVISOS.append((_t, msg)))
plug.get_active_signal = lambda silent=False: senal
plug.active_signal = senal
plug.get_active_trials = lambda signal=None: td
plug.get_widget(None)


def boton():
    b = plug.ui.createWaveletButton
    return b.isEnabled(), b.text()


def reposo():
    return (not plug._calculando and plug._handle is None and not tasks.has_active_tasks()
            and (plug.ui is None or boton() == (True, "Generate")))


# A. Cálculo normal
plug.on_create_wavelet()
durante = boton()
esperar(lambda: len(RENDERS) == 1)
caso("A. botón bloqueado mientras calcula", durante == (False, "Computing..."), str(durante))
caso("A. dibuja una vez con la forma correcta y vuelve a reposo",
     RENDERS == [(998, 3051)] and esperar(reposo), f"renders={RENDERS} botón={boton()}")

# B. Clear durante el cálculo
plug.ui.cyclesSpinBox.setValue(3)
AVISOS.clear()
plug.on_create_wavelet()
esperar(lambda: plug._calculando)
plug._on_clear_clicked()
bloqueado = plug.ui.cyclesSpinBox.value() == 3 and any("en curso" in m for _, m in AVISOS)
esperar(lambda: len(RENDERS) == 2 and reposo())
plug._on_clear_clicked()
caso("B. Clear mientras calcula: avisa y no toca los parámetros", bloqueado, str(AVISOS[:1]))
caso("B. Clear después: restablece los parámetros", plug.ui.cyclesSpinBox.value() == 2)

# C. Cancelación a mitad (como al cambiar de sección)
n = len(RENDERS)
plug.on_create_wavelet()
esperar(lambda: plug._calculando and tasks.has_active_tasks())
time.sleep(0.2)
tasks.cancel_all_from(meta.id)
caso("C. cancelar a mitad: vuelve a reposo sin dibujar", esperar(reposo) and len(RENDERS) == n, f"botón={boton()}")

# D. Falla un trial
orig = cw.compute_wavelet
llamadas = {"n": 0}


def falla_en_el_2(*a, **k):
    llamadas["n"] += 1
    if llamadas["n"] == 2:
        raise MemoryError("Unable to allocate 119. GiB")
    return orig(*a, **k)


cw.compute_wavelet = falla_en_el_2
AVISOS.clear()
plug.on_create_wavelet()
esperar(lambda: any(t == "error" for t, _ in AVISOS))
cw.compute_wavelet = orig
errores = [m for t, m in AVISOS if t == "error"]
caso("D. falla un trial: aviso en español con el número del trial",
     bool(errores) and f"Falló el trial 2 de {N_TRIALS} trials activos" in errores[0],
     errores[0] if errores else "sin aviso")
caso("D. falla un trial: no dibuja y el botón vuelve a quedar disponible", esperar(reposo) and len(RENDERS) == n)

# E. Cerrar el proyecto a mitad, como hace MainWindow
ventana = types.SimpleNamespace(kernel=kernel)
ventana._cancel_all_tasks = types.MethodType(MainWindow._cancel_all_tasks, ventana)
plug.on_create_wavelet()
esperar(lambda: plug._calculando and tasks.has_active_tasks())
caso("E. MainWindow detecta el cálculo en curso", MainWindow._any_background_worker_running(ventana) is True)
MainWindow._stop_all_background_workers(ventana)
plug.widget = None
plug.ui = None
caso("E. cerrar el proyecto a mitad: sin errores, sin dibujar y vuelve a reposo",
     esperar(reposo) and len(RENDERS) == n and not ERRORES)
caso("E. MainWindow ya no ve nada corriendo", MainWindow._any_background_worker_running(ventana) is False)

# E2. El plugin sigue funcionando después de cerrar el proyecto
plug.get_widget(None)
plug.on_create_wavelet()
caso("E2. se puede volver a calcular tras cerrar el proyecto",
     esperar(lambda: len(RENDERS) == n + 1) and esperar(reposo))
n = len(RENDERS)

# F. La interfaz desaparece sin cancelar la tarea: el resultado llega y se descarta sin fallar
plug.on_create_wavelet()
esperar(lambda: plug._calculando)
plug.widget = None
plug.ui = None
caso("F. resultado tardío sin interfaz: se descarta sin errores",
     esperar(reposo) and len(RENDERS) == n and not ERRORES)
plug.get_widget(None)

# G. Relanzar mientras calcula: la señal de la tarea vieja no altera la nueva
plug.on_create_wavelet()
esperar(lambda: tasks.has_active_tasks())
vieja = plug._handle
visto = {}
vieja.cancelled.connect(lambda: visto.setdefault("estado", (plug._calculando, boton())))
plug.on_create_wavelet()
esperar(lambda: "estado" in visto)
caso("G. la cancelación de la tarea vieja no reactiva el botón de la nueva",
     visto.get("estado") == (True, (False, "Computing...")), str(visto.get("estado")))
caso("G. solo dibuja el resultado de la tarea nueva",
     esperar(lambda: len(RENDERS) == n + 1) and esperar(reposo) and len(RENDERS) == n + 1)

caso("sin excepciones en los slots", not ERRORES, " | ".join(ERRORES)[:500])

"""Mide en este equipo los requisitos de rendimiento de GammaLab 2.0 y los compara con su límite.

Uso, desde la carpeta del proyecto:   python installer/medir_equipo.py
Requiere una pantalla real (VTK no funciona sin ella). Imprime una tabla y devuelve 0 si todo cumple.
Usa una señal sintética (3 canales de 180 s a 10 kHz y 50 trials), de modo que no necesita archivos.
"""
import os
import statistics
import sys
import tempfile
import time
from functools import partial
from pathlib import Path

T_INICIO = time.perf_counter()
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

import numpy as np
import vtk
from PyQt5.QtCore import QCoreApplication, QTimer, Qt
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
QMessageBox.exec_ = lambda self: QMessageBox.Ok

from app.view.main_window import MainWindow
from core.filters.trials import cut_trials_single_channel
from core.kernel import Kernel
from core.model.signal_dataset import SignalDataset
from core.plugins.manager import PluginManager
from core.services.compartidos import registrar_servicios_compartidos
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService
from core.services.task_service import TaskService
from core.utils.plugin_alerts import PluginAlerts
from core.utils.vtk_context_menu import VTKContextMenu

for nivel in ("info", "warning", "error"):
    setattr(PluginAlerts, nivel, lambda self, *a, **k: None)

RESULTADOS = []


def anotar(req, que, valor, limite, unidad, minimo=False):
    ok = valor >= limite if minimo else valor <= limite
    RESULTADOS.append((req, que, valor, limite, unidad, minimo, ok))


def esperar(plugin, limite=300):
    t0 = time.time()
    while time.time() - t0 < limite:
        app.processEvents()
        time.sleep(0.002)
        if not getattr(plugin, "_calculando", False) and time.time() - t0 > 0.3:
            break
    for _ in range(20):
        app.processEvents()


kernel = Kernel()
kernel.register_service("DataStore", DataStore())
kernel.register_service("FileIO", FileIOService())
kernel.register_service("TaskService", TaskService())
registrar_servicios_compartidos(kernel)
VTKContextMenu.kernel = kernel
gestor = PluginManager(Path("plugins"))
gestor.load_all()
for meta, plugin in gestor.all():
    kernel.register_plugin(meta.name, plugin)
ventana = MainWindow(kernel)
kernel.register_service("MainWindow", ventana)
ventana.show()
for _ in range(20):
    app.processEvents()
anotar("R81", "Aplicación lista para usarse", time.perf_counter() - T_INICIO, 8.0, "s")

fs, n_tr = 10000.0, 50
n = int(fs * (3.2 * n_tr + 4))
t = np.arange(n) / fs
rng = np.random.default_rng(1)
canales = [np.sin(2 * np.pi * f * t) + 0.3 * rng.standard_normal(n) for f in (5, 8, 13)]
estimulo = np.zeros(n)
for i in range(n_tr):
    estimulo[int((1 + 3.2 * i) * fs): int((1 + 3.2 * i) * fs) + 20] = 1.0
senal = SignalDataset(name="medicion.abf", format="abf", source_path="C:/medicion.abf", sampling_rate=fs, time=t,
                      signals=np.vstack(canales + [estimulo]), channel_names=["a", "b", "c", "estimulo"],
                      units=["mV"] * 3 + ["V"])
almacen = kernel.get_service("DataStore")
almacen.set_active_signal(almacen.add_signal(senal, senal.name))
params = dict(channel=0, stim_channel=3, threshold=0.5, t0=0.0, t1=3.05, end_mode="fixed",
              stim_expected=None, inter_stim_time=None)
trials = cut_trials_single_channel(ds=senal, **params, debug=False)
trials.metadata["generation_params"] = params
senal.add_trial_dataset(trials)

# R49: tres canales dibujados, zoom con la rueda y desplazamiento arrastrando
ventana.on_button_click("Open Signal")
abrir = kernel.get_plugin("Open Signal")
abrir._set_dataset(senal)
for _ in range(30):
    app.processEvents()


def cuadros(plugin, tipo, pasos=24):
    interactor = plugin.vtk_interactor
    ventana_vtk = interactor.GetRenderWindow()
    iren = ventana_vtk.GetInteractor()
    ancho, alto = interactor.width(), interactor.height()
    tiempos = []
    for i in range(pasos):
        x, y = int(ancho * 0.5), int(alto * 0.85)
        t0 = time.perf_counter()
        if tipo == "zoom":
            iren.SetEventInformation(x, y, 0, 0, "0", 0, "")
            iren.InvokeEvent("MouseWheelForwardEvent" if i < pasos // 2 else "MouseWheelBackwardEvent")
        else:
            dx = 6 * (1 if i < pasos // 2 else -1)
            iren.SetEventInformation(x + dx * i, y, 0, 0, "0", 0, "")
            if i == 0:
                iren.InvokeEvent("LeftButtonPressEvent")
            iren.InvokeEvent("MouseMoveEvent")
            if i == pasos - 1:
                iren.InvokeEvent("LeftButtonReleaseEvent")
        ventana_vtk.Render()
        app.processEvents()
        tiempos.append(time.perf_counter() - t0)
    return tiempos


for tipo, nombre in (("zoom", "zoom"), ("arrastre", "desplazamiento")):
    cuadros(abrir, tipo, 6)
    tiempos = cuadros(abrir, tipo)
    anotar("R49", f"{len(abrir._charts)} canales, {nombre}: mediana", 1 / statistics.median(tiempos), 24.0, "FPS", True)
    anotar("R49", f"{len(abrir._charts)} canales, {nombre}: peor cuadro", 1 / max(tiempos), 24.0, "FPS", True)
    abrir._set_dataset(senal)
    for _ in range(20):
        app.processEvents()

ventana.switch_section("Analysis")

# R56: promedio de 50 trials
ventana.on_button_click("Average")
promedio = kernel.get_plugin("Average")
t0 = time.perf_counter()
promedio._on_calculate_average()
esperar(promedio)
anotar("R56", f"Promedio de {trials.trials.shape[1]} trials", time.perf_counter() - t0, 1.0, "s")

# R50: cambio entre módulos con la señal en memoria
peor = 0.0
for nombre in ("FFT", "Wavelet", "PSD", "FFT", "Wavelet", "Average"):
    t0 = time.perf_counter()
    ventana.on_button_click(nombre)
    app.processEvents()
    peor = max(peor, time.perf_counter() - t0)
anotar("R50", "Cambio de módulo (el más lento de 6)", peor, 0.5, "s")

# R48: Wavelet con los parámetros por defecto
ventana.on_button_click("Wavelet")
wavelet = kernel.get_plugin("Wavelet")
t0 = time.perf_counter()
wavelet.on_create_wavelet()
esperar(wavelet)
anotar("R48", "Wavelet de una señal", time.perf_counter() - t0, 10.0, "s")

# R57 y R51: exportación de imagen y de tablas
carpeta = tempfile.mkdtemp()
destino = [None]
QFileDialog.getSaveFileName = staticmethod(lambda *a, **kw: (destino[0], ""))
exportador = wavelet.vtk_menu.export_service
for formato in ("png", "tiff"):
    destino[0] = os.path.join(carpeta, f"w.{formato}")
    t0 = time.perf_counter()
    exportador.export_image(formato, destino[0])
    anotar("R57", f"Imagen {formato}", time.perf_counter() - t0, 1.0, "s")
destino[0] = os.path.join(carpeta, "w.emf")
t0 = time.perf_counter()
exportador.export_emf(destino[0])
anotar("R57", "Vectorial (emf)", time.perf_counter() - t0, 3.0, "s")
secciones = {"Datos": (["x", "y", "z"], [[float(i), 2.0 * i, 3.0 * i] for i in range(100_000)])}
for formato in ("csv", "xlsx"):
    destino[0] = os.path.join(carpeta, f"t.{formato}")
    t0 = time.perf_counter()
    exportador.export_sections(secciones, formato, destino[0])
    anotar("R51", f"Tabla de 100000 filas en {formato}", time.perf_counter() - t0, 2.0, "s")

# R55: la interfaz sigue respondiendo mientras PAC calcula en segundo plano
ventana.on_button_click("PAC")
pac = kernel.get_plugin("PAC")
ultimo = [time.perf_counter()]
peor_pausa = [0.0]


def latido():
    ahora = time.perf_counter()
    peor_pausa[0] = max(peor_pausa[0], ahora - ultimo[0] - 0.01)
    ultimo[0] = ahora


reloj = QTimer()
reloj.timeout.connect(latido)
reloj.start(10)
for ronda in range(3):
    peor_pausa[0] = 0.0
    pac.on_create_pac()
    t0 = time.time()
    while getattr(pac, "_calculando", False) and time.time() - t0 < 300:
        app.processEvents()
        time.sleep(0.002)
    for _ in range(30):
        app.processEvents()
    anotar("R55", "Peor pausa durante PAC, " + ("primera vez" if ronda == 0 else f"ronda {ronda + 1}"), peor_pausa[0], 0.3, "s")
reloj.stop()

# R53: cierre
ventana._confirm_discard_unsaved_changes = lambda: True
t0 = time.perf_counter()
ventana.close()
app.processEvents()
anotar("R53", "Cierre de la ventana", time.perf_counter() - t0, 3.0, "s")

print("\nRequisito  Medida                                          Valor      Límite     Resultado")
for req, que, valor, limite, unidad, minimo, ok in RESULTADOS:
    signo = ">=" if minimo else "<="
    print(f"{req:<9}  {que:<46}  {valor:8.2f}   {signo} {limite:<5g} {unidad:<3}  {'CUMPLE' if ok else 'NO CUMPLE'}")
no_cumplen = [r for r in RESULTADOS if not r[-1]]
print(f"\n{len(RESULTADOS) - len(no_cumplen)} de {len(RESULTADOS)} medidas cumplen su límite.", flush=True)
os._exit(1 if no_cumplen else 0)

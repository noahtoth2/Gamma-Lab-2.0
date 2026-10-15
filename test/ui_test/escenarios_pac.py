"""Escenarios de interfaz del plugin PAC con el orquestador (Fase 5 del plan).

Se ejecuta en un proceso aparte desde test_plugins_con_orquestador.py, porque
necesita una QApplication con widgets y el resto de la suite usa QCoreApplication.
Imprime una línea "CASO|OK|nombre|detalle" por comprobación.
El dibujo de VTK se sustituye: sin pantalla no hay OpenGL.
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

import numpy as np
import vtk
from PyQt5.QtWidgets import QApplication

app = QApplication([])
ERRORES = []
sys.excepthook = lambda t, v, tb: ERRORES.append("".join(traceback.format_exception(t, v, tb)))

from core.kernel import Kernel
from core.model.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from core.services.data_store import DataStore
from core.services.task_service import TaskService
from plugins.analysis.time_frequency.pac import compute as cp
from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin

N_TRIALS = 4
FS = 1000.0
N = 2000


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


# Señal con acoplamiento: gamma de 60 Hz más fuerte en el pico del theta de 5 Hz
t_rel = np.arange(N) / FS
lento = np.cos(2 * np.pi * 5 * t_rel)
base = lento + 0.4 * ((1.0 + lento) / 2.0) * np.sin(2 * np.pi * 60 * t_rel)
rng = np.random.default_rng(0)
X = np.column_stack([base + 0.05 * rng.standard_normal(N) for _ in range(N_TRIALS)])

td = TrialDataset(source="sintetico.abf", sampling_rate=FS, channel_index=0,
                  channel_name="CA1", unit="mV", t0=0.0, t1=N / FS,
                  time_rel=t_rel, trials=np.ascontiguousarray(X), onsets_s=[])
senal = types.SimpleNamespace(name="sintetico.abf")

kernel = Kernel()
kernel.register_service("DataStore", DataStore())
tasks = TaskService()
kernel.register_service("TaskService", tasks)
meta = PluginMeta(id="pac", name="PAC", category="analysis", subcategory="time_frequency",
                  version="0", icon="", logic_class="Pac_plugin")
plug = Pac_plugin(meta)
kernel.register_plugin(meta.name, plug)

DIBUJOS, AVISOS = [], []
plug.ensure_vtk = lambda: None
plug.render_resultado = lambda r, titulo="PAC": DIBUJOS.append((titulo, r))
plug.render_psel = lambda r: DIBUJOS.append(("PAC Psel", r))
for tipo in ("info", "error", "warning"):
    setattr(plug.alerts, tipo, lambda msg, *a, _t=tipo: AVISOS.append((_t, msg)))
plug.get_active_signal = lambda silent=False: senal
plug.active_signal = senal
plug.get_active_trials = lambda signal=None: td
plug.get_widget(None)

# Parámetros que corren rápido (la banda por defecto daría 1.900 frecuencias)
plug.ui.sampleDensitySpinBox.setValue(1000)
plug.ui.ampHighFrequencySpinBox.setValue(100.0)

HILOS = []
calculo_real = cp.pac_un_trial


def anota_hilo(ctx, *a, **k):
    HILOS.append(threading.current_thread().name)
    return calculo_real(ctx, *a, **k)


cp.pac_un_trial = anota_hilo


def boton():
    b = plug.ui.createPacButton
    return b.isEnabled(), b.text()


def reposo():
    return (not plug._calculando and plug._handle is None and not tasks.has_active_tasks()
            and (plug.ui is None or boton() == (True, "Generate")))


# A. El selector de trial
caso("A. el selector conoce cuantos trials hay",
     plug.ui.trialSpinBox.maximum() == N_TRIALS and "de 4" in plug.ui.trialTotalLabel.text(),
     f"max={plug.ui.trialSpinBox.maximum()} texto={plug.ui.trialTotalLabel.text()!r}")
caso("A. empieza en el trial 1, como MATLAB", plug.ui.trialSpinBox.value() == 1)
caso("A. con PAC el selector esta disponible", plug.ui.trialSpinBox.isEnabled())

# B. Cálculo normal
plug.on_create_pac()
durante = boton()
esperar(lambda: len(DIBUJOS) == 1)
caso("B. boton bloqueado mientras calcula", durante == (False, "Computing..."), str(durante))
caso("B. dibuja una vez y vuelve a reposo", len(DIBUJOS) == 1 and esperar(reposo))
caso("B. el calculo corre fuera del hilo principal",
     bool(HILOS) and all(h != "MainThread" for h in HILOS), str(HILOS))

r = DIBUJOS[0][1]
caso("B. el resultado trae el mapa y el vector",
     r.mapa.shape == (int(round(4 * (100 - 25))), 100) and isinstance(r.vector, complex),
     f"mapa={r.mapa.shape}")
caso("B. encuentra el acoplamiento donde se construyo",
     abs(np.angle(r.vector)) < 0.5, f"angulo={np.angle(r.vector):+.3f} rad")

# C. Las flechas navegan y recalculan
antes = len(DIBUJOS)
plug.ui.nextTrialButton.click()
caso("C. la flecha avanza al trial 2", plug.ui.trialSpinBox.value() == 2)
caso("C. y relanza el calculo solo", esperar(lambda: len(DIBUJOS) == antes + 1 and reposo()))
plug.ui.prevTrialButton.click()
esperar(reposo)
caso("C. la flecha atras vuelve al 1", plug.ui.trialSpinBox.value() == 1)

# D. No se sale del rango
plug.ui.trialSpinBox.setValue(N_TRIALS)
n = len(DIBUJOS)
plug.ui.nextTrialButton.click()
caso("D. en el ultimo trial la flecha adelante no hace nada",
     plug.ui.trialSpinBox.value() == N_TRIALS and len(DIBUJOS) == n)
plug.ui.trialSpinBox.setValue(1)
plug.ui.prevTrialButton.click()
caso("D. en el primero la flecha atras no hace nada", plug.ui.trialSpinBox.value() == 1)

# E. PAC Average usa todos los trials y apaga el selector
plug.ui.pacTypeComboBox.setCurrentIndex(1)
caso("E. con Average el selector se deshabilita",
     not plug.ui.trialSpinBox.isEnabled() and "todos" in plug.ui.trialTotalLabel.text(),
     plug.ui.trialTotalLabel.text())
n = len(DIBUJOS)
plug.on_create_pac()
caso("E. el promedio usa los cuatro trials",
     esperar(lambda: len(DIBUJOS) == n + 1 and reposo()) and DIBUJOS[-1][1].n_trials == N_TRIALS,
     f"n_trials={DIBUJOS[-1][1].n_trials}")
plug.ui.pacTypeComboBox.setCurrentIndex(0)

# F. PAC Psel: concatena los trials, detecta ciclos y dibuja sus 13 paneles
AVISOS.clear()
plug.ui.pacTypeComboBox.setCurrentIndex(2)
caso("F. con Psel el selector de trial se deshabilita",
     not plug.ui.trialSpinBox.isEnabled(), plug.ui.trialTotalLabel.text())
# Barrido corto a proposito: con el de fabrica son 950 filas y el escenario
# tardaria demasiado. Lo que se prueba aqui es el camino, no el barrido.
plug.ui.ampLowFrequencySpinBox.setValue(25.0)
plug.ui.ampHighFrequencySpinBox.setValue(60.0)
n = len(DIBUJOS)
plug.on_create_pac()
caso("F. Psel calcula y vuelve a reposo",
     esperar(lambda: len(DIBUJOS) == n + 1 and reposo(), t=180) and DIBUJOS[-1][0] == "PAC Psel",
     f"ultimo dibujo = {DIBUJOS[-1][0]!r}")
caso("F. no abrio ninguna ventana de aviso", not AVISOS, str([m[:50] for _, m in AVISOS]))

rp = DIBUJOS[-1][1]
caso("F. detecto ciclos en la senal concatenada",
     rp.n_ciclos > 5, f"{rp.n_ciclos} ciclos, {rp.ciclos_descartados} descartados")
caso("F. el mapa tiene una fila por frecuencia y 100 bins de fase",
     rp.mapa.shape == (rp.frecuencias.size, 100), str(rp.mapa.shape))
caso("F. usa dos filas por Hz, no cuatro como PAC",
     rp.frecuencias.size == int(cp.FILAS_POR_HZ_PSEL * (60.0 - 25.0)), str(rp.frecuencias.size))
caso("F. devuelve los 16 vectores por grupo de bins",
     rp.vectores_por_grupo.shape == (16,), str(rp.vectores_por_grupo.shape))
caso("F. encuentra acoplamiento", abs(rp.vector) > 0.1 and np.isfinite(abs(rp.vector)),
     f"magnitud {abs(rp.vector):.4f}, fase {np.angle(rp.vector):+.3f} rad")

# F bis. Los graficos propios de Psel. No se renderiza —sin pantalla no hay
# OpenGL—, pero construirlos ya comprueba ejes, marcas y numero de trazas.
mapa_log = plug._grafico_mapa_log(rp.mapa, rp.frecuencias, rp.fases, "prueba", "Fase (rad)")
eje_y = mapa_log.GetAxis(vtk.vtkAxis.LEFT)
caso("F bis. el mapa de Psel lleva el eje en logaritmo",
     abs(eje_y.GetMinimum() - np.log10(25.0)) < 1e-9
     and abs(eje_y.GetMaximum() - np.log10(60.0)) < 1e-9,
     f"{eje_y.GetMinimum():.4f} a {eje_y.GetMaximum():.4f}")
_pos, _lab = eje_y.GetTickPositions(), eje_y.GetTickLabels()
_marcas = [(_pos.GetValue(i), _lab.GetValue(i)) for i in range(_pos.GetNumberOfTuples())]
caso("F bis. con las marcas de MATLAB, etiquetadas en Hz",
     _marcas == [(1.5, "32")], str(_marcas))

_pila = plug._grafico_ciclos(rp.ciclos_theta, rp.promedio_theta, "ciclos", (200, 30, 30))
caso("F bis. la pila de ciclos dibuja cada ciclo mas el promedio",
     _pila.GetNumberOfPlots() == rp.n_ciclos + 1,
     f"{_pila.GetNumberOfPlots()} trazas para {rp.n_ciclos} ciclos")
_muchos = np.zeros((50, 900))
caso("F bis. y se limita cuando hay cientos de ciclos",
     plug._grafico_ciclos(_muchos, _muchos.mean(axis=1), "x", (0, 0, 0)).GetNumberOfPlots()
     == plug.MAX_TRAZAS_CICLOS + 1)

_b2 = plug._grafico_brujula(rp, extra=rp.vectores_por_grupo)
caso("F bis. la segunda brujula suma los 16 vectores por grupo",
     _b2.GetNumberOfPlots() == plug._grafico_brujula(rp).GetNumberOfPlots() + 16,
     str(_b2.GetNumberOfPlots()))

plug.ui.ampLowFrequencySpinBox.setValue(25.0)
plug.ui.ampHighFrequencySpinBox.setValue(500.0)
plug.ui.pacTypeComboBox.setCurrentIndex(0)

# G. Parametros invalidos: avisa en español, no revienta
AVISOS.clear()
plug.ui.lowFrequencySpinBox.setValue(20.0)
plug.ui.highFrequencySpinBox.setValue(5.0)
plug.on_create_pac()
esperar(lambda: any(t == "error" for t, _ in AVISOS))
errores = [m for t, m in AVISOS if t == "error"]
caso("G. una banda al reves avisa en espanol",
     bool(errores) and "alta de fase" in errores[0], errores[0] if errores else "sin aviso")
caso("G. y vuelve a reposo", esperar(reposo))
plug.ui.lowFrequencySpinBox.setValue(3.0)
plug.ui.highFrequencySpinBox.setValue(8.0)

# H. Clear durante el cálculo
plug.ui.ampLowFrequencySpinBox.setValue(30.0)
AVISOS.clear()
plug.on_create_pac()
esperar(lambda: plug._calculando)
plug._on_clear_clicked()
bloqueado = plug.ui.ampLowFrequencySpinBox.value() == 30.0 and any("en curso" in m for _, m in AVISOS)
esperar(reposo)
caso("H. Clear mientras calcula avisa y no toca los parametros", bloqueado, str(AVISOS[:1]))

# I. Cancelación y cierre a mitad
n = len(DIBUJOS)
plug.on_create_pac()
esperar(lambda: tasks.has_active_tasks())
tasks.cancel_all_from(meta.id)
caso("I. cancelar vuelve a reposo sin dibujar", esperar(reposo) and len(DIBUJOS) == n)

plug.on_create_pac()
esperar(lambda: plug._calculando)
plug.widget = None
plug.ui = None
caso("I. resultado tardio sin interfaz: se descarta sin errores",
     esperar(reposo) and len(DIBUJOS) == n and not ERRORES)

# J. Los parámetros se guardan y se restauran
plug.get_widget(None)
plug.ensure_vtk = lambda: None
plug.render_resultado = lambda r, titulo="PAC": DIBUJOS.append((titulo, r))
plug.render_psel = lambda r: DIBUJOS.append(("PAC Psel", r))
plug.ui.sampleDensitySpinBox.setValue(1000)
plug.ui.ampHighFrequencySpinBox.setValue(100.0)
plug.ui.trialSpinBox.setValue(3)
guardados = plug.get_analysis_params()
caso("J. get_analysis_params incluye el trial y el tipo",
     guardados.get("trial") == 3 and guardados.get("pac_type") == "PAC", str(guardados))

# K. La brújula: el vector medio dibujado como la `compass` de MATLAB
def brujula_de(valor):
    return plug._grafico_brujula(types.SimpleNamespace(vector=valor))


def punta_de(chart):
    """El plot 4 es la flecha: 0 y 1 son los circulos, 2 y 3 los ejes."""
    tabla = chart.GetPlot(4).GetInput()
    return (tabla.GetValue(1, 0).ToDouble(), tabla.GetValue(1, 1).ToDouble(),
            tabla.GetValue(0, 0).ToDouble(), tabla.GetValue(0, 1).ToDouble())


ch = brujula_de(complex(3.0, 4.0))
caso("K. la brujula dibuja circulos, ejes, flecha y punta",
     ch.GetNumberOfPlots() == 7, f"{ch.GetNumberOfPlots()} trazos")
caso("K. el radio es el de MATLAB: el mayor entre |real| e |imag|",
     abs(ch.GetAxis(0).GetMaximum() - 1.15 * 4.0) < 1e-9,
     f"rango hasta {ch.GetAxis(0).GetMaximum():.3f}")

bien = []
for grados in (0, 45, 90, 180, -90):
    v = complex(2.0 * np.exp(1j * np.deg2rad(grados)))
    x, y, x0, y0 = punta_de(brujula_de(v))
    medido = np.rad2deg(np.arctan2(y, x))
    bien.append(abs(((medido - grados + 180) % 360) - 180) < 1e-6
                and abs(np.hypot(x, y) - 2.0) < 1e-9
                and (x0, y0) == (0.0, 0.0))
caso("K. la flecha sale del origen y apunta a la fase correcta", all(bien), str(bien))

caso("K. un vector nulo no revienta la escala",
     brujula_de(complex(0.0, 0.0)).GetAxis(0).GetMaximum() > 0)

caso("K. los ejes quedan simetricos y cuadrados",
     all(abs(brujula_de(complex(1.0, -3.0)).GetAxis(e).GetMinimum()
             + brujula_de(complex(1.0, -3.0)).GetAxis(e).GetMaximum()) < 1e-9
         for e in (0, 1)))

caso("sin excepciones en los slots", not ERRORES, " | ".join(ERRORES)[:400])

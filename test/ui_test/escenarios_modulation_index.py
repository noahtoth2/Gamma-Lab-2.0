"""Escenarios de interfaz del plugin Modulation Index con el orquestador.

Se ejecuta en un proceso aparte desde test_plugins_con_orquestador.py.
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
from PyQt5.QtWidgets import QApplication

app = QApplication([])
ERRORES = []
sys.excepthook = lambda t, v, tb: ERRORES.append("".join(traceback.format_exception(t, v, tb)))

from core.kernel import Kernel
from core.model.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from core.services.data_store import DataStore
from core.services.task_service import TaskService
from plugins.analysis.time_frequency.modulation_index import compute as cm
from plugins.analysis.time_frequency.modulation_index.modulation_index_plugin import (
    Modulation_index_plugin)

N_TRIALS = 3
FS = 1000.0
# 8 segundos y no 3: MInorm se sesga al alza cuando caben pocos ciclos de la
# banda de fase mas baja. Con 3 s y la fase desde 2 Hz son 6 ciclos, suficiente
# para la fase pero no para que la amplitud salga estable. Con 8 s son 16 y el
# maximo cae exactamente donde se construyo. Medido.
N = 8000


def caso(nombre, ok, detalle=""):
    print(f"CASO|{'OK' if ok else 'FALLA'}|{nombre}|{detalle}".replace("\n", " "), flush=True)


def esperar(pred, t=90):
    fin = time.monotonic() + t
    while time.monotonic() < fin:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.005)
    app.processEvents()
    return pred()


# Acoplamiento que SI cabe en la banda de amplitud de 10 Hz: la modulacion a
# 3,5 Hz crea laterales a +-3,5 de la portadora, y 2*3,5 = 7 < 10.
t_rel = np.arange(N) / FS
lento = np.cos(2 * np.pi * 3.5 * t_rel)
base = lento + 0.5 * ((1 + lento) / 2) * np.sin(2 * np.pi * 75 * t_rel)
rng = np.random.default_rng(0)
X = np.column_stack([base + 0.03 * rng.standard_normal(N) for _ in range(N_TRIALS)])

td = TrialDataset(source="sintetico.abf", sampling_rate=FS, channel_index=0,
                  channel_name="CA1", unit="mV", t0=0.0, t1=N / FS,
                  time_rel=t_rel, trials=np.ascontiguousarray(X), onsets_s=[])
senal = types.SimpleNamespace(name="sintetico.abf")

kernel = Kernel()
kernel.register_service("DataStore", DataStore())
tasks = TaskService()
kernel.register_service("TaskService", tasks)
meta = PluginMeta(id="modulation_index", name="Modulation Index", category="analysis",
                  subcategory="time_frequency", version="0", icon="",
                  logic_class="Modulation_index_plugin")
plug = Modulation_index_plugin(meta)
kernel.register_plugin(meta.name, plug)

DIBUJOS, AVISOS = [], []
plug.ensure_vtk = lambda: None
plug.render_resultado = lambda r, indice=0: DIBUJOS.append((indice, r))
for tipo in ("info", "error", "warning"):
    setattr(plug.alerts, tipo, lambda msg, *a, _t=tipo: AVISOS.append((_t, msg)))
plug.get_active_signal = lambda silent=False: senal
plug.active_signal = senal
plug.get_active_trials = lambda signal=None: td
plug.get_widget(None)

# Barrido chico para que corra rapido, pero con mas de 178 bandas de amplitud.
# La fase arranca en 2 Hz y no en 1: MInorm se sesga al alza cuando caben pocos
# ciclos de la banda mas baja en la senal. Con 3 s, 1 Hz da 3 ciclos y el maximo
# sale en cualquier parte; 2 Hz da 6 y ya es fiable. Medido.
plug.ui.sampleFqSpinBox.setValue(1000)
plug.ui.fqP1SpinBox.setValue(2.0)
plug.ui.fqP2SpinBox.setValue(8.0)
plug.ui.pStepSpinBox.setValue(0.5)
plug.ui.fqA1SpinBox.setValue(30.0)
plug.ui.fqA2SpinBox.setValue(120.0)
plug.ui.aStepSpinBox.setValue(0.5)

HILOS = []
real = cm.comodulograma


def anota_hilo(ctx, *a, **k):
    HILOS.append(threading.current_thread().name)
    return real(ctx, *a, **k)


cm.comodulograma = anota_hilo


def boton():
    b = plug.ui.generateButton
    return b.isEnabled(), b.text()


def reposo():
    return (not plug._calculando and plug._handle is None and not tasks.has_active_tasks()
            and (plug.ui is None or boton() == (True, "Generate")))


# A. Los campos que faltaban
caso("A. tiene campo de frecuencia de muestreo",
     hasattr(plug.ui, "sampleFqSpinBox") and plug.ui.sampleFqSpinBox.value() == 1000)
caso("A. tiene selector de trial con flechas",
     all(hasattr(plug.ui, n) for n in
         ("trialSpinBox", "prevTrialButton", "nextTrialButton", "trialTotalLabel")))
caso("A. el selector conoce cuantos trials hay",
     plug.ui.trialSpinBox.maximum() == N_TRIALS and "de 3" in plug.ui.trialTotalLabel.text(),
     plug.ui.trialTotalLabel.text())
caso("A. empieza en el trial 1, como MATLAB", plug.ui.trialSpinBox.value() == 1)

# B. Cálculo normal
AVISOS.clear()
plug.on_create_mi()
durante = boton()
caso("B. boton bloqueado mientras calcula", durante == (False, "Computing..."), str(durante))
caso("B. calcula y vuelve a reposo", esperar(lambda: len(DIBUJOS) == 1 and reposo()))
caso("B. el calculo corre fuera del hilo principal",
     bool(HILOS) and all(h != "MainThread" for h in HILOS), str(HILOS))

r = DIBUJOS[0][1]
caso("B. el comodulograma tiene la forma correcta",
     r.mi_norm.shape == (r.frecuencias_amplitud.size, r.frecuencias_fase.size),
     f"{r.mi_norm.shape} con {r.frecuencias_amplitud.size} amplitudes "
     f"y {r.frecuencias_fase.size} fases")

# C. El tope de 178 de MATLAB ya no se aplica
caso("C. calcula el barrido entero, sin el tope de 178",
     r.bandas_calculadas == r.frecuencias_amplitud.size == 181,
     f"{r.bandas_calculadas} de {r.frecuencias_amplitud.size}")
caso("C. no queda ninguna fila vacia",
     not np.isnan(r.mi_norm).any(),
     f"{int(np.all(np.isnan(r.mi_norm), axis=1).sum())} filas en NaN")
caso("C. el resultado deja claro que no se uso el tope", r.limite_matlab is False)
caso("C. y no abre ninguna ventana al terminar",
     not AVISOS, str([m[:50] for _, m in AVISOS]))

# D. Encuentra el acoplamiento donde se construyo
m = np.nan_to_num(r.mi_norm)
ia, ip = np.unravel_index(np.argmax(m), m.shape)
caso("D. el maximo cae en la banda de amplitud correcta",
     abs(r.frecuencias_amplitud[ia] - 70.0) <= 6.0,
     f"amplitud {r.frecuencias_amplitud[ia]:.1f} Hz (se construyo 75, banda 70-80)")
caso("D. y en la frecuencia de fase correcta",
     abs(r.frecuencias_fase[ip] - 3.0) <= 1.0,
     f"fase {r.frecuencias_fase[ip]:.1f} Hz (se construyo 3,5, banda 3-4)")

# E. Las flechas navegan y recalculan
antes = len(DIBUJOS)
plug.ui.nextTrialButton.click()
caso("E. la flecha avanza al trial 2", plug.ui.trialSpinBox.value() == 2)
caso("E. y relanza el calculo solo",
     esperar(lambda: len(DIBUJOS) == antes + 1 and reposo()) and DIBUJOS[-1][0] == 1,
     f"indice dibujado={DIBUJOS[-1][0]}")
plug.ui.trialSpinBox.setValue(N_TRIALS)
n = len(DIBUJOS)
plug.ui.nextTrialButton.click()
caso("E. en el ultimo no se pasa de rango",
     plug.ui.trialSpinBox.value() == N_TRIALS and len(DIBUJOS) == n)
plug.ui.trialSpinBox.setValue(1)

# F. Un barrido corto, que con el tope de MATLAB era un error
AVISOS.clear()
n = len(DIBUJOS)
plug.ui.fqA2SpinBox.setValue(50.0)      # de 30 a 50 con paso 0,5 son 41 bandas
plug.on_create_mi()
caso("F. un barrido de 41 bandas ya es valido", esperar(lambda: len(DIBUJOS) == n + 1 and reposo()))
rc = DIBUJOS[-1][1]
caso("F. y se calcula entero, sin errores",
     rc.bandas_calculadas == rc.frecuencias_amplitud.size == 41 and not AVISOS,
     f"{rc.bandas_calculadas} de {rc.frecuencias_amplitud.size}, avisos={len(AVISOS)}")
plug.ui.fqA2SpinBox.setValue(120.0)

# G. Clear durante el cálculo
AVISOS.clear()
plug.ui.pStepSpinBox.setValue(0.4)
plug.on_create_mi()
esperar(lambda: plug._calculando)
plug._on_clear_clicked()
bloqueado = plug.ui.pStepSpinBox.value() == 0.4 and any("en curso" in m for _, m in AVISOS)
esperar(reposo)
caso("G. Clear mientras calcula avisa y no toca los parametros", bloqueado, str(AVISOS[:1]))

# H. Cancelación y cierre a mitad
plug._on_clear_clicked()
plug.ui.sampleFqSpinBox.setValue(1000)
plug.ui.fqP1SpinBox.setValue(2.0)
plug.ui.fqP2SpinBox.setValue(8.0)
plug.ui.pStepSpinBox.setValue(0.5)
plug.ui.fqA1SpinBox.setValue(30.0)
plug.ui.fqA2SpinBox.setValue(120.0)
plug.ui.aStepSpinBox.setValue(0.5)
n = len(DIBUJOS)
plug.on_create_mi()
esperar(lambda: tasks.has_active_tasks())
tasks.cancel_all_from(meta.id)
caso("H. cancelar vuelve a reposo sin dibujar", esperar(reposo) and len(DIBUJOS) == n)

plug.on_create_mi()
esperar(lambda: plug._calculando)
plug.widget = None
plug.ui = None
caso("H. resultado tardio sin interfaz: se descarta sin errores",
     esperar(reposo) and len(DIBUJOS) == n and not ERRORES)

# I. Los parámetros se guardan
plug.get_widget(None)
plug.ui.trialSpinBox.setValue(2)
guardados = plug.get_analysis_params()
caso("I. get_analysis_params incluye el muestreo, los pasos y el trial",
     all(k in guardados for k in ("sample_fq", "p_step", "a_step", "trial"))
     and guardados["trial"] == 2, str(guardados))


# J. Los NaN se dibujan transparentes, como imagesc
# El grafico no se puede inspeccionar despues (vtkChartHistogram2D no expone
# getters), asi que se capturan los objetos que el plugin crea al vuelo.
import dataclasses

import vtk as _vtk
from vtkmodules.util import numpy_support as _ns

# El barrido entero ya no deja NaN, asi que se fabrica uno que si los tenga:
# es el caso real cuando el Nyquist recorta las bandas de arriba.
_mi = r.mi_norm.copy()
_mi[-3:] = np.nan
_con_nan = dataclasses.replace(r, mi_norm=_mi, bandas_calculadas=r.bandas_calculadas - 3)

CAPTURA = {}
_lut_real, _img_real = _vtk.vtkColorTransferFunction, _vtk.vtkImageData
_vtk.vtkColorTransferFunction = lambda: CAPTURA.setdefault("lut", _lut_real())
_vtk.vtkImageData = lambda: CAPTURA.setdefault("img", _img_real())
try:
    plug._grafico_comodulograma(_con_nan, 0)
finally:
    _vtk.vtkColorTransferFunction, _vtk.vtkImageData = _lut_real, _img_real

caso("J. los NaN se pintan transparentes y no rellenos",
     CAPTURA["lut"].GetNanOpacity() == 0.0,
     f"opacidad de NaN = {CAPTURA['lut'].GetNanOpacity()}")
caso("J. y del color del fondo, para que se vean en blanco",
     tuple(round(v, 2) for v in CAPTURA["lut"].GetNanColor()) == plug.FONDO,
     str(CAPTURA["lut"].GetNanColor()))
_px = _ns.vtk_to_numpy(CAPTURA["img"].GetPointData().GetScalars())
caso("J. la matriz que llega a VTK conserva los NaN",
     int(np.isnan(_px).sum()) == 3 * r.frecuencias_fase.size,
     f"{int(np.isnan(_px).sum())} NaN de {_px.size} celdas")

# K. Lo que condiciona la lectura va al log, no a una ventana
# Un modal en cada calculo estorbaba, y ademas abre un bucle de eventos anidado
# dentro del cual sigue disparando el temporizador de VTK: las caidas del 7 de
# octubre apuntan ahi (nº 24 de problemas-encontrados.md).
REGISTRO = []
plug._log = lambda *a: REGISTRO.append(" ".join(str(x) for x in a))

AVISOS.clear(); REGISTRO.clear()
plug._avisar_de_los_limites(r)
caso("K. con 16 ciclos y todo calculado no dice nada",
     not REGISTRO and not AVISOS, str(REGISTRO[:1]))

AVISOS.clear(); REGISTRO.clear()
plug._avisar_de_los_limites(dataclasses.replace(r, duracion_s=3.05, ciclos_banda_lenta=0.305))
caso("K. con 0,3 ciclos lo registra", any("ciclos" in m for m in REGISTRO), str(len(REGISTRO)))
caso("K. y dice cuanto subir Fq P1 en vez de solo quejarse",
     any("2.0 Hz" in m for m in REGISTRO), REGISTRO[0][-80:] if REGISTRO else "nada")
caso("K. sin abrir ninguna ventana", not AVISOS, str([m[:40] for _, m in AVISOS]))

AVISOS.clear(); REGISTRO.clear()
plug._avisar_de_los_limites(dataclasses.replace(
    r, bandas_calculadas=120, limite_matlab=False, ciclos_banda_lenta=99.0))
caso("K. si faltan bandas por Nyquist lo dice, y no culpa a MATLAB",
     len(REGISTRO) == 1 and "Nyquist" in REGISTRO[0] and "MATLAB" not in REGISTRO[0],
     REGISTRO[0][:95] if REGISTRO else "nada")

AVISOS.clear(); REGISTRO.clear()
plug._avisar_de_los_limites(dataclasses.replace(
    r, bandas_calculadas=178, limite_matlab=True, ciclos_banda_lenta=99.0))
caso("K. y si alguien pide el tope de MATLAB, lo distingue",
     len(REGISTRO) == 1 and "MATLAB" in REGISTRO[0] and "Nyquist" not in REGISTRO[0],
     REGISTRO[0][:95] if REGISTRO else "nada")

caso("L. la casilla «All bands» ya no existe: el barrido entero es lo normal",
     not hasattr(plug.ui, "allBandsCheckBox")
     and "todas_las_bandas" not in plug.get_analysis_params())

caso("sin excepciones en los slots", not ERRORES, " | ".join(ERRORES)[:400])

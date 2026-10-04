"""Escenarios de la barra de progreso del orquestador (problema nº 9).

Se ejecuta en un proceso aparte desde test_plugins_con_orquestador.py, porque
necesita una QApplication con widgets y el resto de la suite usa QCoreApplication.
Imprime una línea "CASO|OK|nombre|detalle" (o "CASO|FALLA|...") por comprobación.
"""
import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.chdir(REPO)

from PyQt5.QtWidgets import QApplication

app = QApplication([])
ERRORES = []
sys.excepthook = lambda t, v, tb: ERRORES.append("".join(traceback.format_exception(t, v, tb)))

from core.services.task_service import TaskService
from core.utils.task_progress import TaskProgressBar


def caso(nombre, ok, detalle=""):
    print(f"CASO|{'OK' if ok else 'FALLA'}|{nombre}|{detalle}".replace("\n", " "), flush=True)


def esperar(pred, t=20):
    fin = time.monotonic() + t
    while time.monotonic() < fin:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.005)
    app.processEvents()
    return pred()


def tarea_lenta(ctx, pasos=40, espera=0.02):
    """Reporta avance y atiende la cancelación, como wavelet_promedio."""
    for i in range(pasos):
        if ctx.cancelled:
            return "cancelada"
        time.sleep(espera)
        ctx.progress(int(100 * (i + 1) / pasos), f"Paso {i + 1}/{pasos}")
    return "completa"


def tarea_que_revienta(ctx):
    raise MemoryError("Unable to allocate 119. GiB")


tasks = TaskService()
barra = TaskProgressBar()
tasks.task_started.connect(lambda h: barra.seguir(h, "Prueba: calculando…"))

# A. Arranca oculta
caso("A. arranca oculta", not barra.isVisible())

# B. Al encolar una tarea se muestra con porcentaje
resultados = []
h = tasks.submit(tarea_lenta, owner="prueba")
h.finished.connect(resultados.append)
caso("B. se muestra en cuanto se encola la tarea", barra.isVisible())
caso("B. la barra es determinada, no un spinner indeterminado",
     (barra._barra.minimum(), barra._barra.maximum()) == (0, 100),
     f"rango=({barra._barra.minimum()}, {barra._barra.maximum()})")
caso("B. no es modal: no hay ningun dialogo modal abierto",
     app.activeModalWidget() is None)

# C. El porcentaje avanza
esperar(lambda: barra._barra.value() > 20)
intermedio = barra._barra.value()
caso("C. el porcentaje avanza mientras calcula", 0 < intermedio < 100, f"valor={intermedio}")
caso("C. el mensaje del paso llega a la etiqueta",
     "Paso" in barra._etiqueta.text(), barra._etiqueta.text())

# D. Al terminar se oculta
esperar(lambda: resultados and not barra.isVisible())
caso("D. al terminar se oculta", resultados == ["completa"] and not barra.isVisible(),
     f"resultados={resultados} visible={barra.isVisible()}")

# E. El boton Cancelar cancela de verdad
cancelado = []
h2 = tasks.submit(tarea_lenta, owner="prueba")
h2.cancelled.connect(lambda: cancelado.append(True))
esperar(lambda: barra._barra.value() > 10)
caso("E. hay boton Cancelar y esta disponible",
     barra._cancelar.isEnabled() and barra._cancelar.text() == "Cancelar")
barra._cancelar.click()
caso("E. al pulsar Cancelar la tarea se cancela", esperar(lambda: bool(cancelado)))
caso("E. y la barra se oculta", esperar(lambda: not barra.isVisible()))
caso("E. la tarea cancelada no entrega resultado", len(resultados) == 1, str(resultados))

# F. Si la tarea falla, la barra tambien se oculta
fallos = []
h3 = tasks.submit(tarea_que_revienta, owner="prueba")
h3.failed.connect(fallos.append)
esperar(lambda: bool(fallos))
caso("F. si la tarea falla la barra se oculta", esperar(lambda: not barra.isVisible()),
     str(fallos[:1]))

# G. Relanzar: la tarea vieja no mueve la barra de la nueva
h4 = tasks.submit(tarea_lenta, owner="prueba")
esperar(lambda: barra._barra.value() > 30)
alto = barra._barra.value()
h5 = tasks.submit(tarea_lenta, owner="prueba")   # descarta la anterior de ese dueno
caso("G. al relanzar, la barra se reinicia y sigue a la tarea nueva",
     barra._barra.value() < alto and barra._handle is h5,
     f"antes={alto} ahora={barra._barra.value()}")
tasks.cancel_all_from("prueba")
esperar(lambda: not tasks.has_active_tasks())

# H. ocultar() suelta el handle
h6 = tasks.submit(tarea_lenta, owner="prueba")
esperar(lambda: barra.isVisible())
barra.ocultar()
caso("H. ocultar() suelta el handle y no vuelve a mostrarse sola",
     barra._handle is None and esperar(lambda: not barra.isVisible()))
tasks.cancel_all_from("prueba")
esperar(lambda: not tasks.has_active_tasks())

caso("sin excepciones en los slots", not ERRORES, " | ".join(ERRORES)[:500])

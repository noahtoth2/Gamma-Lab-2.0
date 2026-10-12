"""La guarda del temporizador de VTK (nº 24).

Se ejecuta en un proceso aparte desde test_plugins_con_orquestador.py, como los
demás escenarios: necesita una QApplication con widgets.

Lo que se comprueba es que `TimerEvent` **no entre en VTK** cuando el widget no
está en condiciones, que es lo que cerraba la aplicación al cambiar de pestaña.
No se puede comprobar «no se cae» directamente —una violación de acceso mata el
proceso—, así que se comprueba la condición que la provoca.
"""
import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.chdir(REPO)

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout

app = QApplication([])
ERRORES = []
sys.excepthook = lambda t, v, tb: ERRORES.append("".join(traceback.format_exception(t, v, tb)))

from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from core.utils import vtk_temporizador


def caso(nombre, ok, detalle=""):
    print(f"CASO|{'OK' if ok else 'FALLA'}|{nombre}|{detalle}".replace("\n", " "), flush=True)


# --- A. La instalación
original = QVTKRenderWindowInteractor.TimerEvent
vtk_temporizador.instalar()
caso("A. instalar reemplaza el TimerEvent de la clase",
     QVTKRenderWindowInteractor.TimerEvent is not original)
vtk_temporizador.instalar()
caso("A. instalar dos veces no encadena guardas",
     QVTKRenderWindowInteractor.TimerEvent is not original)
vtk_temporizador.desinstalar()
caso("A. desinstalar devuelve el original",
     QVTKRenderWindowInteractor.TimerEvent is original)
vtk_temporizador.instalar()


# --- Un interactor de mentira: cuenta las veces que VTK recibe el aviso
class InteractorFalso:
    def __init__(self, con_ventana=True):
        self.avisos = 0
        self._ventana = object() if con_ventana else None

    def TimerEvent(self):
        self.avisos += 1

    def GetRenderWindow(self):
        return self._ventana


class WidgetFalso:
    """Lo mínimo que mira la guarda: `_Iren` y `isVisible()`."""

    def __init__(self, visible=True, con_ventana=True, destruido=False):
        self._Iren = InteractorFalso(con_ventana)
        self._visible = visible
        self._destruido = destruido

    def isVisible(self):
        if self._destruido:
            raise RuntimeError("wrapped C/C++ object of type QVTKRenderWindowInteractor "
                               "has been deleted")
        return self._visible


def disparar(widget):
    QVTKRenderWindowInteractor.TimerEvent(widget)
    return widget._Iren.avisos


# --- B. Cuándo pasa el aviso y cuándo no
caso("B. con el widget visible, el aviso llega a VTK",
     disparar(WidgetFalso(visible=True)) == 1)

caso("B. con el plugin fuera de pantalla, NO llega",
     disparar(WidgetFalso(visible=False)) == 0,
     "es el caso que cerraba la aplicacion al cambiar de pestana")

caso("B. sin ventana de render tampoco llega",
     disparar(WidgetFalso(visible=True, con_ventana=False)) == 0)

sin_iren = WidgetFalso()
sin_iren._Iren = None
QVTKRenderWindowInteractor.TimerEvent(sin_iren)
caso("B. sin interactor no revienta", True)

# --- C. El widget ya destruido: PyQt lanza RuntimeError
destruido = WidgetFalso(destruido=True)
try:
    QVTKRenderWindowInteractor.TimerEvent(destruido)
    paso = True
except RuntimeError:
    paso = False
caso("C. si el widget ya se destruyo, la guarda se traga el RuntimeError", paso,
     "el QTimer alcanza a saltar una vez despues de destruir el widget")

# --- D. Un widget de VTK de verdad, oculto
contenedor = QWidget()
QVBoxLayout(contenedor)
real = QVTKRenderWindowInteractor(contenedor)
contenedor.layout().addWidget(real)
app.processEvents()
caso("D. un interactor real sin mostrar esta oculto", not real.isVisible())
QVTKRenderWindowInteractor.TimerEvent(real)
caso("D. y dispararle el temporizador no produce ninguna excepcion", not ERRORES,
     " | ".join(ERRORES)[:300])

caso("sin excepciones", not ERRORES, " | ".join(ERRORES)[:400])

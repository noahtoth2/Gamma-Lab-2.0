"""Arregla el temporizador de `QVTKRenderWindowInteractor`.

**El problema.** La clase que trae VTK para Qt arranca un `QTimer` que se repite
cada 10 ms y, cada vez que salta, hace esto sin comprobar nada
(`vtkmodules/qt/QVTKRenderWindowInteractor.py`, línea 436):

```python
def TimerEvent(self):
    self._Iren.TimerEvent()
```

Cada plugin de GammaLab crea **su propio** interactor —son quince—, y al
cambiar de pestaña `Kernel.stop_plugins()` solo llama a `Disable()` sobre el
interactor: **el `QTimer` sigue corriendo**. Así, el temporizador del plugin que
ya no está en pantalla sigue entrando en VTK sobre un widget oculto cuyo
contexto de OpenGL no está activo.

El resultado es que la aplicación se cierra sola, sin excepción de Python. Está
documentado como el nº 24 de `docs/Plan de Programación/problemas-encontrados.md`,
con esta traza, capturada tres veces:

```
Windows fatal exception: access violation
  File "vtkmodules\\qt\\QVTKRenderWindowInteractor.py", line 436 in TimerEvent
Exception code: 0xc0000005        <- violacion de acceso
Fault offset:   0x0000000000000000  <- salto a direccion nula
```

**Por qué se arregla aquí y no en los quince plugins.** Lo que falta es una
guarda dentro del propio `TimerEvent`, y repetirla quince veces dejaría el
fallo a un plugin de distancia: basta con que alguien añada uno nuevo y se
olvide. Tocar la clase una sola vez cubre los que hay y los que vengan.

Se reemplaza el método de la clase, no se parchea VTK en disco: si algún día la
librería añade la guarda, basta con borrar este archivo.
"""
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

_original = QVTKRenderWindowInteractor.TimerEvent


def _timer_event_seguro(self):
    """`TimerEvent` con las comprobaciones que le faltan al original.

    Se salta el aviso —no se para el temporizador— cuando el widget no está en
    condiciones de recibirlo. Pararlo exigiría volver a arrancarlo al mostrar el
    plugin de nuevo, y eso sí habría que repetirlo en cada uno.
    """
    try:
        interactor = getattr(self, "_Iren", None)
        if interactor is None:
            return
        # El plugin no esta en pantalla: su contexto de OpenGL no esta activo
        if not self.isVisible():
            return
        if interactor.GetRenderWindow() is None:
            return
        interactor.TimerEvent()
    except RuntimeError:
        # PyQt lanza "wrapped C/C++ object has been deleted" cuando el widget
        # ya se destruyo y el QTimer alcanza a saltar una ultima vez.
        return


def instalar():
    """Deja puesta la guarda. Se llama una vez, al arrancar la aplicación."""
    if QVTKRenderWindowInteractor.TimerEvent is not _timer_event_seguro:
        QVTKRenderWindowInteractor.TimerEvent = _timer_event_seguro


def desinstalar():
    """Devuelve el método original. Existe para las pruebas."""
    QVTKRenderWindowInteractor.TimerEvent = _original

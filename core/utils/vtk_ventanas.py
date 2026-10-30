"""Libera la ventana OpenGL de un modulo al salir de el (R45).

Ocultar el widget de un modulo deja viva su ventana OpenGL: el contexto, los
buffers y las texturas siguen ocupando memoria aunque nadie mire el grafico.
`Finalize` los libera y deja intactos el widget, la escena con sus graficos, los
observadores y el menu contextual; la ventana se vuelve a crear sola en el
siguiente `Render`, que el propio widget pide al mostrarse otra vez. El resultado
numerico que cada modulo conserva (`_ultimo`, las tablas de las curvas) no se toca.

Volver a crear la ventana cuesta entre 60 y 460 ms al volver al modulo (R50). A
cambio, recorrer los 12 modulos de analisis con 50 trials de 30 500 muestras deja el
proceso en 913 MB en vez de 3118 MB. El controlador grafico devuelve esa memoria
cuando hay otra actividad OpenGL, no al instante. Un plugin que no lo quiera
declara `free_graphics: false` en su properties.yml.
"""
from core.utils.vtk_observers import widgets_vtk


def liberar_ventanas(contenedor):
    """Finaliza la ventana OpenGL de cada widget VTK dentro de `contenedor`. Devuelve cuantas."""
    n = 0
    for widget in widgets_vtk(contenedor):
        ventana = widget.GetRenderWindow()
        if ventana is not None:
            ventana.Finalize()
            n += 1
    return n

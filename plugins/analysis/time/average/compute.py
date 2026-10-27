import numpy as np


def promedio_trials(trials, ctx=None):
    """Promedio muestra a muestra entre los trials.

    Recibe la matriz (muestras, trials) y devuelve un vector de una muestra por
    fila. El plugin la despacha por el orquestador (R71) aunque con el archivo
    de prueba tarde menos de un milisegundo, para que todas las operaciones
    tengan el mismo progreso y cancelación.
    """
    datos = np.asarray(trials)
    if datos.size == 0:
        raise ValueError("No hay trials activos para promediar.")
    if datos.ndim == 1:
        return datos.astype(np.float64, copy=True)
    return np.mean(datos, axis=1)

import numpy as np


def promedio_trials(trials):
    """Promedio muestra a muestra entre los trials.

    Recibe la matriz (muestras, trials) y devuelve un vector de una muestra por
    fila. No se encola en el orquestador: con el archivo de prueba tarda menos
    de un milisegundo.
    """
    datos = np.asarray(trials)
    if datos.size == 0:
        raise ValueError("No hay trials activos para promediar.")
    if datos.ndim == 1:
        return datos.astype(np.float64, copy=True)
    return np.mean(datos, axis=1)

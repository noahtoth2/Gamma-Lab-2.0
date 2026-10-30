import numpy as np


<<<<<<< HEAD
def promedio_trials(trials, ctx=None):
    """Promedio muestra a muestra entre los trials.

    Recibe la matriz (muestras, trials) y devuelve un vector de una muestra por
    fila. El plugin la despacha por el orquestador (R71) aunque con el archivo
    de prueba tarde menos de un milisegundo, para que todas las operaciones
    tengan el mismo progreso y cancelación.
=======
def promedio_trials(trials, idx=None, ctx=None):
    """Promedio muestra a muestra entre los trials.

    Recibe la matriz (muestras, trials) y devuelve un vector de una muestra por
    fila. `idx` son las posiciones (base 1, entre los trials válidos) que entran
    en el promedio; `None` promedia todos (R41). El plugin la despacha por el
    orquestador (R71) para que todas las operaciones tengan el mismo progreso y
    cancelación.
>>>>>>> f19cc48027c8d0790d3a1557c7f2977055e15238
    """
    datos = np.asarray(trials)
    if datos.size == 0:
        raise ValueError("No hay trials activos para promediar.")
    if datos.ndim == 1:
        return datos.astype(np.float64, copy=True)
    if idx is not None:
        pos = sorted({int(i) for i in idx})
        if not pos:
            raise ValueError("No hay trials seleccionados para promediar.")
        if pos[0] < 1 or pos[-1] > datos.shape[1]:
            raise ValueError(f"Selección fuera de rango (hay {datos.shape[1]} trials).")
        datos = datos[:, [p - 1 for p in pos]]
    return np.mean(datos, axis=1)

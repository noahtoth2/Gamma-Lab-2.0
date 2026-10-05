import numpy as np

# Límite de muestras que se dibujan en el mapa de calor. Por encima de esto el
# submuestreo no cambia lo que se ve y sí el tiempo de dibujo.
MAX_MUESTRAS = 2000


def preparar_mapa_calor(t, sel, max_muestras=MAX_MUESTRAS):
    """Prepara los datos del mapa de calor: submuestreo, rango de color y eje de tiempo.

    No se encola en el orquestador: con el archivo de prueba son milisegundos.
    Devuelve (X, t, vmin, vmax, t0, t_end, dt, factor), donde factor es 1 si no
    hubo submuestreo.
    """
    X = np.asarray(sel, dtype=np.float32)
    if X.ndim != 2:
        raise ValueError(f"Se esperaba una matriz de (trials, muestras); llegó con {X.ndim} dimensiones.")
    t = np.asarray(t)
    _, n_muestras = X.shape

    factor = 1
    if n_muestras > max_muestras:
        factor = int(np.ceil(n_muestras / max_muestras))
        X = X[:, ::factor]
        t = t[::factor]
        n_muestras = X.shape[1]

    finite = np.isfinite(X)
    if finite.any():
        p2, p98 = np.nanpercentile(X[finite], (2, 98))
        if p98 <= p2:
            vmin = float(X[finite].min())
            vmax = float(X[finite].max()) if float(X[finite].max()) > vmin else (vmin + 1.0)
        else:
            vmin, vmax = float(p2), float(p98)
    else:
        vmin, vmax = 0.0, 1.0

    t0 = float(t[0]) if t.size > 0 else 0.0
    t_end = float(t[-1]) if t.size > 0 else 1.0
    dt = (t_end - t0) / n_muestras if n_muestras > 0 else 1.0

    return X, t, vmin, vmax, t0, t_end, dt, factor

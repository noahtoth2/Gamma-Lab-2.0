"""Submuestreo visual de las series de las gráficas (R73).

Una serie larga se dibuja con a lo sumo `MAX_PUNTOS` puntos. Se conservan el
mínimo y el máximo de cada tramo, así que los picos no se pierden. Solo cambia
lo que se pinta: los datos completos quedan guardados y son los que leen la
exportación y las mediciones (`tabla_de`).

Al acercar el gráfico, la serie se vuelve a reducir sobre el rango visible, así
que el zoom recupera el detalle hasta la resolución original.
"""
import numpy as np
import vtk
from vtkmodules.util import numpy_support

MAX_PUNTOS = 2000

# dirección del plot -> (x, y, nombre_x, nombre_y); se limpia cuando el plot se destruye
_COMPLETAS = {}


def indices_reducidos(y, n_max=MAX_PUNTOS, con_nan=True):
    """Índices (ordenados) de a lo sumo ~n_max puntos: mínimo y máximo de cada tramo, más los extremos."""
    n = len(y)
    if n <= n_max:
        return np.arange(n)
    y = np.asarray(y, dtype=np.float64)
    tramos = max(1, n_max // 2)
    k = n // tramos
    util = tramos * k
    bloques = y[:util].reshape(tramos, k)
    base = np.arange(tramos, dtype=np.int64) * k
    # los NaN no ganan ni el mínimo ni el máximo
    if con_nan:
        imin = base + np.argmin(np.where(np.isnan(bloques), np.inf, bloques), axis=1)
        imax = base + np.argmax(np.where(np.isnan(bloques), -np.inf, bloques), axis=1)
    else:
        imin = base + np.argmin(bloques, axis=1)
        imax = base + np.argmax(bloques, axis=1)
    extra = [0, n - 1]
    if util < n:
        cola = y[util:]
        if con_nan and not np.isnan(cola).all() or not con_nan and cola.size:
            extra += [util + int(np.nanargmin(cola)), util + int(np.nanargmax(cola))]
    return np.unique(np.concatenate([imin, imax, np.asarray(extra, dtype=np.int64)]))


def _a_vtk(valores, nombre):
    arr = numpy_support.numpy_to_vtk(np.ascontiguousarray(valores, dtype=np.float64), deep=True)
    arr.SetName(nombre)
    return arr


def _llenar(tabla, x, y, nombre_x, nombre_y):
    while tabla.GetNumberOfColumns():
        tabla.RemoveColumn(0)
    tabla.AddColumn(_a_vtk(x, nombre_x))
    tabla.AddColumn(_a_vtk(y, nombre_y))
    tabla.SetNumberOfRows(len(x))
    tabla.Modified()


def recortar(x, y, desde=None, hasta=None, n_max=MAX_PUNTOS, ordenado=True, con_nan=True):
    """Puntos a dibujar de (x, y) dentro del rango visible [desde, hasta]."""
    if ordenado and desde is not None and hasta is not None:
        i0 = max(0, int(np.searchsorted(x, desde, side="left")) - 1)
        i1 = min(len(x), int(np.searchsorted(x, hasta, side="right")) + 1)
        x, y = x[i0:i1], y[i0:i1]
    idx = indices_reducidos(y, n_max, con_nan)
    return x[idx], y[idx]


class _Serie:
    def __init__(self, x, y, nombre_x, nombre_y, tabla, ordenado):
        self.x, self.y, self.nombre_x, self.nombre_y = x, y, nombre_x, nombre_y
        self.tabla, self.ordenado = tabla, ordenado
        self.con_nan = bool(np.isnan(y).any())

    def actualizar(self, desde, hasta, n_max):
        xs, ys = recortar(self.x, self.y, desde, hasta, n_max, self.ordenado, self.con_nan)
        _llenar(self.tabla, xs, ys, self.nombre_x, self.nombre_y)


class _Controlador:
    """Vuelve a reducir las series de un gráfico cuando cambia el rango de su eje X."""

    def __init__(self, n_max):
        self.n_max = n_max
        self.series = []
        self._ventana = None
        self._ocupado = False
        # El eje arranca con un rango por defecto que no es un zoom del usuario:
        # se empieza a recortar cuando el eje ya abarcó todos los datos.
        self._armado = False

    def _abarca_todo(self, ventana):
        lo = min(float(s.x[0]) for s in self.series)
        hi = max(float(s.x[-1]) for s in self.series)
        margen = 0.02 * (hi - lo)
        return ventana[0] <= lo + margen and ventana[1] >= hi - margen

    def al_cambiar_eje(self, eje, _evento):
        if self._ocupado:
            return
        ventana = (eje.GetMinimum(), eje.GetMaximum())
        if ventana == self._ventana:
            return
        if not self._armado:
            if not self._abarca_todo(ventana):
                return
            self._armado = True
        self._ocupado = True
        try:
            self._ventana = ventana
            for s in self.series:
                if s.ordenado:
                    s.actualizar(ventana[0], ventana[1], self.n_max)
        except Exception as e:
            print("submuestreo:", e)
        finally:
            self._ocupado = False


def agregar_linea(chart, x, y, nombre_x="x", nombre_y="y", n_max=MAX_PUNTOS, tipo=None):
    """Añade a `chart` una serie de línea reducida y devuelve el plot."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ordenado = bool(len(x) < 2 or np.all(np.diff(x) >= 0))
    tabla = vtk.vtkTable()
    if len(x) <= n_max:
        _llenar(tabla, x, y, nombre_x, nombre_y)
        plot = chart.AddPlot(tipo if tipo is not None else vtk.vtkChart.LINE)
        plot.SetInputData(tabla, 0, 1)
        return plot
    xs, ys = recortar(x, y, n_max=n_max, ordenado=False)
    _llenar(tabla, xs, ys, nombre_x, nombre_y)

    plot = chart.AddPlot(tipo if tipo is not None else vtk.vtkChart.LINE)
    plot.SetInputData(tabla, 0, 1)

    clave = plot.__this__
    _COMPLETAS[clave] = (x, y, nombre_x, nombre_y)
    plot.AddObserver("DeleteEvent", lambda o, e, k=clave: _COMPLETAS.pop(k, None))

    ctrl = getattr(chart, "_submuestreo", None)
    if ctrl is None:
        ctrl = chart._submuestreo = _Controlador(n_max)
        chart.GetAxis(vtk.vtkAxis.BOTTOM).AddObserver("ModifiedEvent", ctrl.al_cambiar_eje)
    ctrl.series.append(_Serie(x, y, nombre_x, nombre_y, tabla, ordenado))
    return plot


def tabla_de(plot):
    """Tabla con los datos completos del plot (X, Y), no la reducida que se dibuja."""
    completa = _COMPLETAS.get(getattr(plot, "__this__", None))
    if completa is None:
        return plot.GetInput()
    x, y, nombre_x, nombre_y = completa
    tabla = vtk.vtkTable()
    tabla.AddColumn(_a_vtk(x, nombre_x))
    tabla.AddColumn(_a_vtk(y, nombre_y))
    tabla.SetNumberOfRows(len(x))
    return tabla


def agregar_columna(chart, tabla, columna, n_max=MAX_PUNTOS):
    """Serie reducida con la columna 0 de `tabla` como X y `columna` como Y."""
    col_x, col_y = tabla.GetColumn(0), tabla.GetColumn(columna)
    return agregar_linea(chart, numpy_support.vtk_to_numpy(col_x), numpy_support.vtk_to_numpy(col_y),
                         col_x.GetName() or "x", col_y.GetName() or f"y{columna}", n_max)

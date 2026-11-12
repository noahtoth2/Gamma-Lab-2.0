"""Al acercar en el tiempo, el eje Y se ajusta a la amplitud de lo que se ve.

La rueda acercaba los dos ejes por igual. Con 15 pasos sobre un trial de
17613000.abf, la ventana vertical quedaba en 0,006 mV mientras la señal ocupaba
0,085 mV en ese tramo. Solo el 10 % de las muestras caía dentro y se veían rayas
verticales: la señal entrando y saliendo de una franja de 2,5 escalones del
conversor. Ahora, en las gráficas de líneas, la rueda acerca solo el tiempo y el
eje Y sigue a los datos visibles, como en MATLAB o Clampfit.

El ajuste se activa con el zoom del usuario, no antes: hasta entonces cada
gráfica conserva el rango que le puso su plugin (el histograma de PAC, por
ejemplo, deja un 10 % de margen como MATLAB). «Reset view» lo devuelve.
"""
import numpy as np
import vtk

from core.utils.submuestreo import datos_completos

MARGEN = 0.05     # fracción del rango visible que se deja arriba y abajo


def es_grafico_de_lineas(chart):
    """Gráficas X-Y (señales, espectros, barras); no los mapas de color."""
    return isinstance(chart, vtk.vtkChartXY) and not isinstance(chart, vtk.vtkChartHistogram2D)


def rango_visible_y(chart, x0, x1):
    """(mínimo, máximo) de las curvas visibles de `chart` entre x0 y x1, o None si no hay datos."""
    lo, hi = np.inf, -np.inf
    for i in range(chart.GetNumberOfPlots()):
        plot = chart.GetPlot(i)
        if not plot.GetVisible():
            continue
        datos = datos_completos(plot)
        if datos is None or datos[0].size == 0:
            continue
        x, y = datos
        if x[0] <= x[-1]:
            # Se suma una muestra a cada lado: el tramo de línea que entra y sale de la ventana
            i0 = max(0, int(np.searchsorted(x, x0, side="left")) - 1)
            i1 = min(x.size, int(np.searchsorted(x, x1, side="right")) + 1)
            tramo = y[i0:i1]
        else:
            tramo = y[(x >= x0) & (x <= x1)]
        tramo = tramo[np.isfinite(tramo)]
        if tramo.size:
            lo, hi = min(lo, float(tramo.min())), max(hi, float(tramo.max()))
    return (lo, hi) if np.isfinite(lo) else None


class AjusteVertical:
    """Mantiene el eje Y de `chart` ajustado a los datos que muestra su eje X."""

    def __init__(self, chart):
        self.chart = chart
        self.activo = False
        self._ocupado = False
        self._ventana = None
        eje_y = chart.GetAxis(vtk.vtkAxis.LEFT)
        self._original = (eje_y.GetBehavior(), eje_y.GetMinimum(), eje_y.GetMaximum())
        chart.GetAxis(vtk.vtkAxis.BOTTOM).AddObserver("ModifiedEvent", self.ajustar)

    @classmethod
    def de(cls, chart):
        """El ajuste de `chart`, creándolo la primera vez."""
        ajuste = getattr(chart, "_ajuste_vertical", None)
        if ajuste is None:
            ajuste = chart._ajuste_vertical = cls(chart)
        return ajuste

    def activar(self):
        if not self.activo:
            self.activo = True
            self._ventana = None
            self.ajustar()

    def ajustar(self, *_):
        if not self.activo or self._ocupado:
            return
        eje_x = self.chart.GetAxis(vtk.vtkAxis.BOTTOM)
        eje_y = self.chart.GetAxis(vtk.vtkAxis.LEFT)
        if eje_y.GetLogScaleActive():
            return
        ventana = (eje_x.GetMinimum(), eje_x.GetMaximum())
        if ventana == self._ventana:
            return
        self._ocupado = True
        try:
            rango = rango_visible_y(self.chart, *ventana)
            if rango is None:
                return
            self._ventana = ventana
            lo, hi = rango
            margen = (hi - lo) * MARGEN or max(abs(hi) * MARGEN, 1e-12)
            eje_y.SetRange(lo - margen, hi + margen)
            eje_y.SetBehavior(vtk.vtkAxis.FIXED)
        except Exception as e:
            print("ajuste_vertical:", e)
        finally:
            self._ocupado = False

    def restaurar(self):
        """Apaga el ajuste y deja el eje Y como lo había puesto el plugin."""
        self.activo = False
        self._ventana = None
        comportamiento, lo, hi = self._original
        eje_y = self.chart.GetAxis(vtk.vtkAxis.LEFT)
        eje_y.SetBehavior(comportamiento)
        if comportamiento == vtk.vtkAxis.FIXED:
            eje_y.SetRange(lo, hi)

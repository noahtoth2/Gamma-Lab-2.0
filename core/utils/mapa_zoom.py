"""Mapas de color que se dibujan a la resolución de la pantalla y muestran cada celda al acercar.

La wavelet calculada con la densidad completa del archivo tiene decenas de miles
de columnas: 998 x 45.454 para un trial de 4,5 s a 10 kHz. VTK no puede dibujar
esa imagen entera, porque supera el tamaño de textura de la tarjeta gráfica: sale
de **un solo color**, y tarda 10 s. Además, `vtkChartHistogram2D` vuelve a pintar
la imagen completa en cada redibujo, así que el costo crece con su tamaño: 109 ms
con 4546 columnas, 306 ms con 16.000.

Aquí se guarda la matriz completa y se dibuja solo la zona visible, con a lo sumo
`MAX_COLUMNAS` x `MAX_FILAS` celdas (más celdas que píxeles no se ven). Al acercar
se vuelve a recortar, hasta mostrar cada celda calculada. Solo cambia lo que se
pinta: las exportaciones leen la matriz completa (`chart.emf_imagen`, que deja
`anotar_mapa`).

Para que el zoom sea fluido, al crear el mapa se arma una pirámide: la matriz,
otra con las columnas promediadas de a 2, otra de a 4, y así hasta caber en
`MAX_COLUMNAS`. Cada zoom solo recorta del nivel adecuado. Promediar en el
momento costaba de 180 a 240 ms por recorte, y un paso de la rueda dispara
hasta cuatro.
"""
import numpy as np
import vtk
from vtkmodules.util import numpy_support

MAX_COLUMNAS = 2048
MAX_FILAS = 1024


def piramide(Z, max_columnas=MAX_COLUMNAS):
    """[Z, Z con columnas promediadas de a 2, de a 4, ...] hasta caber en `max_columnas`.

    Con un número impar de columnas, la última del nivel siguiente queda sola.
    """
    niveles = [np.ascontiguousarray(Z, dtype=np.float32)]
    while niveles[-1].shape[1] > max_columnas:
        a = niveles[-1]
        pares = a.shape[1] // 2
        siguiente = (a[:, 0:2 * pares:2] + a[:, 1:2 * pares:2]) * np.float32(0.5)
        if a.shape[1] % 2:
            siguiente = np.concatenate([siguiente, a[:, -1:]], axis=1)
        niveles.append(np.ascontiguousarray(siguiente))
    return niveles


def _promediar_filas(bloque, paso):
    """Promedio de a grupos de `paso` filas; el último grupo puede ser menor."""
    if paso <= 1:
        return bloque
    n = bloque.shape[0]
    inicios = np.arange(0, n, paso)
    sumas = np.add.reduceat(bloque, inicios, axis=0, dtype=np.float64)
    return sumas / np.diff(np.append(inicios, n)).astype(np.float64)[:, None]


def celdas_visibles(niveles, x0, dx, y0, dy, rango_x, rango_y,
                    max_columnas=MAX_COLUMNAS, max_filas=MAX_FILAS):
    """Lo que hay que dibujar en la ventana visible, tomado del nivel de la pirámide adecuado.

    La celda (i, j) de la matriz cubre de x0 + j*dx a x0 + (j+1)*dx, como la
    dibuja `vtkChartHistogram2D`. Devuelve (bloque, x0, dx, y0, dy) del recorte.
    """
    ny, nx = niveles[0].shape

    def tramo(lo, hi, origen, paso, n):
        a = int(np.floor((min(lo, hi) - origen) / paso)) - 1
        b = int(np.ceil((max(lo, hi) - origen) / paso)) + 1
        a = min(max(a, 0), n - 1)
        return a, min(max(b, a + 1), n)

    c0, c1 = tramo(rango_x[0], rango_x[1], x0, dx, nx)
    f0, f1 = tramo(rango_y[0], rango_y[1], y0, dy, ny)

    nivel = 0
    while nivel + 1 < len(niveles) and -(-(c1 - c0) // (1 << nivel)) > max_columnas:
        nivel += 1
    escala = 1 << nivel
    datos = niveles[nivel]
    c0n, c1n = c0 // escala, min(-(-c1 // escala), datos.shape[1])

    por_filas = -(-(f1 - f0) // max_filas)
    bloque = _promediar_filas(datos[f0:f1, c0n:c1n], por_filas)
    return bloque, x0 + c0n * escala * dx, dx * escala, y0 + f0 * dy, dy * por_filas


class MapaConZoom:
    """Dibuja `Z` en `chart` (un `vtkChartHistogram2D`) según la ventana de sus ejes.

    Se crea después de fijar el rango de los ejes. Se queda observando los ejes
    inferior e izquierdo y vuelve a recortar cuando cambian (zoom o desplazamiento).
    """

    def __init__(self, chart, Z, x0, dx, y0, dy, max_columnas=MAX_COLUMNAS, max_filas=MAX_FILAS):
        self.chart = chart
        self.niveles = piramide(Z, max_columnas)
        self.x0, self.dx, self.y0, self.dy = float(x0), float(dx), float(y0), float(dy)
        self.max_columnas, self.max_filas = max_columnas, max_filas
        self.imagen = vtk.vtkImageData()
        self._recorte = None
        self._ocupado = False
        self.actualizar()
        chart.SetInputData(self.imagen, 0)
        for eje in (vtk.vtkAxis.BOTTOM, vtk.vtkAxis.LEFT):
            chart.GetAxis(eje).AddObserver("ModifiedEvent", self.actualizar)

    def _ventana(self):
        ax_x = self.chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_y = self.chart.GetAxis(vtk.vtkAxis.LEFT)
        return (ax_x.GetMinimum(), ax_x.GetMaximum()), (ax_y.GetMinimum(), ax_y.GetMaximum())

    def actualizar(self, *_):
        if self._ocupado:
            return
        self._ocupado = True
        try:
            rango_x, rango_y = self._ventana()
            bloque, x0, dx, y0, dy = celdas_visibles(self.niveles, self.x0, self.dx, self.y0, self.dy,
                                                     rango_x, rango_y, self.max_columnas, self.max_filas)
            recorte = (bloque.shape, x0, dx, y0, dy)
            if recorte == self._recorte:
                return          # mismo recorte: no se vuelve a subir la imagen
            self._recorte = recorte
            filas, columnas = bloque.shape
            self.imagen.SetDimensions(columnas, filas, 1)
            self.imagen.SetOrigin(x0, y0, 0.0)
            self.imagen.SetSpacing(dx, dy, 1.0)
            self.imagen.GetPointData().SetScalars(numpy_support.numpy_to_vtk(
                np.ascontiguousarray(bloque, dtype=np.float32).ravel(), deep=True, array_type=vtk.VTK_FLOAT))
            self.imagen.Modified()
        except Exception as e:
            print("mapa_zoom:", e)
        finally:
            self._ocupado = False

    @property
    def celdas_dibujadas(self):
        """(filas, columnas) de la imagen que se está dibujando."""
        dims = self.imagen.GetDimensions()
        return dims[1], dims[0]

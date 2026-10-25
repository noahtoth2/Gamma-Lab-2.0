"""Escritor de EMF (Enhanced Metafile) para las gráficas de VTK.

VTK no sabe escribir EMF y en este proyecto no hay pywin32, así que el archivo
se arma a mano siguiendo [MS-EMF]. El resultado es **vectorial** en lo que
importa para publicar: ejes, marcas, rótulos, título, líneas y barra de color
son registros de dibujo, no píxeles. El mapa de calor (escalograma, mapa de
acoplamiento) va como un bitmap incrustado, que es lo que hace cualquier
exportador de EMF —también el de MATLAB— porque una imagen de millones de celdas
no cabe como rectángulos.

Se usan solo los registros que Word, PowerPoint e Inkscape entienden sin
problema: líneas, rectángulos, texto, polilíneas e imagen.
"""
import os
import struct

import numpy as np
import vtk
from vtkmodules.util import numpy_support

# --- Constantes de [MS-EMF]
EMR_HEADER = 1
EMR_POLYLINE16 = 87
EMR_EOF = 14
EMR_SETBKMODE = 18
EMR_SETTEXTALIGN = 22
EMR_SETTEXTCOLOR = 24
EMR_MOVETOEX = 27
EMR_SELECTOBJECT = 37
EMR_CREATEPEN = 38
EMR_CREATEBRUSHINDIRECT = 39
EMR_DELETEOBJECT = 40
EMR_RECTANGLE = 43
EMR_LINETO = 54
EMR_STRETCHDIBITS = 81
EMR_EXTCREATEFONTINDIRECTW = 82
EMR_EXTTEXTOUTW = 84
EMR_SETSTRETCHBLTMODE = 21

TRANSPARENT = 1
TA_LEFT, TA_RIGHT, TA_CENTER = 0, 2, 6
TA_TOP, TA_BOTTOM, TA_BASELINE = 0, 8, 24
PS_SOLID, PS_NULL = 0, 5
BS_SOLID, BS_NULL = 0, 1
STOCK = 0x80000000          # bit de los objetos de serie
NULL_BRUSH = STOCK | 5
NULL_PEN = STOCK | 8
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
COLORONCOLOR = 3

DPI = 96.0
FUENTES = (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf")


def _rgb(r, g, b):
    return int(r) | (int(g) << 8) | (int(b) << 16)


def _pad4(b):
    return b + b"\x00" * (-len(b) % 4)


def _medidor(alto_px):
    """Devuelve `ancho(texto)` en píxeles para Arial de `alto_px`; con PIL si hay
    fuente y, si no, una aproximación."""
    try:
        from PIL import ImageFont
        for ruta in FUENTES:
            if os.path.exists(ruta):
                fuente = ImageFont.truetype(ruta, int(alto_px))
                return lambda t: float(fuente.getlength(t))
    except Exception:
        pass
    return lambda t: 0.55 * alto_px * len(t)


class EmfWriter:
    """Acumula registros y los vuelca con la cabecera correcta."""

    def __init__(self, ancho_px, alto_px):
        self.w, self.h = int(ancho_px), int(alto_px)
        self._reg = []
        self._n_obj = 0                  # índice 0 está reservado
        self._fuentes = {}
        self._medidores = {}
        self.emit(EMR_SETBKMODE, struct.pack("<I", TRANSPARENT))
        self.emit(EMR_SETSTRETCHBLTMODE, struct.pack("<I", COLORONCOLOR))

    # ---- bajo nivel
    def emit(self, tipo, cuerpo=b""):
        cuerpo = _pad4(cuerpo)
        self._reg.append(struct.pack("<II", tipo, 8 + len(cuerpo)) + cuerpo)

    def _nuevo_objeto(self):
        self._n_obj += 1
        return self._n_obj

    def _seleccionar(self, idx):
        self.emit(EMR_SELECTOBJECT, struct.pack("<I", idx))

    # ---- lápiz y pincel
    def pluma(self, color, ancho=1):
        idx = self._nuevo_objeto()
        self.emit(EMR_CREATEPEN, struct.pack("<IIiiI", idx, PS_SOLID, int(ancho), 0, _rgb(*color)))
        self._seleccionar(idx)
        return idx

    def pincel(self, color):
        idx = self._nuevo_objeto()
        self.emit(EMR_CREATEBRUSHINDIRECT, struct.pack("<IIII", idx, BS_SOLID, _rgb(*color), 0))
        self._seleccionar(idx)
        return idx

    def sin_pincel(self):
        self._seleccionar(NULL_BRUSH)

    def liberar(self, idx):
        self.emit(EMR_DELETEOBJECT, struct.pack("<I", idx))

    # ---- figuras
    def linea(self, x0, y0, x1, y1):
        self.emit(EMR_MOVETOEX, struct.pack("<ii", int(round(x0)), int(round(y0))))
        self.emit(EMR_LINETO, struct.pack("<ii", int(round(x1)), int(round(y1))))

    def rectangulo(self, x0, y0, x1, y1):
        self.emit(EMR_RECTANGLE, struct.pack("<iiii", int(round(x0)), int(round(y0)),
                                             int(round(x1)), int(round(y1))))

    def polilinea(self, xs, ys):
        pts = np.column_stack([np.round(xs), np.round(ys)]).astype(np.int16)
        n = len(pts)
        if n < 2:
            return
        x0, y0 = pts.min(axis=0)
        x1, y1 = pts.max(axis=0)
        self.emit(EMR_POLYLINE16, struct.pack("<iiiiI", x0, y0, x1, y1, n) + pts.tobytes())

    # ---- texto
    def _fuente(self, alto_px, angulo=0, negrita=False):
        clave = (int(alto_px), int(angulo), bool(negrita))
        if clave in self._fuentes:
            return self._fuentes[clave]
        idx = self._nuevo_objeto()
        # LOGFONTW: alto, ancho, escapement, orientation, weight, italic, underline,
        # strikeout, charset, outprec, clipprec, quality, pitch, facename[32 WCHAR]
        nombre = "Arial".encode("utf-16-le").ljust(64, b"\x00")
        logfont = struct.pack("<iiiiiBBBBBBBB", -int(alto_px), 0, int(angulo) * 10, int(angulo) * 10,
                              700 if negrita else 400, 0, 0, 0, 1, 0, 0, 4, 34) + nombre
        self.emit(EMR_EXTCREATEFONTINDIRECTW, struct.pack("<I", idx) + logfont)
        self._fuentes[clave] = idx
        return idx

    def ancho_texto(self, texto, alto_px):
        if alto_px not in self._medidores:
            self._medidores[alto_px] = _medidor(alto_px)
        return self._medidores[alto_px](texto)

    def texto(self, x, y, texto, alto_px=14, alineacion=TA_LEFT | TA_TOP, color=(0, 0, 0),
              angulo=0, negrita=False):
        if not texto:
            return
        self._seleccionar(self._fuente(alto_px, angulo, negrita))
        self.emit(EMR_SETTEXTCOLOR, struct.pack("<I", _rgb(*color)))
        self.emit(EMR_SETTEXTALIGN, struct.pack("<I", alineacion))
        cadena = texto.encode("utf-16-le")
        n = len(texto)
        # Espaciado por carácter: sin él cada lector elige uno y el texto sale desigual
        dx = struct.pack("<%di" % n, *[int(round(self.ancho_texto(c, alto_px))) for c in texto])
        cuerpo = struct.pack("<iiii", 0, 0, 0, 0)                # bounds (se ignora)
        cuerpo += struct.pack("<Iff", 1, 1.0, 1.0)               # graphics mode, exScale, eyScale
        cuerpo += struct.pack("<iiIIIiiiiI", int(round(x)), int(round(y)), n, 76, 0, 0, 0, 0, 0,
                              76 + len(_pad4(cadena)))
        self.emit(EMR_EXTTEXTOUTW, cuerpo + _pad4(cadena) + dx)

    # ---- imagen
    def imagen(self, rgb, x0, y0, ancho, alto):
        """`rgb`: arreglo (filas, columnas, 3) uint8, la fila 0 arriba."""
        filas, columnas, _ = rgb.shape
        bytes_fila = columnas * 3
        relleno = (-bytes_fila) % 4
        bgr = np.ascontiguousarray(rgb[::-1, :, ::-1]).reshape(filas, bytes_fila)   # DIB: de abajo hacia arriba, BGR
        if relleno:
            bgr = np.pad(bgr, ((0, 0), (0, relleno)))
        datos = bgr.tobytes()
        cabecera = struct.pack("<IiiHHIIiiII", 40, columnas, filas, 1, 24, 0, len(datos), 0, 0, 0, 0)
        off_bmi = 80
        off_bits = off_bmi + len(cabecera)
        cuerpo = struct.pack("<iiii", int(x0), int(y0), int(x0 + ancho), int(y0 + alto))   # bounds
        cuerpo += struct.pack("<iiiiii", int(x0), int(y0), 0, 0, columnas, filas)            # dest, src
        cuerpo += struct.pack("<IIIIII", off_bmi, len(cabecera), off_bits, len(datos),
                              DIB_RGB_COLORS, SRCCOPY)
        cuerpo += struct.pack("<ii", int(ancho), int(alto))
        self.emit(EMR_STRETCHDIBITS, _pad4(cuerpo + cabecera + datos))

    # ---- volcado
    def guardar(self, ruta):
        fin = struct.pack("<IIIII", EMR_EOF, 20, 0, 16, 20)
        cuerpo = b"".join(self._reg) + fin
        px_mm = 25.4 / DPI
        marco = (0, 0, int(round(self.w * px_mm * 100)), int(round(self.h * px_mm * 100)))
        total = 88 + len(cuerpo)
        cab = struct.pack("<II", EMR_HEADER, 88)
        cab += struct.pack("<iiii", 0, 0, self.w - 1, self.h - 1)          # bounds en píxeles
        cab += struct.pack("<iiii", *marco)                                # frame en 0,01 mm
        cab += struct.pack("<IIIIHHIII", 0x464D4520, 0x10000, total, len(self._reg) + 2,
                           self._n_obj + 1, 0, 0, 0, 0)                    # sin descripción ni paleta
        cab += struct.pack("<ii", self.w, self.h)                          # dispositivo en píxeles
        cab += struct.pack("<ii", int(round(self.w * px_mm)), int(round(self.h * px_mm)))
        assert len(cab) == 88, len(cab)
        with open(ruta, "wb") as f:
            f.write(cab + cuerpo)


# =====================================================================
#   De una gráfica de VTK a un EMF
# =====================================================================
NEGRO = (0, 0, 0)
GRIS = (150, 150, 150)
GRIS_TEXTO = (60, 60, 60)


def _marcas_bonitas(vmin, vmax, n=6):
    """Marcas con un paso de 1, 2 o 5 por una potencia de diez."""
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return [vmin]
    bruto = (vmax - vmin) / max(1, n)
    exp = np.floor(np.log10(bruto))
    for c in (1, 2, 2.5, 5, 10):
        if bruto / 10 ** exp <= c:
            paso = c * 10 ** exp
            break
    ini = np.ceil(vmin / paso - 1e-9) * paso
    return [float(v) for v in np.arange(ini, vmax + paso * 1e-6, paso)]


def _formato(v):
    v = v + 0.0                         # -0,0 se escribiría "-0"
    return f"{v:.4g}" if abs(v) < 1e5 else f"{v:.3g}"


def _marcas_del_eje(eje):
    """(posiciones, etiquetas) tal como VTK las dibujaría."""
    pos = eje.GetTickPositions()
    et = eje.GetTickLabels()
    if pos is None or et is None or pos.GetNumberOfTuples() == 0:
        return [], []
    n = min(pos.GetNumberOfTuples(), et.GetNumberOfValues())
    return [pos.GetValue(i) for i in range(n)], [et.GetValue(i) for i in range(n)]


def _marco(e, titulo, x_titulo, y_titulo, ancho, alto, margenes, rango_x, rango_y,
           marcas_x, marcas_y):
    """Dibuja ejes, marcas, rótulos y título. Devuelve el rectángulo del área."""
    izq, der, arr, aba = margenes
    x0, y0, x1, y1 = izq, arr, ancho - der, alto - aba
    to_x = lambda v: x0 + (v - rango_x[0]) / (rango_x[1] - rango_x[0]) * (x1 - x0)
    to_y = lambda v: y1 - (v - rango_y[0]) / (rango_y[1] - rango_y[0]) * (y1 - y0)

    p = e.pluma(NEGRO, 1)
    e.sin_pincel()
    e.rectangulo(x0, y0, x1, y1)
    for v, t in zip(*marcas_x):
        if rango_x[0] - 1e-9 <= v <= rango_x[1] + 1e-9:
            px = to_x(v)
            e.linea(px, y1, px, y1 + 5)
            e.texto(px, y1 + 8, t, 13, TA_CENTER | TA_TOP, GRIS_TEXTO)
    for v, t in zip(*marcas_y):
        if rango_y[0] - 1e-9 <= v <= rango_y[1] + 1e-9:
            py = to_y(v)
            e.linea(x0 - 5, py, x0, py)
            e.texto(x0 - 8, py - 7, t, 13, TA_RIGHT | TA_TOP, GRIS_TEXTO)
    e.liberar(p)
    e.texto((x0 + x1) / 2, alto - 24, x_titulo, 15, TA_CENTER | TA_TOP, NEGRO)
    e.texto(26, (y0 + y1) / 2, y_titulo, 15, TA_CENTER | TA_BOTTOM, NEGRO, angulo=90)
    e.texto((x0 + x1) / 2, 14, titulo, 17, TA_CENTER | TA_TOP, NEGRO, negrita=True)
    return (x0, y0, x1, y1), to_x, to_y


def _ejes(chart, ancho, alto, margenes, e, titulo):
    ax_x, ax_y = chart.GetAxis(vtk.vtkAxis.BOTTOM), chart.GetAxis(vtk.vtkAxis.LEFT)
    rx = (ax_x.GetMinimum(), ax_x.GetMaximum())
    ry = (ax_y.GetMinimum(), ax_y.GetMaximum())
    mx = _marcas_del_eje(ax_x)
    my = _marcas_del_eje(ax_y)
    if not mx[0]:
        mx = (_marcas_bonitas(*rx), [_formato(v) for v in _marcas_bonitas(*rx)])
    if not my[0]:
        my = (_marcas_bonitas(*ry), [_formato(v) for v in _marcas_bonitas(*ry)])
    return _marco(e, titulo, ax_x.GetTitle() or "", ax_y.GetTitle() or "", ancho, alto,
                  margenes, rx, ry, mx, my)


def anotar_mapa(chart, imagen, funcion_color):
    """Deja en la gráfica el mapa y su tabla de color.

    `vtkChartHistogram2D` no los devuelve (solo tiene `SetInputData` y
    `SetTransferFunction`), y el EMF necesita releerlos. Quien construye el
    mapa llama a esto una vez.
    """
    chart.emf_imagen = imagen
    chart.emf_color = funcion_color
    return chart


def heatmap_a_emf(chart, ruta, ancho=1000, alto=700):
    """Un `vtkChartHistogram2D` a EMF: bitmap del mapa, resto vectorial."""
    img = getattr(chart, "emf_imagen", None)
    tf = getattr(chart, "emf_color", None)
    if img is None or tf is None:
        raise ValueError("La gráfica no tiene un mapa de calor que exportar.")
    nx, ny, _ = img.GetDimensions()
    ox, oy, _ = img.GetOrigin()
    sx, sy, _ = img.GetSpacing()
    z = numpy_support.vtk_to_numpy(img.GetPointData().GetScalars()).reshape(ny, nx)

    margenes = (95, 130, 52, 78)
    e = EmfWriter(ancho, alto)
    (x0, y0, x1, y1), to_x, to_y = _ejes(chart, ancho, alto, margenes, e,
                                        chart.GetTitle() or "")

    # --- El mapa: se muestrea a la resolución de pantalla (x2) y no a la de los datos
    ax_x, ax_y = chart.GetAxis(vtk.vtkAxis.BOTTOM), chart.GetAxis(vtk.vtkAxis.LEFT)
    rx = (ax_x.GetMinimum(), ax_x.GetMaximum())
    ry = (ax_y.GetMinimum(), ax_y.GetMaximum())
    # Con pocas celdas no hace falta más resolución que la de pantalla; con muchas, el doble
    w_px = max(2, min(int(2 * (x1 - x0)), max(int(x1 - x0), nx), 4000))
    h_px = max(2, min(int(2 * (y1 - y0)), max(int(y1 - y0), ny), 3000))
    xs = rx[0] + (np.arange(w_px) + 0.5) / w_px * (rx[1] - rx[0])
    ys = ry[1] - (np.arange(h_px) + 0.5) / h_px * (ry[1] - ry[0])          # fila 0 = arriba
    col = np.floor((xs - ox) / sx).astype(int)
    fila = np.floor((ys - oy) / sy).astype(int)
    dentro = ((col >= 0) & (col < nx))[None, :] & ((fila >= 0) & (fila < ny))[:, None]
    muestra = z[np.clip(fila, 0, ny - 1)][:, np.clip(col, 0, nx - 1)].astype(np.float32)

    va = numpy_support.numpy_to_vtk(np.ascontiguousarray(muestra).ravel(), deep=True,
                                    array_type=vtk.VTK_FLOAT)
    rgba = numpy_support.vtk_to_numpy(tf.MapScalars(va, 1, 0)).reshape(h_px, w_px, -1)
    rgb = rgba[:, :, :3].astype(np.float32)
    alfa = (rgba[:, :, 3:4].astype(np.float32) / 255.0) if rgba.shape[2] == 4 else 1.0
    rgb = (rgb * alfa + 255.0 * (1.0 - alfa))                                # sobre blanco
    rgb[~dentro] = 255.0
    e.imagen(np.clip(rgb, 0, 255).astype(np.uint8), x0, y0, x1 - x0, y1 - y0)
    # el marco se redibuja encima del bitmap
    p = e.pluma(NEGRO, 1)
    e.sin_pincel()
    e.rectangulo(x0, y0, x1, y1)
    e.liberar(p)

    # --- Barra de color, en vectores
    vmin, vmax = tf.GetRange()
    bx0, bx1 = x1 + 22, x1 + 44
    n = 96
    e._seleccionar(NULL_PEN)
    for k in range(n):
        v = vmax - (k + 0.5) / n * (vmax - vmin)
        rgb3 = [0.0, 0.0, 0.0]
        tf.GetColor(v, rgb3)
        b = e.pincel(tuple(int(round(c * 255)) for c in rgb3))
        ya, yb = y0 + k * (y1 - y0) / n, y0 + (k + 1) * (y1 - y0) / n
        e.rectangulo(bx0, ya, bx1, yb + 1)
        e.liberar(b)
    p = e.pluma(NEGRO, 1)
    e.sin_pincel()
    e.rectangulo(bx0, y0, bx1, y1)
    for v in _marcas_bonitas(vmin, vmax):
        py = y1 - (v - vmin) / (vmax - vmin) * (y1 - y0)
        e.linea(bx1, py, bx1 + 5, py)
        e.texto(bx1 + 8, py - 7, _formato(v), 13, TA_LEFT | TA_TOP, GRIS_TEXTO)
    e.liberar(p)
    e.guardar(ruta)


PALETA = ((0, 114, 189), (217, 83, 25), (237, 177, 32), (126, 47, 142), (119, 172, 48),
          (77, 190, 238), (162, 20, 47))


def xy_a_emf(chart, ruta, ancho=1000, alto=700, max_puntos=4000):
    """Un `vtkChartXY` con líneas a EMF, todo vectorial."""
    n_plots = chart.GetNumberOfPlots()
    series = []
    for i in range(n_plots):
        plot = chart.GetPlot(i)
        tabla = plot.GetInput()
        if tabla is None or tabla.GetNumberOfColumns() < 2:
            continue
        x = numpy_support.vtk_to_numpy(tabla.GetColumn(0)).astype(np.float64)
        y = numpy_support.vtk_to_numpy(tabla.GetColumn(1)).astype(np.float64)
        if x.size > max_puntos:
            paso = int(np.ceil(x.size / max_puntos))
            x, y = x[::paso], y[::paso]
        try:
            c = plot.GetPen().GetColorObject()
            rgb = [c.GetRed(), c.GetGreen(), c.GetBlue()]
        except Exception:
            rgb = list(PALETA[i % len(PALETA)])
        series.append((x, y, tuple(int(v) for v in rgb)))
    if not series:
        raise ValueError("La gráfica no contiene datos que exportar.")

    e = EmfWriter(ancho, alto)
    (x0, y0, x1, y1), to_x, to_y = _ejes(chart, ancho, alto, (95, 40, 52, 78), e,
                                        chart.GetTitle() or "")
    for x, y, color in series:
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 2:
            continue
        p = e.pluma(color, 1)
        px = np.clip(to_x(x[ok]), -30000, 30000)
        py = np.clip(to_y(y[ok]), -30000, 30000)
        e.polilinea(px, py)
        e.liberar(p)
    e.guardar(ruta)


def chart_a_emf(chart, ruta, ancho=1000, alto=700):
    """Elige el dibujo según el tipo de gráfica."""
    if isinstance(chart, vtk.vtkChartHistogram2D):
        return heatmap_a_emf(chart, ruta, ancho, alto)
    if isinstance(chart, vtk.vtkChartXY):
        return xy_a_emf(chart, ruta, ancho, alto)
    raise ValueError("Este tipo de gráfica no se puede exportar a EMF.")

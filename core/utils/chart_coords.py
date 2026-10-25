"""Conversion entre pixeles de la escena VTK y coordenadas de datos de un grafico.

Funciones puras sobre un `vtkChartXY` (o `vtkChartHistogram2D`, que hereda de
el). Las coordenadas de pantalla son las de VTK: origen abajo a la izquierda,
las mismas que devuelve `interactor.GetEventPosition()`.

Es la misma cuenta que hace `MeasurementService._screen_to_plot`, sin el
estado propio de la medicion (rangos guardados, eje invertido).
"""

import vtk


def _xy(v):
    if isinstance(v, (tuple, list)) and len(v) >= 2:
        return float(v[0]), float(v[1])
    if hasattr(v, "GetX") and hasattr(v, "GetY"):
        return float(v.GetX()), float(v.GetY())
    return None, None


def plot_rect_pixels(chart):
    """Rectangulo del area de trazado (x_min, x_max, y_min, y_max) en pixeles
    de la escena, o None si el grafico aun no tiene geometria."""
    try:
        x1, y1 = _xy(chart.GetPoint1())
        x2, y2 = _xy(chart.GetPoint2())
    except Exception:
        return None
    if None in (x1, y1, x2, y2) or x2 <= x1 or y2 <= y1:
        return None
    return x1, x2, y1, y2


def _axis_range(axis):
    lo, hi = float(axis.GetMinimum()), float(axis.GetMaximum())
    log = False
    try:
        log = bool(axis.GetLogScaleActive())
    except Exception:
        pass
    return lo, hi, log


def current_ranges(chart):
    """Rangos visibles de los ejes inferior e izquierdo (tras zoom/pan)."""
    try:
        ax_x = chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_y = chart.GetAxis(vtk.vtkAxis.LEFT)
    except Exception:
        return None
    if ax_x is None or ax_y is None:
        return None
    return {"x": _axis_range(ax_x), "y": _axis_range(ax_y)}


def _interp(p, p_min, p_max, v_min, v_max, log):
    v = v_min + (p - p_min) * (v_max - v_min) / (p_max - p_min)
    # Con escala logaritmica el eje guarda log10 del valor
    return 10.0 ** v if log else v


def screen_to_plot(chart, sx, sy):
    """Pixel de la escena -> (x, y) en unidades de los ejes. None si el punto
    cae fuera del area de trazado o el grafico no tiene rangos validos."""
    rect = plot_rect_pixels(chart)
    rng = current_ranges(chart) if rect is not None else None
    if rect is None or rng is None:
        return None
    x_min_px, x_max_px, y_min_px, y_max_px = rect
    if not (x_min_px <= sx <= x_max_px and y_min_px <= sy <= y_max_px):
        return None
    x_min, x_max, x_log = rng["x"]
    y_min, y_max, y_log = rng["y"]
    if x_max == x_min or y_max == y_min:
        return None
    return (_interp(sx, x_min_px, x_max_px, x_min, x_max, x_log),
            _interp(sy, y_min_px, y_max_px, y_min, y_max, y_log))


def chart_at_pixel(charts, sx, sy):
    """El grafico cuya area de trazado contiene el pixel (para paneles con
    varios graficos apilados en una misma escena)."""
    for ch in charts or []:
        rect = plot_rect_pixels(ch)
        if rect is None:
            continue
        x_min_px, x_max_px, y_min_px, y_max_px = rect
        if x_min_px <= sx <= x_max_px and y_min_px <= sy <= y_max_px:
            return ch
    return None


def axis_titles(chart):
    """Titulos de los ejes inferior e izquierdo ("" si no tienen)."""
    try:
        return (chart.GetAxis(vtk.vtkAxis.BOTTOM).GetTitle() or "",
                chart.GetAxis(vtk.vtkAxis.LEFT).GetTitle() or "")
    except Exception:
        return "", ""

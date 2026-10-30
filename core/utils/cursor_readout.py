"""Valores X/Y bajo el cursor en las graficas VTK.

`CursorReadout.attach(vtk_widget, get_charts)` engancha un observador de
`MouseMoveEvent` al interactor del widget y muestra la posicion del cursor en
unidades de los ejes:

- en una etiqueta pequena en la esquina del propio grafico, y
- en la barra de estado de la ventana principal (`mainwin.cursor_readout`).

Es la posicion libre del cursor, no el punto de datos mas cercano.

Muchos plugins recrean su `VTKContextMenu` en cada render sobre el mismo
widget. Por eso `attach` es idempotente: hay un solo observador por widget y
cada llamada solo actualiza de donde salen los graficos.
"""

from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtWidgets import QLabel

<<<<<<< HEAD
=======
from core.utils.vtk_observers import observar
>>>>>>> f19cc48027c8d0790d3a1557c7f2977055e15238
from core.utils.chart_coords import screen_to_plot, chart_at_pixel, axis_titles, plot_rect_pixels


def format_value(v: float) -> str:
    """Numero corto y legible: 0.2341, -12.08, 1.234e-05."""
    if v == 0:
        return "0"
    return f"{v:.5g}"


def format_readout(x: float, y: float, x_title: str = "", y_title: str = "") -> str:
    xs = f"X = {format_value(x)}"
    ys = f"Y = {format_value(y)}"
    if x_title:
        xs += f"  [{x_title}]"
    if y_title:
        ys += f"  [{y_title}]"
    return f"{xs}     {ys}"


class CursorReadout(QObject):

    _ATTR = "_gamma_cursor_readout"

    @classmethod
    def attach(cls, vtk_widget, get_charts):
        """Instala (una sola vez por widget) la lectura del cursor.

        `get_charts`: funcion sin argumentos que devuelve la lista de graficos
        actuales del widget; se consulta en cada movimiento, asi que sigue
        valiendo despues de un re-render.
        """
        if vtk_widget is None:
            return None
        existing = getattr(vtk_widget, cls._ATTR, None)
        if existing is not None:
            existing._get_charts = get_charts
            return existing
        readout = cls(vtk_widget, get_charts)
        setattr(vtk_widget, cls._ATTR, readout)
        return readout

    def __init__(self, vtk_widget, get_charts):
        super().__init__(vtk_widget)
        self._widget = vtk_widget
        self._get_charts = get_charts
        self._overlay = None
        self._last_text = None

<<<<<<< HEAD
        iren = vtk_widget.GetRenderWindow().GetInteractor()
        # Prioridad baja: corre despues de los observadores de la medicion y
        # no devuelve nada, asi que no interfiere con ellos.
        self._observer = iren.AddObserver("MouseMoveEvent", self._on_mouse_move, -1.0)
=======
        # Prioridad baja: corre despues de los observadores de la medicion y
        # no devuelve nada, asi que no interfiere con ellos.
        self._observer = observar(vtk_widget, "MouseMoveEvent", self._on_mouse_move, -1.0)
>>>>>>> f19cc48027c8d0790d3a1557c7f2977055e15238
        vtk_widget.installEventFilter(self)

    # ---------- eventos ----------
    def _on_mouse_move(self, obj, evt):
        try:
            sx, sy = obj.GetEventPosition()
            charts = self._charts()
            chart = chart_at_pixel(charts, sx, sy)
            xy = screen_to_plot(chart, sx, sy) if chart is not None else None
            if xy is None:
                self._show(None)
                return
            x_title, y_title = axis_titles(chart)
            self._show(xy, x_title, y_title, plot_rect_pixels(chart))
        except Exception:
            # Nunca romper la interaccion del grafico por la lectura
            self._show(None)

    def eventFilter(self, obj, event):
        if obj is self._widget and event.type() == QEvent.Leave:
            self._show(None)
        return False

    def _charts(self):
        try:
            charts = self._get_charts() if self._get_charts else []
        except Exception:
            return []
        if charts is None:
            return []
        if not isinstance(charts, (list, tuple)):
            charts = [charts]
        # Solo graficos con ejes (la brujula de PAC es un vtkPythonItem)
        return [c for c in charts if c is not None and hasattr(c, "GetAxis") and hasattr(c, "GetPoint1")]

    # ---------- salida ----------
    def _status_label(self):
        try:
            win = self._widget.window()
        except RuntimeError:
            return None
        return getattr(win, "cursor_readout", None)

    def _place_overlay(self, overlay, rect):
        """Esquina superior derecha del area de trazado del grafico bajo el
        cursor. Asi sigue al grafico correcto en paneles apilados o con scroll.
        Los pixeles de VTK tienen el origen abajo y estan escalados por el DPR."""
        margin = 6
        w = self._widget
        if rect is None:
            overlay.move(max(0, w.width() - overlay.width() - margin), margin)
            return
        dpr = w.devicePixelRatioF() or 1.0
        _, x_max_px, _, y_max_px = rect
        x = int(x_max_px / dpr) - overlay.width() - margin
        y = int(w.height() - y_max_px / dpr) + margin
        overlay.move(max(0, x), max(0, y))

    def _ensure_overlay(self):
        if self._overlay is None:
            lbl = QLabel(self._widget)
            lbl.setObjectName("cursorOverlayLabel")
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            # Nativa para quedar por encima del render OpenGL de VTK
            lbl.setAttribute(Qt.WA_NativeWindow, True)
            lbl.hide()
            self._overlay = lbl
        return self._overlay

    def _show(self, xy, x_title="", y_title="", rect=None):
        text = None if xy is None else format_readout(xy[0], xy[1], x_title, y_title)
        if text == self._last_text:
            return
        self._last_text = text

        status = self._status_label()
        if status is not None:
            try:
                status.setText(text or "")
            except RuntimeError:
                pass

        try:
            overlay = self._ensure_overlay()
            if text is None:
                overlay.hide()
                return
            overlay.setText(f"X = {format_value(xy[0])}   Y = {format_value(xy[1])}")
            overlay.ensurePolished()
            overlay.adjustSize()
            self._place_overlay(overlay, rect)
            overlay.show()
            overlay.raise_()
        except RuntimeError:
            self._overlay = None

"""Al hacer zoom no se pierde definición (Trials, PAC y el submuestreo compartido).

Dos defectos, comprobados con 17613000.abf (10,1 kHz, trials de 4,5 s):

1. `indices_reducidos` partía la ventana en tramos de `n // 1000` muestras y lo
   que sobraba al final quedaba en solo 2 puntos, que se dibujaban como una
   recta. Con 2999 muestras visibles era un tercio de la ventana: un hueco de
   86 ms sin dibujar, cuando entre muestras hay 0,1 ms.
2. Trials y los paneles de señal de PAC dibujaban a lo sumo 2000 puntos. El
   investigador tiene que ver el trial con todas sus muestras, haga zoom o no.
"""
import numpy as np
import pytest
import vtk

from core.model.trial_dataset import TrialDataset
from core.utils import submuestreo as sm
from core.utils.submuestreo import MAX_PUNTOS, MAX_PUNTOS_DETALLE, indices_reducidos, recortar

FS = 10101.0


def _ruido(n, semilla=0):
    return np.random.default_rng(semilla).standard_normal(n).cumsum()


@pytest.mark.parametrize("n", [2001, 2500, 2999, 3999, 4999, 6263, 9999, 45454])
def test_los_tramos_cubren_toda_la_serie_sin_dejar_huecos(n):
    y = _ruido(n)
    idx = indices_reducidos(y)
    assert len(idx) <= MAX_PUNTOS + 2
    assert idx[0] == 0 and idx[-1] == n - 1
    # Dos puntos dibujados seguidos nunca quedan más lejos que dos tramos
    tramo = -(-n // (MAX_PUNTOS // 2))
    hueco = int(np.max(np.diff(idx)))
    assert hueco <= 2 * tramo, (
        f"con {n} muestras quedó un hueco de {hueco} muestras sin dibujar (tramo de {tramo})")


def test_el_zoom_no_deja_una_recta_al_final_de_la_ventana():
    """El caso medido: ventana de 1,600 a 1,896 s, 2990 muestras visibles."""
    t = np.arange(45454) / FS - 0.5
    y = _ruido(t.size, 1)
    lo, hi = 1.60, 1.60 + 2990 / FS
    xs, _ = recortar(t, y, lo, hi)
    hueco_ms = float(np.max(np.diff(xs))) * 1000
    assert hueco_ms < 1.0, f"hueco de {hueco_ms:.1f} ms dibujado como recta (antes: 86 ms)"


def test_los_picos_del_final_siguen_apareciendo():
    """Los picos de la parte que antes quedaba como cola tienen que dibujarse.

    De la cola solo se guardaban su máximo y su mínimo: de estos cuatro picos
    se veían dos, y los otros desaparecían dentro de la recta.
    """
    n = 2999
    y = np.zeros(n)
    picos = {2300: 3.0, 2500: 5.0, 2700: -5.0, 2900: 4.0}
    for i, v in picos.items():
        y[i] = v
    idx = set(indices_reducidos(y).tolist())
    faltan = [i for i in picos if i not in idx]
    assert not faltan, f"picos sin dibujar en las muestras {faltan}"


def test_una_serie_del_tamano_de_un_trial_se_dibuja_completa():
    x = np.arange(45454) / FS
    chart = vtk.vtkChartXY()
    plot = sm.agregar_linea(chart, x, _ruido(x.size), "t", "y", n_max=MAX_PUNTOS_DETALLE)
    assert plot.GetInput().GetNumberOfRows() == x.size
    assert getattr(chart, "_submuestreo", None) is None, "sin reducir no hace falta el controlador"


def _trial_dataset(n_muestras=45454, n_trials=3):
    t = np.arange(n_muestras) / FS - 0.5
    trials = np.column_stack([_ruido(n_muestras, s) for s in range(n_trials)])
    return TrialDataset(source="x.abf", sampling_rate=FS, channel_index=0, channel_name="vM1",
                        unit="mV", t0=float(t[0]), t1=float(t[-1]), time_rel=t, trials=trials,
                        onsets_s=[1.0 * i for i in range(n_trials)])


def test_trials_dibuja_todas_las_muestras_del_trial():
    from plugins.preprocessing.trials.trials_plugin import TrialsPlugin
    p = object.__new__(TrialsPlugin)
    vista = vtk.vtkContextView()
    vista.GetRenderWindow().SetOffScreenRendering(1)
    p.vtk_view = vista
    p.vtk_menu = None
    p.visible_trials = [1]
    p._log = lambda *a, **k: None
    td = _trial_dataset()

    p._render_trials(td)

    tabla = p.chart.GetPlot(0).GetInput()
    assert tabla.GetNumberOfRows() == td.trials.shape[0], (
        f"se dibujaron {tabla.GetNumberOfRows()} de {td.trials.shape[0]} muestras")
    y = np.array([tabla.GetColumn(1).GetValue(i) for i in (0, 12345, td.trials.shape[0] - 1)])
    assert np.allclose(y, td.trials[[0, 12345, -1], 1]), "es el trial 2, sin tocar"


def _pac():
    from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin
    p = object.__new__(Pac_plugin)
    p.ui = None
    return p


def test_los_paneles_de_senal_de_pac_dibujan_todas_las_muestras():
    t = np.arange(45454) / FS
    chart = _pac()._grafico_senal(t, _ruido(t.size), "Original")
    assert chart.GetPlot(0).GetInput().GetNumberOfRows() == t.size


def test_los_ciclos_de_pac_se_dibujan_completos():
    pila = np.column_stack([_ruido(3000, s) for s in range(5)])
    chart = _pac()._grafico_ciclos(pila, pila.mean(axis=1), "Ciclos", (200, 30, 30))
    filas = [chart.GetPlot(i).GetInput().GetNumberOfRows() for i in range(chart.GetNumberOfPlots())]
    assert filas == [3000] * 6, f"filas dibujadas por serie: {filas}"


# ============================================================
#   3. La rueda acercaba también el eje Y y la señal se perdía
# ============================================================
# Con 15 pasos sobre un trial, la ventana vertical quedaba en 0,006 mV y la señal
# ocupaba 0,085 mV: solo el 10 % de las muestras caía dentro y se veían rayas.
from PyQt5.QtCore import Qt  # noqa: E402

from core.utils.ajuste_vertical import AjusteVertical  # noqa: E402
from core.utils.vtk_context_menu import EJE_X, EJE_Y, VTKContextMenu  # noqa: E402


def _menu(chart):
    menu = VTKContextMenu.__new__(VTKContextMenu)     # solo la lógica del zoom
    menu.chart = chart
    return menu


def test_en_una_senal_la_rueda_acerca_solo_el_tiempo_y_en_un_mapa_los_dos_ejes():
    linea, mapa = vtk.vtkChartXY(), vtk.vtkChartHistogram2D()
    assert _menu(linea)._ejes_del_zoom(linea) == (True, False)
    assert _menu(mapa)._ejes_del_zoom(mapa) == (True, True)
    assert _menu(linea)._ejes_del_zoom(linea, Qt.ControlModifier) == (True, False)
    assert _menu(linea)._ejes_del_zoom(linea, Qt.ShiftModifier) == (False, True)


def test_el_modo_elegido_en_el_menu_no_se_pierde_con_la_rueda():
    """Antes cada giro de la rueda volvía a poner X+Y."""
    linea = vtk.vtkChartXY()
    menu = _menu(linea)
    menu.set_zoom_mode("xy")
    assert menu._ejes_del_zoom(linea) == (True, True)
    menu.set_zoom_mode("x")
    assert menu._ejes_del_zoom(linea) == (True, False)


def _senal_lenta_y_rapida(n=45454):
    t = np.arange(n) / FS - 0.5
    y = 0.08 * np.sin(2 * np.pi * 2 * t) + 0.002 * np.sin(2 * np.pi * 300 * t)
    return t, np.round(y / 0.0025) * 0.0025            # cuantizada como el conversor


def _vista_con_rueda(chart):
    vista = vtk.vtkContextView()
    rw = vista.GetRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.SetSize(775, 600)
    vista.GetScene().AddItem(chart)
    chart.SetZoomWithMouseWheel(True)
    iren = vtk.vtkGenericRenderWindowInteractor()
    iren.SetRenderWindow(rw)
    estilo = vtk.vtkContextInteractorStyle()
    estilo.SetScene(vista.GetScene())
    iren.SetInteractorStyle(estilo)
    iren.Initialize()
    rw.Render()
    menu = _menu(chart)

    def rueda(n):
        for _ in range(n):
            x, y = menu._ejes_del_zoom(chart)           # lo que hace custom_wheel_event
            chart.SetAxisZoom(EJE_X, x)
            chart.SetAxisZoom(EJE_Y, y)
            menu._ajuste_de(chart, x and not y)
            iren.SetEventInformationFlipY(387, 300, 0, 0)
            iren.MouseWheelForwardEvent()
            rw.Render()
    return menu, rueda, rw


def _ventanas(chart):
    bx, ly = chart.GetAxis(EJE_X), chart.GetAxis(EJE_Y)
    return (bx.GetMinimum(), bx.GetMaximum()), (ly.GetMinimum(), ly.GetMaximum())


def test_al_acercar_con_la_rueda_la_senal_sigue_entera_en_pantalla():
    t, y = _senal_lenta_y_rapida()
    chart = vtk.vtkChartXY()
    sm.agregar_linea(chart, t, y, "t", "y", n_max=MAX_PUNTOS_DETALLE)
    _, rueda, _rw = _vista_con_rueda(chart)
    rueda(15)
    (x0, x1), (y0, y1) = _ventanas(chart)
    assert x1 - x0 < 0.5, "la rueda sí acercó el tiempo"
    m = (t >= x0) & (t <= x1)
    dentro = np.mean((y[m] >= y0) & (y[m] <= y1))
    assert dentro == 1.0, f"solo el {dentro:.0%} de las muestras quedó dentro de la ventana"
    amplitud = y[m].max() - y[m].min()
    assert y1 - y0 <= 1.2 * amplitud, "el eje Y se ajusta a lo que se ve, no a todo el trial"


def test_reset_devuelve_el_eje_y_que_puso_el_plugin():
    t, y = _senal_lenta_y_rapida(5000)
    chart = vtk.vtkChartXY()
    sm.agregar_linea(chart, t, y, "t", "y", n_max=MAX_PUNTOS_DETALLE)
    eje_y = chart.GetAxis(EJE_Y)
    eje_y.SetBehavior(vtk.vtkAxis.FIXED)
    eje_y.SetRange(-0.2, 0.2)                           # p. ej. el margen del histograma de PAC
    menu, rueda, _rw = _vista_con_rueda(chart)
    rueda(10)
    assert _ventanas(chart)[1] != (-0.2, 0.2)
    menu.reset_zoom()
    assert _ventanas(chart)[1] == (-0.2, 0.2) and eje_y.GetBehavior() == vtk.vtkAxis.FIXED


def test_sin_zoom_el_ajuste_no_toca_el_eje_y():
    chart = vtk.vtkChartXY()
    t, y = _senal_lenta_y_rapida(5000)
    sm.agregar_linea(chart, t, y, "t", "y", n_max=MAX_PUNTOS_DETALLE)
    chart.GetAxis(EJE_Y).SetRange(-1.0, 1.0)
    AjusteVertical.de(chart)                            # creado pero no activado
    chart.GetAxis(EJE_X).SetRange(0.0, 0.1)
    assert _ventanas(chart)[1] == (-1.0, 1.0)


def test_el_boton_mas_de_la_cinta_acerca_el_tiempo_y_reset_lo_devuelve():
    t, y = _senal_lenta_y_rapida(5000)
    chart = vtk.vtkChartXY()
    sm.agregar_linea(chart, t, y, "t", "y", n_max=MAX_PUNTOS_DETALLE)
    menu, _, rw = _vista_con_rueda(chart)
    (x0, x1), _ = _ventanas(chart)
    for _ in range(5):
        menu.zoom_by_factor(0.8)
    (a, b), (c, d) = _ventanas(chart)
    assert b - a < 0.5 * (x1 - x0)
    m = (t >= a) & (t <= b)
    assert y[m].min() >= c and y[m].max() <= d
    menu.reset_zoom()
    rw.Render()
    assert np.allclose(_ventanas(chart)[0], (x0, x1)), "antes el eje X quedaba fijo y Reset no lo devolvía"


# ============================================================
#   4. En PAC la rueda bajaba la página mientras hacía zoom
# ============================================================
# PAC apila sus paneles en un lienzo alto dentro de un QScrollArea. El gráfico
# hacía zoom pero dejaba el evento sin aceptar, y Qt se lo pasaba al contenedor:
# la página bajaba y el gráfico se iba de la vista.
from types import SimpleNamespace as _NS  # noqa: E402


class _RuedaFalsa:
    def __init__(self, x, y):
        self._x, self._y = x, y
        self.aceptado = None

    def pos(self):
        return _NS(x=lambda: self._x, y=lambda: self._y)

    def accept(self):
        self.aceptado = True

    def ignore(self):
        self.aceptado = False


def _pila_como_pac(alto=1200):
    """Dos gráficos apilados con altura fija, como los dispone PAC."""
    vista = vtk.vtkContextView()
    rw = vista.GetRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.SetSize(800, alto)
    graficos = []
    for y0 in (alto - 16 - 300, alto - 16 - 300 - 52 - 170):     # mapa arriba, histograma debajo
        ch = vtk.vtkChartXY()
        ch.SetAutoSize(False)
        h = 300 if not graficos else 170
        ch.SetSize(vtk.vtkRectf(12, y0, 776, h))
        t, y = _senal_lenta_y_rapida(500)
        sm.agregar_linea(ch, t, y, "t", "y")
        vista.GetScene().AddItem(ch)
        graficos.append(ch)
    rw.Render()
    return vista, graficos


def test_la_rueda_sobre_un_grafico_no_baja_la_pagina_y_entre_graficos_si(app=None):
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    vista, graficos = _pila_como_pac()
    llamadas = []
    widget = _NS(height=lambda: 1200, wheelEvent=lambda ev: llamadas.append(ev))
    menu = VTKContextMenu.__new__(VTKContextMenu)
    menu.chart = graficos
    menu.vtk_widget = widget
    menu._install_wheel_shortcuts()

    sobre_el_mapa = _RuedaFalsa(400, 16 + 150)            # coordenadas de Qt: y desde arriba
    widget.wheelEvent(sobre_el_mapa)
    assert llamadas, "la rueda le llega a VTK para el zoom"
    assert sobre_el_mapa.aceptado is True, "aceptado: el contenedor no baja la página"

    en_el_hueco = _RuedaFalsa(400, 16 + 300 + 26)
    widget.wheelEvent(en_el_hueco)
    assert en_el_hueco.aceptado is False, "fuera de los gráficos la rueda sigue moviendo la página"
    assert menu._grafico_bajo(_RuedaFalsa(400, 16 + 300 + 52 + 85)) is graficos[1]

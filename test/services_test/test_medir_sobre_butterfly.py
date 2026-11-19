"""Medir sobre el butterfly: el clic toma la curva más cercana (un trial o el promedio)."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import vtk

from core.services.measurement_service import SesionDeMedicion
from core.utils.submuestreo import agregar_linea

T = np.linspace(0.0, 1.0, 101)
RECT = (0.0, 1000.0, 0.0, 1000.0)


def _a_pantalla(x, y):
    return x * 1000.0, (y + 10.0) * 50.0


def _a_datos(sx, sy):
    return sx / 1000.0, sy / 50.0 - 10.0


def _butterfly():
    """Trials con pendiente 1, 4 y 8 y su promedio, etiquetados como en el ERP."""
    chart = vtk.vtkChartXY()
    curvas = {}
    for k, m in ((1, 1.0), (2, 4.0), (3, 8.0)):
        y = m * T
        pl = agregar_linea(chart, T, y, "time", f"trial_{k}")
        pl.SetLabel(f"Trial {k}")
        curvas[k] = y
    prom = np.mean(np.vstack(list(curvas.values())), axis=0)
    agregar_linea(chart, T, prom, "time", "average").SetLabel("Average")
    return chart, curvas, prom


def _sesion(chart):
    almacen = {"measurements": []}
    svc = SesionDeMedicion(Mock(), Mock(), Mock(return_value=chart),
                           lambda k, d=None: almacen.get(k, d),
                           lambda k, v: almacen.__setitem__(k, v))
    svc.alerts = Mock()
    svc.set_context(plugin="erp", view_id="erp", graph_id="butterfly", channel_name="s:CA1")
    svc._plot_rect_pixels = lambda: RECT
    svc._screen_to_plot = _a_datos
    svc._plot_to_screen = _a_pantalla
    svc._suspend_left_actions = lambda on: None
    svc._add_overlay_for_points = Mock()
    return svc, almacen


def _clic(svc, x, y):
    sx, sy = _a_pantalla(x, y)
    svc.on_left_release(sx, sy)


def test_las_curvas_del_butterfly_dicen_de_que_trial_son():
    chart, _, _ = _butterfly()
    svc, _ = _sesion(chart)
    series = svc._series_of_chart(chart)
    assert [s["label"] for s in series] == ["Trial 1", "Trial 2", "Trial 3", "Average"]
    assert [s["ctx"] for s in series] == [{"trial_id": 0}, {"trial_id": 1}, {"trial_id": 2},
                                          {"graph_id": "average"}]


def test_slope_sobre_un_trial_del_butterfly():
    chart, curvas, _ = _butterfly()
    svc, almacen = _sesion(chart)
    svc.start("slope")
    _clic(svc, 0.2, curvas[2][20])
    assert svc.state == "waiting_p2"
    _clic(svc, 0.8, curvas[2][80] + 0.05)
    (m,) = almacen["measurements"]
    assert m["slope"] == pytest.approx(4.0)
    assert m["ctx"]["trial_id"] == 1 and m["ctx"]["plugin"] == "erp"


def test_amplitude_sobre_el_promedio():
    chart, _, prom = _butterfly()
    svc, almacen = _sesion(chart)
    svc.start("amplitude")
    _clic(svc, 0.0, prom[0])
    _clic(svc, 1.0, prom[100])
    (m,) = almacen["measurements"]
    assert m["amp_pp"] == pytest.approx(prom.max() - prom.min())
    assert m["ctx"]["graph_id"] == "average" and m["ctx"].get("trial_id") is None


def test_difference_sobre_un_trial():
    chart, curvas, _ = _butterfly()
    svc, almacen = _sesion(chart)
    svc.start("difference")
    _clic(svc, 0.1, curvas[3][10])
    _clic(svc, 0.9, curvas[3][90])
    (m,) = almacen["measurements"]
    assert m["type"] == "difference" and m["d_mean"] == pytest.approx(8.0)
    assert m["ctx"]["trial_id"] == 2


def test_un_clic_lejos_de_toda_curva_no_avanza():
    chart, _, _ = _butterfly()
    svc, almacen = _sesion(chart)
    svc.start("slope")
    _clic(svc, 0.5, -9.0)
    assert svc.state == "waiting_p1" and not almacen["measurements"]


def test_las_lineas_de_medicion_no_cuentan_como_curvas():
    chart, curvas, _ = _butterfly()
    svc, _ = _sesion(chart)
    del svc._add_overlay_for_points
    svc.vtk_widget = Mock()
    svc._add_overlay_for_points("slope-001", (0.2, 0.2), (0.8, 0.8))
    assert len(svc._series_of_chart(chart)) == 4


def test_la_cinta_usa_el_menu_vivo_del_plugin_en_pantalla():
    from app.view.main_window import MainWindow
    viejo, nuevo = SimpleNamespace(measure_service="viejo"), SimpleNamespace(measure_service="nuevo")
    mw = SimpleNamespace(_active_vtk_menu=viejo, active_plugin=SimpleNamespace(vtk_menu=nuevo))
    mw._live_vtk_menu = MainWindow._live_vtk_menu.__get__(mw)
    assert MainWindow._get_active_measure_service(mw) == "nuevo"
    mw.active_plugin = SimpleNamespace(vtk_menu=None)
    assert MainWindow._get_active_measure_service(mw) == "nuevo"

"""Tras un zoom, medir no debe 'borrar' el resto del trial, y Reset view debe volver al registro completo.

Las curvas largas (butterfly) se recortan al tramo visible al hacer zoom. Antes, al
añadir la línea de una medida, VTK recalculaba los ejes con esas tablas recortadas y la
vista quedaba pegada a la ventana; Reset view tampoco lo arreglaba.
"""
from unittest.mock import Mock

import numpy as np
import pytest
import vtk

from core.services.measurement_service import SesionDeMedicion
from core.utils.submuestreo import agregar_linea, rango_x_completo, restablecer_vista

T = np.arange(-0.1, 3.0, 0.001)


def _grafico():
    view = vtk.vtkContextView()
    rw = view.GetRenderWindow()
    rw.SetSize(600, 400)
    rw.SetOffScreenRendering(1)
    ch = vtk.vtkChartXY()
    view.GetScene().AddItem(ch)
    rng = np.random.default_rng(0)
    for k in range(3):
        agregar_linea(ch, T, 0.02 * rng.standard_normal(T.size), "time", f"trial_{k + 1}").SetLabel(f"Trial {k + 1}")
    rw.Render()
    return view, ch


def _zoom(view, ch, lo=0.0, hi=0.2):
    ch.GetAxis(vtk.vtkAxis.BOTTOM).SetRange(lo, hi)
    view.GetRenderWindow().Render()


def _rango_x(ch):
    b = ch.GetAxis(vtk.vtkAxis.BOTTOM)
    return b.GetMinimum(), b.GetMaximum()


def test_reset_view_vuelve_al_registro_completo_tras_un_zoom():
    view, ch = _grafico()
    _zoom(view, ch)
    assert ch.GetPlot(0).GetInput().GetNumberOfRows() < 400
    restablecer_vista(ch)
    view.GetRenderWindow().Render()
    lo, hi = _rango_x(ch)
    assert lo <= T[0] and hi >= T[-1] - 1e-9
    assert rango_x_completo(ch) == pytest.approx((T[0], T[-1]))


@pytest.mark.parametrize("tipo", ["slope", "amplitude", "difference"])
def test_medir_con_zoom_no_mueve_la_vista(tipo):
    view, ch = _grafico()
    _zoom(view, ch)
    svc = SesionDeMedicion(Mock(), view, lambda: ch, lambda k, d=None: [], lambda k, v: None)
    svc.alerts = Mock()
    svc.start(tipo)
    svc._current["p1"] = (0.02, 0.0)
    svc._current["p2"] = (0.15, 0.0)
    svc._finalize()
    view.GetRenderWindow().Render()
    assert _rango_x(ch) == pytest.approx((0.0, 0.2))
    restablecer_vista(ch)
    view.GetRenderWindow().Render()
    lo, hi = _rango_x(ch)
    assert lo <= T[0] and hi >= T[-1] - 1e-9


def test_reset_de_un_grafico_sin_series_reducidas_no_cambia():
    view = vtk.vtkContextView()
    ch = vtk.vtkChartXY()
    view.GetScene().AddItem(ch)
    agregar_linea(ch, np.linspace(0, 1, 50), np.linspace(0, 1, 50))
    assert rango_x_completo(ch) is None
    restablecer_vista(ch)

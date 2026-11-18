"""La derivada de 'difference' (eje derecho) y las líneas de medida no deben estirar el eje mV.

Con el ajuste vertical activo (tras un zoom), medir 'difference' llevaba el eje izquierdo
de ±0.1 mV a −240..100 y el trial quedaba aplastado en una línea.
"""
from unittest.mock import Mock

import numpy as np
import pytest
import vtk

from core.services.measurement_service import SesionDeMedicion
from core.utils.ajuste_vertical import AjusteVertical, rango_visible_y
from core.utils.submuestreo import agregar_linea

T = np.arange(-0.05, 4.0, 0.0001)


def _trial():
    rng = np.random.default_rng(3)
    y = 0.03 * np.sin(2 * np.pi * 3 * T) + 0.01 * rng.standard_normal(T.size)
    return y


def _grafico():
    view = vtk.vtkContextView()
    rw = view.GetRenderWindow()
    rw.SetSize(600, 400)
    rw.SetOffScreenRendering(1)
    ch = vtk.vtkChartXY()
    view.GetScene().AddItem(ch)
    y = _trial()
    agregar_linea(ch, T, y, "time", "trial_1").SetLabel("Trial 1")
    rw.Render()
    ajuste = AjusteVertical.de(ch)
    ajuste.activar()
    ch.GetAxis(vtk.vtkAxis.BOTTOM).SetRange(1.0, 1.9)
    rw.Render()
    return view, ch, y


def _rango_y(ch):
    a = ch.GetAxis(vtk.vtkAxis.LEFT)
    return a.GetMinimum(), a.GetMaximum()


@pytest.mark.parametrize("tipo", ["difference", "slope", "amplitude", "difference_all_trials"])
def test_medir_no_estira_el_eje_mv(tipo):
    view, ch, y = _grafico()
    antes = _rango_y(ch)
    assert antes[1] - antes[0] < 0.5
    svc = SesionDeMedicion(Mock(), view, lambda: ch, lambda k, d=None: [], lambda k, v: None)
    svc.alerts = Mock()
    svc.trials_source = lambda: (T, y[:, None], [0])
    svc.set_context(plugin="trials", trial_id=0, graph_id="trial 0")
    svc.start(tipo)
    svc._current["p1"] = (1.40, 0.0)
    svc._current["p2"] = (1.42, 0.0)
    svc._finalize()
    view.GetRenderWindow().Render()
    ch.GetAxis(vtk.vtkAxis.BOTTOM).SetRange(1.05, 1.85)
    view.GetRenderWindow().Render()
    lo, hi = _rango_y(ch)
    assert hi - lo < 0.5, (tipo, lo, hi)


def test_el_rango_visible_ignora_el_eje_derecho():
    view, ch, y = _grafico()
    pl = agregar_linea(ch, T, 1000.0 * y, "time", "deriv")
    ch.SetPlotCorner(pl, 1)
    lo, hi = rango_visible_y(ch, 1.0, 1.9)
    assert hi - lo < 0.5

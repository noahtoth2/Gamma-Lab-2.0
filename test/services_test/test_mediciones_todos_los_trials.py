"""Mediciones 'all trials' (slope, amplitude, difference) y la derivada de 'difference'."""
from unittest.mock import Mock

import numpy as np
import pytest

from core.filters.measurements import derivative_in_window
from core.services.measurement_service import SesionDeMedicion


def _sesion(trials_source=None, contexto=None):
    almacen = {"measurements": []}
    vtk_widget = Mock()
    svc = SesionDeMedicion(Mock(), vtk_widget, Mock(return_value=None),
                           lambda k, d=None: almacen.get(k, d),
                           lambda k, v: almacen.__setitem__(k, v))
    svc.alerts = Mock()
    svc.trials_source = trials_source
    if contexto:
        svc.set_context(**contexto)
    return svc, almacen


def _trials():
    """3 trials lineales con pendientes 1, 2 y 3 sobre t = 0..1 s."""
    t = np.linspace(0.0, 1.0, 101)
    M = np.column_stack([1.0 * t, 2.0 * t, 3.0 * t])
    return t, M, [4, 7, 9]


def _medir(svc, tipo, x1, x2):
    assert svc.start(tipo) is None
    svc._current["p1"] = (x1, 0.0)
    svc._current["p2"] = (x2, 0.0)
    svc._finalize()


def test_la_derivada_de_una_recta_es_su_pendiente():
    t = np.linspace(0, 2, 201)
    r = derivative_in_window(t, 5.0 * t + 1.0, 0.5, 1.5)
    assert r["d_mean"] == pytest.approx(5.0)
    assert r["d_max"] == pytest.approx(5.0) and r["d_min"] == pytest.approx(5.0)
    assert r["n"] == 101


def test_la_derivada_de_un_seno_es_un_coseno():
    t = np.linspace(0, 1, 2001)
    r = derivative_in_window(t, np.sin(2 * np.pi * t), 0.0, 1.0)
    assert r["d_max"] == pytest.approx(2 * np.pi, rel=1e-3)
    assert r["x_at_dmax"] == pytest.approx(0.0, abs=1e-3) or r["x_at_dmax"] == pytest.approx(1.0, abs=1e-3)


def test_la_derivada_es_diff_de_y_entre_diff_de_x():
    x = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    y = np.array([0.0, 1.0, 1.5, 4.5, 4.0])
    r = derivative_in_window(x, y, 0.0, 0.4)
    assert r["d_max"] == pytest.approx(30.0)
    assert r["x_at_dmax"] == pytest.approx(0.25)
    assert r["y_at_dmax"] == pytest.approx(3.0)
    assert r["d_min"] == pytest.approx(-5.0)
    assert r["d_mean"] == pytest.approx(np.mean(np.diff(y) / np.diff(x)))


def test_la_tangente_pasa_por_el_maximo_con_su_pendiente():
    x = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    y = np.array([0.0, 1.0, 1.5, 4.5, 4.0])
    r = derivative_in_window(x, y, 0.0, 0.4)
    (xa, ya), (xb, yb) = r["tangent"]
    assert (yb - ya) / (xb - xa) == pytest.approx(r["d_max"])
    assert (xa + xb) / 2 == pytest.approx(r["x_at_dmax"]) and (ya + yb) / 2 == pytest.approx(r["y_at_dmax"])


def test_la_derivada_necesita_dos_muestras():
    assert derivative_in_window([0.0, 1.0], [0.0, 1.0], 0.4, 0.6) is None


def test_all_trials_sin_trials_en_la_vista_no_arranca():
    svc, _ = _sesion(contexto={"plugin": "fft"})
    assert svc.start("slope_all_trials") is False
    assert svc.start("difference_all_trials") is False
    assert svc.state == "idle"


def test_slope_all_trials_mide_cada_trial_con_su_numero():
    svc, almacen = _sesion(trials_source=_trials)
    _medir(svc, "slope_all_trials", 0.2, 0.8)
    meds = almacen["measurements"]
    assert [m["ctx"]["trial_id"] for m in meds] == [4, 7, 9]
    assert [m["slope"] for m in meds] == pytest.approx([1.0, 2.0, 3.0])
    assert all(m["p1"][0] == pytest.approx(0.2) and m["p2"][0] == pytest.approx(0.8) for m in meds)
    assert len({m["batch"] for m in meds}) == 1 and all(m["all_trials"] for m in meds)
    assert svc.state == "idle"


def test_amplitude_all_trials_una_fila_por_trial():
    svc, almacen = _sesion(trials_source=_trials)
    _medir(svc, "amplitude_all_trials", 0.0, 1.0)
    meds = almacen["measurements"]
    assert [m["type"] for m in meds] == ["amplitude"] * 3
    assert [m["amp_pp"] for m in meds] == pytest.approx([1.0, 2.0, 3.0])


def test_difference_all_trials_marca_el_maximo_de_cada_trial():
    svc, almacen = _sesion(trials_source=_trials)
    _medir(svc, "difference_all_trials", 0.1, 0.9)
    meds = almacen["measurements"]
    assert [m["type"] for m in meds] == ["difference"] * 3
    assert [m["d_max"] for m in meds] == pytest.approx([1.0, 2.0, 3.0])
    for m in meds:
        assert "tangent" not in m and not m.get("overlay_right_axis")
        assert len(m["overlay_pts"]) == 2
        assert tuple(m["overlay_marker"]) == (m["x_at_dmax"], m["y_at_dmax"])


def test_en_trials_cada_medicion_queda_en_la_grafica_de_su_trial():
    svc, almacen = _sesion(trials_source=_trials,
                           contexto={"plugin": "trials", "trial_id": 7, "graph_id": "trial 7"})
    _medir(svc, "slope_all_trials", 0.2, 0.8)
    assert [m["ctx"]["graph_id"] for m in almacen["measurements"]] == ["trial 4", "trial 7", "trial 9"]


def _con_grafico(svc, ids, n_extra=0):
    """Un vtkChartXY real con una curva 'Trial k' por cada id."""
    import vtk
    from core.utils.submuestreo import agregar_linea
    chart = vtk.vtkChartXY()
    t = np.linspace(0.0, 1.0, 101)
    for k in ids:
        agregar_linea(chart, t, (k + 1) * t, "time", f"trial_{k + 1}").SetLabel(f"Trial {k + 1}")
    svc.get_active_chart = Mock(return_value=chart)
    return chart


def _lineas(svc):
    return [o["id"] for o in svc._overlays]


def test_las_lineas_solo_se_dibujan_para_los_trials_en_pantalla():
    svc, almacen = _sesion(trials_source=_trials)
    _con_grafico(svc, [7])
    svc.visible_trial_ids = {7}
    _medir(svc, "slope_all_trials", 0.2, 0.8)
    meds = almacen["measurements"]
    assert len(meds) == 3
    ids = _lineas(svc)
    assert meds[1]["id"] in ids and meds[0]["id"] not in ids and meds[2]["id"] not in ids
    assert sum(i.startswith("batch:") for i in ids) == 2


def _color(ov):
    import vtk
    c = vtk.vtkColor4ub(); ov["line_plot"].GetColorRGBA(c)
    return tuple(c)[:3]


def test_las_lineas_de_slope_son_rojas_y_sin_marcadores():
    svc, almacen = _sesion(trials_source=_trials)
    _con_grafico(svc, [4, 7, 9])
    _medir(svc, "slope_all_trials", 0.2, 0.8)
    lineas = [o for o in svc._overlays if not o["id"].startswith("batch:")]
    assert len(lineas) == 3
    assert all(_color(o) == SesionDeMedicion.SLOPE_COLOR and o["points_plot"] is None for o in lineas)


def test_slope_de_dos_puntos_tambien_es_rojo():
    svc, _ = _sesion()
    _con_grafico(svc, [0])
    svc.start("slope"); svc._current["p1"] = (0.0, 0.0); svc._current["p2"] = (1.0, 1.0)
    svc._finalize()
    assert _color(svc._overlays[-1]) == SesionDeMedicion.SLOPE_COLOR


def test_las_derivadas_llevan_el_color_de_su_trial():
    svc, almacen = _sesion(trials_source=_trials)
    chart = _con_grafico(svc, [4, 7, 9])
    _medir(svc, "difference_all_trials", 0.2, 0.8)
    colores = svc._trial_colors(chart)
    for ov in svc._overlays:
        if ov["id"].startswith("batch:"):
            continue
        tid = next(m["ctx"]["trial_id"] for m in almacen["measurements"] if m["id"] == ov["id"])
        assert _color(ov) == colores[tid]


def test_con_muchos_trials_en_pantalla_solo_se_marcan_los_dos_puntos():
    t = np.linspace(0.0, 1.0, 101)
    ids = list(range(30))
    fuente = lambda: (t, np.column_stack([(k + 1) * t for k in ids]), ids)
    svc, almacen = _sesion(trials_source=fuente)
    _con_grafico(svc, ids)
    _medir(svc, "slope_all_trials", 0.2, 0.8)
    assert len(almacen["measurements"]) == 30
    assert len(_lineas(svc)) == 2 and all(i.startswith("batch:") for i in _lineas(svc))
    assert "groups of 6" in svc.alerts.info.call_args.args[0]


def test_borrar_la_ultima_borra_todo_el_all_trials():
    svc, almacen = _sesion(trials_source=_trials)
    _con_grafico(svc, [4, 7, 9])
    svc.start("slope"); svc._current["p1"] = (0.0, 0.0); svc._current["p2"] = (1.0, 1.0)
    svc._finalize()
    _medir(svc, "slope_all_trials", 0.2, 0.8)
    assert len(almacen["measurements"]) == 4
    assert svc.remove_last_measurement() is True
    assert [m["type"] for m in almacen["measurements"]] == ["slope"]
    assert not any(m.get("batch") for m in almacen["measurements"])
    assert _lineas(svc) == [almacen["measurements"][0]["id"]]


def test_difference_de_una_traza():
    svc, almacen = _sesion()
    t = np.linspace(0, 1, 11)
    svc._ref_data = {"xs": list(t), "ys": list(4.0 * t)}
    svc._add_overlay_for_points = Mock()
    _medir(svc, "difference", 0.0, 1.0)
    (m,) = almacen["measurements"]
    assert m["type"] == "difference" and m["d_mean"] == pytest.approx(4.0)
    kw = svc._add_overlay_for_points.call_args.kwargs
    assert not kw.get("right_axis") and len(kw["points"]) == 2
    assert svc._add_overlay_for_points.call_args.args[1] == pytest.approx((m["x_at_dmax"], m["y_at_dmax"]))

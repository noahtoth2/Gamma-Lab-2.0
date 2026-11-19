"""Butterfly del ERP: el promedio va encima en negro y los trials se ven por grupos."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import vtk
from PyQt5.QtWidgets import QApplication

from core.plugins.meta import PluginMeta


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _erp(qapp, n_trials):
    from plugins.analysis.time.erp.erp_plugin import Erp_plugin
    from plugins.analysis.time.erp.erp_plugin_ui import Ui_ErpPlot
    p = Erp_plugin.__new__(Erp_plugin)
    p.meta = PluginMeta(id="erp", name="ERP", category="Analysis", subcategory="Time", version="1", icon="i",
                        logic_class="Erp_plugin")
    p.view_top = vtk.vtkContextView()
    p.vtk_top = None
    p.alerts = Mock()
    p.active_signal = SimpleNamespace(name="s")
    p.ch_name = "c"
    p.widget = None
    p.vtk_menu = None
    p.ui = Ui_ErpPlot()
    p._trials_used = {"label": "todos"}
    p._t = np.linspace(0, 1, 50)
    p._sel = np.random.default_rng(1).standard_normal((n_trials, 50))
    p._sel_ids = list(range(n_trials))
    p._group_idx = 0
    return p


def _grafico(p):
    return p.view_top.GetScene().GetItem(0)


def _etiquetas(p):
    ch = _grafico(p)
    return [ch.GetPlot(i).GetLabel() for i in range(ch.GetNumberOfPlots())]


def test_el_promedio_se_dibuja_encima_en_negro(qapp):
    p = _erp(qapp, 5)
    p._render_group()
    ch = _grafico(p)
    ultimo = ch.GetPlot(ch.GetNumberOfPlots() - 1)
    assert ultimo.GetLabel() == "Average"
    color = vtk.vtkColor4ub()
    ultimo.GetColorRGBA(color)
    assert list(color)[:3] == [0, 0, 0]
    assert ultimo.GetWidth() == pytest.approx(3.0)


def test_el_promedio_se_puede_ocultar(qapp):
    p = _erp(qapp, 5)
    p.ui.chkShowAverage.setChecked(False)
    p._render_group()
    assert "Average" not in _etiquetas(p)


def test_grupos_de_6(qapp):
    p = _erp(qapp, 14)
    p.ui.cmbGroupSize.setCurrentText("6")
    p._render_group()
    assert _etiquetas(p)[:6] == [f"Trial {i}" for i in range(1, 7)] and len(_etiquetas(p)) == 7
    p._move_group(+1); p._move_group(+1)
    assert _etiquetas(p)[:-1] == ["Trial 13", "Trial 14"]
    assert p.ui.lblGroup.text().startswith("Group 3/3")
    p._move_group(+1)
    assert p._group_idx == 0


def test_grupo_personalizado_y_todos(qapp):
    p = _erp(qapp, 10)
    p.ui.cmbGroupSize.setCurrentText("Custom")
    p.ui.spnGroupSize.setValue(3)
    p._render_group()
    assert len(_etiquetas(p)) == 3 + 1
    assert p._n_groups() == 4
    p.ui.cmbGroupSize.setCurrentText("All")
    p._render_group()
    assert len(_etiquetas(p)) == 10 + 1


def test_las_mediciones_all_trials_usan_los_trials_del_grupo(qapp, monkeypatch):
    import plugins.analysis.time.erp.erp_plugin as mod
    menu = Mock()
    monkeypatch.setattr(mod, "VTKContextMenu", Mock(return_value=menu))
    p = _erp(qapp, 9)
    p.ui.cmbGroupSize.setCurrentText("3")
    p._move_group(+1)
    fuente = menu.set_trials_source.call_args.args[0]
    assert menu.set_trials_source.call_args.kwargs["visible_trial_ids"] == [3, 4, 5]
    t, M, ids = fuente()
    assert ids == [3, 4, 5] and M.shape == (50, 3)
    assert np.allclose(M[:, 0], p._sel[3])

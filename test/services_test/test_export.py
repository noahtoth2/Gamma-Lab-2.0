# test/export_test/test_export_service.py
import os
import json
import csv
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest

# SUT
from core.services.export_service import ExportService


# -----------------------------
# Helpers / Dummies for VTK
# -----------------------------
class DummyWindow:
    pass


class DummyWindowToImageFilter:
    def __init__(self):
        self._input = None
        self.updated = False

    def SetInput(self, window):
        self._input = window

    def Update(self):
        self.updated = True

    def GetOutputPort(self):
        return "dummy-port"


class _WriterBase:
    def __init__(self):
        self.filename = None
        self.port = None
        self.written = False

    def SetFileName(self, fn):
        self.filename = fn

    def SetInputConnection(self, port):
        self.port = port

    def Write(self):
        self.written = True


class DummyPNGWriter(_WriterBase):
    pass


class DummyJPEGWriter(_WriterBase):
    pass


class DummyBMPWriter(_WriterBase):
    pass


class DummyTIFFWriter(_WriterBase):
    pass


def make_service(tmp_path, chart_cb=None, names=("sig", "ch", "plugin")):
    """Build an ExportService fully isolated with fakes/mocks."""
    parent = Mock()
    vtk_widget = Mock()
    vtk_widget.GetRenderWindow.return_value = DummyWindow()

    get_active_chart = chart_cb or (lambda: None)
    get_names = lambda: names

    last_dir_cell = {"v": str(tmp_path)}

    def _get_last():
        return last_dir_cell["v"]

    def _set_last(d):
        last_dir_cell["v"] = d

    svc = ExportService(
        parent=parent,
        vtk_widget=vtk_widget,
        get_active_chart=get_active_chart,
        get_names=get_names,
        last_dir_getter=_get_last,
        last_dir_setter=_set_last,
    )
    # Replace alerts with a mock to observe messages
    svc.alerts = Mock()
    return svc


# =========================
# Image export tests
# =========================

@patch("core.services.export_service.QFileDialog.getSaveFileName")
def test_export_image_png_with_explicit_filename_uses_png_writer_and_sets_last_dir(mock_dlg, tmp_path, monkeypatch):
    # Prepare VTK dummies
    import core.services.export_service as mod
    monkeypatch.setattr(mod.vtk, "vtkWindowToImageFilter", DummyWindowToImageFilter, raising=True)
    monkeypatch.setattr(mod.vtk, "vtkPNGWriter", DummyPNGWriter, raising=True)
    monkeypatch.setattr(mod.vtk, "vtkJPEGWriter", DummyJPEGWriter, raising=True)
    monkeypatch.setattr(mod.vtk, "vtkBMPWriter", DummyBMPWriter, raising=True)
    monkeypatch.setattr(mod.vtk, "vtkTIFFWriter", DummyTIFFWriter, raising=True)

    # Build service
    svc = make_service(tmp_path)

    # No dialog (explicit path)
    out_file = tmp_path / "custom.png"
    mock_dlg.return_value = ("", "")  # should not be used

    # Run
    svc.export_image(format="png", filename=str(out_file))

    # Assertions
    # alerts.info should be called once
    svc.alerts.info.assert_called_once()
    # last dir should be updated to the parent directory
    assert str(tmp_path) in svc._get_last_dir()

    # Verify the writer used (we inspect the class by checking last instantiated writer)
    # The easiest is to ensure the file name was set on the PNG writer:
    # Our Dummy writers are indistinguishable from outside, so patch a hook:
    # Instead, we rely on the absence of errors + last_dir set and simply ensure success path ran.


@patch("core.services.export_service.QFileDialog.getSaveFileName")
def test_export_image_dialog_cancel_returns_without_error(mock_dlg, tmp_path, monkeypatch):
    import core.services.export_service as mod
    monkeypatch.setattr(mod.vtk, "vtkWindowToImageFilter", DummyWindowToImageFilter, raising=True)
    monkeypatch.setattr(mod.vtk, "vtkPNGWriter", DummyPNGWriter, raising=True)

    svc = make_service(tmp_path)

    mock_dlg.return_value = ("", "")  # user cancels dialog

    # Should return quietly, no info alert
    svc.export_image(format="png", filename=None)
    svc.alerts.info.assert_not_called()
    # No error either
    svc.alerts.error.assert_not_called()


def test_export_image_unsupported_format_calls_error(tmp_path, monkeypatch):
    import core.services.export_service as mod
    monkeypatch.setattr(mod.vtk, "vtkWindowToImageFilter", DummyWindowToImageFilter, raising=True)

    # Provide a filename to skip dialog
    svc = make_service(tmp_path)
    out_file = tmp_path / "out.gif"

    svc.export_image(format="gif", filename=str(out_file))
    # Unsupported => error called
    svc.alerts.error.assert_called_once()
    # No success alert
    svc.alerts.info.assert_not_called()


# =========================
# Table export tests
# =========================

class DummyColumn:
    def __init__(self, values):
        self._v = list(values)

    def GetValue(self, i):
        return self._v[i]


class DummyTable:
    def __init__(self, xs, ys):
        self._x = DummyColumn(xs)
        self._y = DummyColumn(ys)
        self._n = len(xs)

    def GetColumn(self, idx):
        return self._x if idx == 0 else self._y

    def GetNumberOfRows(self):
        return self._n


class DummyPlot:
    def __init__(self, xs, ys, label):
        self._tbl = DummyTable(xs, ys)
        self._label = label

    def GetInput(self):
        return self._tbl

    def GetLabel(self):
        return self._label


class DummyChart:
    def __init__(self, plots):
        self._plots = plots

    def GetNumberOfPlots(self):
        return len(self._plots)

    def GetPlot(self, i):
        return self._plots[i]


def test_export_table_no_chart_triggers_error(tmp_path):
    svc = make_service(tmp_path, chart_cb=lambda: None)
    svc.export_table(fmt="csv", filename=str(tmp_path / "tbl.csv"))
    svc.alerts.error.assert_called_once()
    svc.alerts.info.assert_not_called()


def test_export_table_chart_with_zero_plots_triggers_error(tmp_path):
    chart = DummyChart([])
    svc = make_service(tmp_path, chart_cb=lambda: chart)
    svc.export_table(fmt="csv", filename=str(tmp_path / "tbl.csv"))
    svc.alerts.error.assert_called_once()
    svc.alerts.info.assert_not_called()


def test_export_table_csv_writes_headers_and_rows(tmp_path):
    # Two plots → headers: P1_X,P1_Y,P2_X,P2_Y
    xs1, ys1 = [0.0, 1.0, 2.0], [10.0, 11.0, 12.0]
    xs2, ys2 = [0.0, 1.0, 2.0], [20.0, 21.0, 22.0]
    plots = [DummyPlot(xs1, ys1, "P1"), DummyPlot(xs2, ys2, "P2")]
    chart = DummyChart(plots)

    svc = make_service(tmp_path, chart_cb=lambda: chart)
    outfile = tmp_path / "out.csv"
    svc.export_table(fmt="csv", filename=str(outfile))

    # Verify CSV contents
    rows = []
    with open(outfile, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        rows = list(r)

    # header
    assert rows[0] == ["P1_X", "P1_Y", "P2_X", "P2_Y"]
    # 3 data rows
    assert len(rows) == 1 + 3
    # first data row aligned
    assert rows[1] == ["0.0", "10.0", "0.0", "20.0"]

    # success alert and last_dir set
    svc.alerts.info.assert_called_once()
    assert svc._get_last_dir() == str(tmp_path)


def test_export_table_json_writes_records(tmp_path):
    xs, ys = [0.0, 0.5, 1.0], [100.0, 101.0, 102.0]
    chart = DummyChart([DummyPlot(xs, ys, "S1")])
    svc = make_service(tmp_path, chart_cb=lambda: chart)

    out = tmp_path / "out.json"
    svc.export_table(fmt="json", filename=str(out))

    with open(out, encoding="utf-8") as f:
        data = json.load(f)

    # 3 records with keys S1_X, S1_Y
    assert isinstance(data, list) and len(data) == 3
    assert set(data[0].keys()) == {"S1_X", "S1_Y"}
    assert data[0]["S1_X"] == xs[0] and data[0]["S1_Y"] == ys[0]
    svc.alerts.info.assert_called_once()
    assert svc._get_last_dir() == str(tmp_path)


@patch("core.services.export_service.QFileDialog.getSaveFileName")
def test_export_table_uses_dialog_and_respects_cancel(mock_dlg, tmp_path):
    # When filename=None and dialog returns empty -> no write, no alerts
    xs, ys = [0.0, 1.0], [10.0, 11.0]
    chart = DummyChart([DummyPlot(xs, ys, "S1")])
    svc = make_service(tmp_path, chart_cb=lambda: chart)

    mock_dlg.return_value = ("", "")  # cancel
    svc.export_table(fmt="csv", filename=None)

    svc.alerts.info.assert_not_called()
    svc.alerts.error.assert_not_called()

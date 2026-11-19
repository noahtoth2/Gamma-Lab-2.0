"""Relative PSD: valores contra una señal de potencia conocida, aviso de resolución, campos de banda y gráfica."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import vtk
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from core.plugins.meta import PluginMeta
from plugins.analysis.frequency.relative_psd.relative_psd_plugin import Relative_psd_plugin, calcular_psd

FS = 10000.0
T = np.arange(0, 4, 1 / FS)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _plugin():
    meta = PluginMeta(id="r", name="Relative PSD", category="Analysis", subcategory="Frequency",
                      version="1", icon="i", logic_class="x")
    p = Relative_psd_plugin(meta)
    p.mainwin = None
    p.alerts = Mock()
    return p


def _trials():
    """10 Hz de amplitud 1 (potencia 0.5) + 40 Hz de amplitud 0.5 (potencia 0.125) + ruido."""
    rng = np.random.default_rng(0)
    return np.column_stack([np.sin(2 * np.pi * 10 * T + rng.uniform(0, 6))
                            + 0.5 * np.sin(2 * np.pi * 40 * T + rng.uniform(0, 6))
                            + 0.05 * rng.standard_normal(T.size) for _ in range(5)])


@pytest.mark.parametrize("nperseg", [1024, 2048, 4000])
def test_la_potencia_absoluta_es_la_de_la_senal_y_no_depende_de_nperseg(nperseg):
    p = _plugin()
    f, pxx, _ = calcular_psd(_trials(), FS, 1000, "hamming", nperseg, nperseg // 2, nperseg, "none")
    absoluta, relativa = p._compute_relative_psd(f, pxx, 8.0, 12.0, GF=0)
    assert absoluta == pytest.approx(0.5, rel=0.02)
    assert relativa == pytest.approx(0.5 / (0.5 + 0.125 + 0.0025 * 0.98), rel=0.02)


def test_todos_los_trials_suma_la_potencia_de_cada_uno():
    p = _plugin()
    f, pxx, _ = calcular_psd(_trials(), FS, 1000, "hamming", 2048, 1024, 2048, "none")
    a0, r0 = p._compute_relative_psd(f, pxx, 8.0, 12.0, GF=0)
    a1, r1 = p._compute_relative_psd(f, pxx, 8.0, 12.0, GF=1)
    assert a1 == pytest.approx(5 * a0) and r1 == pytest.approx(r0)


def _terminar(p, nperseg, f1=8.0, f2=12.0):
    p.ui = SimpleNamespace(absPowerValue=Mock(), relPowerValue=Mock())
    p.publish_current_trial = lambda *a, **k: None
    p.mark_project_dirty = lambda *a, **k: None
    p._plot_enabled = False
    res = calcular_psd(_trials(), FS, 1000, "hamming", nperseg, nperseg // 2, nperseg, "none")
    p._on_psd_done(dict(f1=f1, f2=f2, GF=0, ch_name="CA1", n_trials=5, posiciones=[1, 2, 3, 4, 5]), res)


def test_avisa_cuando_la_banda_tiene_muy_pocos_puntos():
    p = _plugin()
    _terminar(p, 256)
    texto = p.alerts.warning.call_args.args[0]
    assert "Low frequency resolution" in texto and "nperseg" in texto


def test_no_avisa_con_resolucion_suficiente():
    p = _plugin()
    _terminar(p, 1024)
    assert not p.alerts.warning.called


def test_escribir_la_frecuencia_alta_no_mueve_la_baja(qapp):
    p = _plugin()
    p.get_widget(None)
    lo, hi = p.ui.lowFrequencySpinBox, p.ui.highFrequencySpinBox
    assert (lo.value(), hi.value()) == (8.0, 12.0)
    hi.selectAll()
    QTest.keyClicks(hi, "100")
    QTest.keyClick(hi, Qt.Key_Enter)
    assert (lo.value(), hi.value()) == (8.0, 100.0)


def test_la_grafica_muestra_el_espectro_entero_con_el_promedio_y_la_banda():
    p = _plugin()
    p.active_signal = SimpleNamespace(name="s")
    p.vtk_view = vtk.vtkContextView()
    p._trials_used = {"label": "todos (5)"}
    f, pxx, _ = calcular_psd(_trials(), FS, 1000, "hamming", 256, 128, 256, "none")
    p._plot_psd(f, pxx, "CA1", 8.0, 12.0)
    ch = p.chart
    etiquetas = [ch.GetPlot(i).GetLabel() for i in range(ch.GetNumberOfPlots())]
    assert "Average" in etiquetas
    assert ch.GetNumberOfPlots() == 5 + 1 + 2
    datos = ch.GetPlot(0).GetInput()
    assert datos.GetNumberOfRows() > 100
    assert "8-12 Hz" in ch.GetTitle()

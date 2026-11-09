"""Regresión: los tres plugins de PSD rotulaban el eje «PSD (V^2/Hz)» fijo, aunque
los registros vienen en mV. El rótulo sale ahora de la unidad del canal."""
import importlib
import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from core.model.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from core.utils.unidades import etiqueta_psd

PLUGINS = [
    ("plugins.analysis.frequency.psd.psd_plugin", "Psd_plugin"),
    ("plugins.analysis.frequency.psd_average.psd_average_plugin", "Psd_average_plugin"),
    ("plugins.analysis.frequency.relative_psd.relative_psd_plugin", "Relative_psd_plugin"),
]


@pytest.mark.parametrize("unidad,esperado", [
    ("mV", "PSD (mV²/Hz)"),
    ("V", "PSD (V²/Hz)"),
    ("µV", "PSD (µV²/Hz)"),
    ("a.u.", "PSD ((a.u.)²/Hz)"),
    ("", "PSD (unidad²/Hz)"),
])
def test_el_rotulo_sale_de_la_unidad(unidad, esperado):
    assert etiqueta_psd(unidad) == esperado


@pytest.mark.parametrize("ruta,clase", PLUGINS)
def test_cada_plugin_toma_la_unidad_de_los_trials_que_calcula(ruta, clase):
    cls = getattr(importlib.import_module(ruta), clase)
    p = cls(PluginMeta(id="x", name="X", category="Analysis", subcategory="Frequency",
                       version="1.0", icon="x.png", logic_class=clase))
    td = TrialDataset(source="C:/datos/x.abf", sampling_rate=1000.0, channel_index=0, channel_name="CA1",
                      unit="mV", t0=0.0, t1=1.0, time_rel=np.arange(1000) / 1000.0,
                      trials=np.zeros((1000, 2)), onsets_s=[0, 1])
    p.mainwin = object()
    p.get_active_signal = lambda *a, **k: SimpleNamespace(name="x.abf")
    p.get_active_trials = lambda *a, **k: td
    p._load_trials_from_store()
    assert etiqueta_psd(p._unidad_psd) == "PSD (mV²/Hz)"
    fuente = inspect.getsource(cls._plot_psd)
    assert '"PSD (V^2/Hz)"' not in fuente and "etiqueta_psd" in fuente

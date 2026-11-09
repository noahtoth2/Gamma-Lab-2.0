"""Regresiones de la densidad de muestreo 0 y de los .mat v7.3.

- Densidad 0: `tasa_efectiva` dividía por cero. En PAC, PPC y el índice de
  modulación el error llegaba como «ZeroDivisionError: float division by zero»;
  en Wavelet y Wavelet Average ocurría en el hilo de la interfaz, y PyQt 5.15
  cierra la aplicación ante una excepción no atrapada en un slot.
- .mat v7.3: cada variable se aplanaba en un solo canal (una matriz de tres
  canales quedaba como un canal con los tres seguidos), y los escalares y los
  textos entraban como canales rellenos de NaN.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import h5py
import numpy as np
import pytest

from core.filters.wavelet import tasa_efectiva
from core.model.trial_dataset import TrialDataset
from core.services.fileio_service import FileIOService

FS = 1000.0


# ============================================================
#   Densidad de muestreo 0
# ============================================================
def test_tasa_efectiva_con_densidad_cero_lo_explica():
    with pytest.raises(ValueError, match="densidad de muestreo debe ser mayor que cero"):
        tasa_efectiva(10000.0, 0)


def test_los_calculos_con_densidad_cero_fallan_en_espanol():
    from plugins.analysis.time_frequency.modulation_index import compute as mi
    from plugins.analysis.time_frequency.pac import compute as pac
    from plugins.analysis.time_frequency.ppc import compute as ppc
    sig = np.sin(2 * np.pi * 6 * np.arange(4000) / FS)
    llamadas = [
        lambda: pac.pac_un_trial(None, sig, FS, 0, 3, 8, 25, 120),
        lambda: mi.comodulograma(None, sig, FS, 0, 2, 10, 1, 20, 200, 5),
        lambda: ppc.ppc_mapa(None, sig[:, None], sig[:, None], FS, 0, 5, 100),
    ]
    for llamar in llamadas:
        with pytest.raises(ValueError, match="densidad de muestreo"):
            llamar()


class _Spin:
    def __init__(self):
        self.rango = None

    def setRange(self, a, b):
        self.rango = (a, b)

    def __getattr__(self, nombre):          # setSingleStep, setDecimals, ...
        return lambda *a, **k: None


def _ui_con_spins():
    ui = MagicMock(sampleDensitySpinBox=_Spin(), sampleFqSpinBox=_Spin())
    ui.trialSpinBox.value.return_value = 1      # el selector de trial lo compara con un entero
    return ui


def _plugin(clase):
    from core.plugins.meta import PluginMeta
    return clase(PluginMeta(id="x", name="X", category="Analysis", subcategory="Time-Frequency",
                            version="1.0", icon="x.png", logic_class=clase.__name__))


def test_pac_no_deja_escribir_densidad_cero():
    from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin
    p = _plugin(Pac_plugin)
    p.ui = _ui_con_spins()
    p._init_controls()
    assert p.ui.sampleDensitySpinBox.rango[0] >= 1


def test_indice_de_modulacion_no_deja_escribir_densidad_cero():
    from plugins.analysis.time_frequency.modulation_index.modulation_index_plugin import (
        Modulation_index_plugin)
    p = _plugin(Modulation_index_plugin)
    p.ui = _ui_con_spins()
    p._init_controls()
    assert p.ui.sampleFqSpinBox.rango[0] >= 1


@pytest.mark.parametrize("ruta,clase", [
    ("plugins.analysis.time_frequency.wavelet.wavelet_plugin", "Wavelet_plugin"),
    ("plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin", "Wavelet_average_plugin"),
])
def test_wavelet_con_densidad_cero_avisa_en_vez_de_reventar(ruta, clase):
    import importlib
    from core.plugins.meta import PluginMeta
    cls = getattr(importlib.import_module(ruta), clase)
    p = cls(PluginMeta(id="w", name="Wavelet", category="Analysis", subcategory="Time-Frequency",
                       version="1.0", icon="x.png", logic_class=clase))
    assert p.params["sample_density_range"][0] >= 1

    # Aunque llegara un 0 (un proyecto viejo, otro camino), el cálculo no revienta
    tareas = MagicMock()
    p.kernel = SimpleNamespace(get_service=lambda clave: tareas if clave == "TaskService" else None)
    p.alerts = MagicMock()
    td = TrialDataset(source="C:/datos/x.abf", sampling_rate=FS, channel_index=0, channel_name="CA1",
                      unit="mV", t0=0.0, t1=1.0, time_rel=np.arange(1000) / FS,
                      trials=np.random.default_rng(0).normal(size=(1000, 3)), onsets_s=[0, 1, 2])
    p.get_active_signal = lambda *a, **k: SimpleNamespace(name="x.abf")
    p.get_active_trials = lambda *a, **k: td
    p.selector_trials = MagicMock(posiciones=MagicMock(return_value=[1]))
    p.ui = MagicMock()
    p.ui.sampleDensitySpinBox.value.return_value = 0
    p.ui.lowFrequencySpinBox.value.return_value = 1.0
    p.ui.highFrequencySpinBox.value.return_value = 100.0
    p.ui.cyclesSpinBox.value.return_value = 7
    p.on_create_wavelet()
    tareas.submit.assert_not_called()
    assert any("densidad" in str(c.args[0]) for c in p.alerts.warning.call_args_list)


# ============================================================
#   .mat v7.3
# ============================================================
def escribir_mat73(ruta, variables):
    """Un .mat v7.3 de verdad: HDF5 con la cabecera de MATLAB en el bloque de usuario.
    Cada variable va en la forma de MATLAB; HDF5 la guarda traspuesta, como MATLAB."""
    with h5py.File(ruta, "w", userblock_size=512) as f:
        for nombre, (valor, clase) in variables.items():
            d = f.create_dataset(nombre, data=np.asarray(valor).T)
            d.attrs["MATLAB_class"] = np.bytes_(clase)
    cabecera = b"MATLAB 7.3 MAT-file, Platform: PCWIN64, Created on: Mon Nov  9 10:00:00 2026 HDF5 schema 1.00 ."
    with open(ruta, "r+b") as f:
        f.write(cabecera.ljust(116, b" ") + b"\x00" * 8 + b"\x00\x02IM")


def cargar(ruta):
    return FileIOService().load_mat(str(ruta))


def test_una_matriz_de_muestras_por_canales_da_un_canal_por_columna(tmp_path):
    n = 1000
    datos = np.column_stack([np.arange(n) + 10_000 * k for k in range(3)]).astype(float)   # n × 3
    escribir_mat73(tmp_path / "a.mat", {"datos": (datos, "double")})
    ds = cargar(tmp_path / "a.mat")
    assert ds.channel_names == ["datos_ch1", "datos_ch2", "datos_ch3"]
    assert ds.signals.shape == (3, n)
    for k in range(3):
        assert np.array_equal(ds.signals[k], datos[:, k])


def test_una_matriz_de_canales_por_muestras_tambien(tmp_path):
    datos = np.vstack([np.arange(800.0), -np.arange(800.0)])             # 2 × 800
    escribir_mat73(tmp_path / "b.mat", {"x": (datos, "double")})
    ds = cargar(tmp_path / "b.mat")
    assert ds.signals.shape == (2, 800)
    assert np.array_equal(ds.signals[1], datos[1])


def test_los_escalares_y_los_textos_no_son_canales(tmp_path):
    escribir_mat73(tmp_path / "c.mat", {
        "senal": (np.arange(500.0)[:, None], "double"),
        "fs": (np.array([[1000.0]]), "double"),
        "nombre": (np.array([[ord(c) for c in "rata1"]], dtype=np.uint16), "char"),
    })
    ds = cargar(tmp_path / "c.mat")
    assert ds.channel_names == ["senal"]
    assert ds.signals.shape == (1, 500)
    assert not np.isnan(ds.signals).any()


def test_varios_vectores_siguen_siendo_un_canal_cada_uno(tmp_path):
    escribir_mat73(tmp_path / "d.mat", {
        "ch1": (np.arange(300.0)[None, :], "double"),
        "ch2": (np.arange(300.0)[None, :] * 2, "single"),
    })
    ds = cargar(tmp_path / "d.mat")
    assert ds.channel_names == ["ch1", "ch2"]
    assert np.allclose(ds.signals[1], np.arange(300.0) * 2)


def test_sin_nada_numerico_lo_dice_en_espanol(tmp_path):
    escribir_mat73(tmp_path / "e.mat", {"nombre": (np.array([[72, 111]], dtype=np.uint16), "char")})
    with pytest.raises(ValueError, match="No se encontró ningún vector ni matriz"):
        cargar(tmp_path / "e.mat")

"""Regresiones de los análisis entre canales (PAC Psel entre canales y PPC).

- PAC Psel entre canales solo comparaba la forma de las dos matrices. Con un
  descarte distinto en cada canal las formas coinciden, pero el trial i de un
  canal ya no es el trial i del otro, y el cálculo emparejaba estímulos
  distintos sin avisar. Ahora usa la misma comprobación que PPC
  (`core.filters.trials.validar_alineacion`).
- PPC, al cortar por su cuenta el canal que le faltaba, lo dejaba como canal
  activo: los análisis de un canal (PAC, FFT, PSD...) pasaban a leer otro canal.
"""
import numpy as np
import pytest
from PyQt5.QtCore import QCoreApplication

from core.filters.trials import cut_trials_single_channel, validar_alineacion
from core.model.signal_dataset import SignalDataset
from core.services.task_service import TaskService
from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin
from plugins.analysis.time_frequency.ppc import compute as cp
from test_ppc_plugin_orquestado import esperar, plugin_con

FS = 500.0
ARCHIVO = "17308005.abf"


@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


def senal_con_estimulos(n_estimulos=6):
    n = int(FS * (2 + 1.5 * n_estimulos))
    t = np.arange(n) / FS
    estimulo = np.zeros(n)
    for k in range(n_estimulos):
        i = int((1 + 1.5 * k) * FS)
        estimulo[i:i + 10] = 1.0
    return SignalDataset(
        name=ARCHIVO, format="abf", source_path=f"C:/datos/{ARCHIVO}", sampling_rate=FS,
        time=t, signals=np.vstack([np.sin(2 * np.pi * 10 * t), np.cos(2 * np.pi * 10 * t), estimulo]),
        channel_names=["CA1", "IN 7", "STIM"], units=["mV", "mV", "V"], metadata={})


RECETA = dict(stim_channel=2, threshold=0.5, t0=0.0, t1=1.0,
              end_mode="fixed", stim_expected=None, inter_stim_time=None)


def cortar(ds, canal, activar=True):
    receta = dict(RECETA, channel=ds.channel_names.index(canal))
    td = cut_trials_single_channel(ds=ds, **receta, debug=False)
    td.metadata["generation_params"] = receta
    ds.add_trial_dataset(td, activar=activar)
    return td


@pytest.fixture
def dos_canales():
    ds = senal_con_estimulos()
    cortar(ds, "IN 7")
    cortar(ds, "CA1")          # CA1 queda activo
    return ds


# ============================================================
#   La comprobación compartida
# ============================================================
def test_descartes_distintos_con_la_misma_forma_se_rechazan(dos_canales):
    ds = dos_canales
    ds.discard_trial(ds.name, "CA1", 1)
    ds.discard_trial(ds.name, "IN 7", 3)
    a, b = ds.get_active_trials(ds.name, "CA1"), ds.get_active_trials(ds.name, "IN 7")
    assert a.trials.shape == b.trials.shape          # lo único que PAC miraba
    with pytest.raises(ValueError, match="descartaron trials distintos"):
        validar_alineacion(a, b)


def test_los_mismos_descartes_pasan(dos_canales):
    ds = dos_canales
    for canal in ("CA1", "IN 7"):
        ds.discard_trial(ds.name, canal, 2)
    validar_alineacion(ds.get_active_trials(ds.name, "CA1"), ds.get_active_trials(ds.name, "IN 7"))


def test_un_numero_distinto_de_descartes_dice_que_son_los_descartes(dos_canales):
    ds = dos_canales
    ds.discard_trial(ds.name, "CA1", 1)
    with pytest.raises(ValueError, match="descarta los mismos trials"):
        validar_alineacion(ds.get_active_trials(ds.name, "CA1"), ds.get_active_trials(ds.name, "IN 7"))


def test_ppc_usa_la_misma_funcion_que_core():
    assert cp.validar_alineacion is validar_alineacion


# ============================================================
#   PAC Psel entre canales no calcula con trials desemparejados
# ============================================================
class _Valor:
    def __init__(self, v):
        self._v = v

    def value(self):
        return self._v


class _Texto:
    def __init__(self, t):
        self._t = t

    def currentText(self):
        return self._t


class _Alertas:
    def __init__(self):
        self.errores, self.avisos = [], []

    def error(self, msg, *a, **k):
        self.errores.append(msg)

    def warning(self, msg, *a, **k):
        self.avisos.append(msg)


class _Tareas:
    def __init__(self):
        self.encoladas = []

    def submit(self, *a, **k):
        self.encoladas.append((a, k))
        raise AssertionError("no debía encolar nada")


class _UiPac:
    def __init__(self, canal_amplitud):
        self.sampleDensitySpinBox = _Valor(500)
        self.lowFrequencySpinBox = _Valor(3.0)
        self.highFrequencySpinBox = _Valor(8.0)
        self.ampLowFrequencySpinBox = _Valor(25.0)
        self.ampHighFrequencySpinBox = _Valor(120.0)
        self.pacTypeComboBox = _Texto(Pac_plugin.PSEL_INTER)
        self.ampChannelComboBox = _Texto(canal_amplitud)
        self.trialSpinBox = _Valor(1)


def pac_con(ds, tareas):
    p = object.__new__(Pac_plugin)
    p._restaurando = False
    p.ui = _UiPac("IN 7")
    p.alerts = _Alertas()
    p.kernel = type("K", (), {"get_service": staticmethod(lambda clave: tareas)})()
    p.get_active_signal = lambda *a, **k: ds
    p.get_active_trials = lambda *a, **k: ds.get_active_trials(ds.name, None)
    p.get_trials_de_canal = lambda canal, *a, **k: ds.get_active_trials(ds.name, canal)
    p._actualizar_selector_trial = lambda: None
    return p


def test_pac_entre_canales_no_calcula_con_descartes_distintos(dos_canales):
    ds = dos_canales
    ds.discard_trial(ds.name, "CA1", 1)
    ds.discard_trial(ds.name, "IN 7", 3)
    tareas = _Tareas()
    p = pac_con(ds, tareas)
    p.on_create_pac()
    assert not tareas.encoladas
    assert len(p.alerts.errores) == 1
    assert "descartaron trials distintos" in p.alerts.errores[0]


# ============================================================
#   PPC no cambia el canal activo
# ============================================================
def test_ppc_corta_el_canal_que_falta_sin_cambiar_el_canal_activo(qt_app):
    ds = senal_con_estimulos()
    cortar(ds, "CA1")
    assert ds.get_active_trials(ds.name, "IN 7") is None

    tareas = TaskService()
    p = plugin_con(ds, tareas)
    p.ui.channel1ComboBox.setCurrentText("CA1")
    p.ui.channel2ComboBox.setCurrentText("IN 7")
    p.ui.lowFrequencySpinBox.setValue(20.0)
    p.ui.highFrequencySpinBox.setValue(120.0)
    p.ui.sampleDensitySpinBox.setValue(int(FS))
    try:
        p.on_create_ppc()
        assert esperar(lambda: p._ultimo is not None)
    finally:
        tareas.cancel_all_from("ppc")

    assert ds.get_active_trials(ds.name, "IN 7") is not None      # PPC sí lo cortó
    assert ds.get_active_trials(ds.name, None).channel_name == "CA1"

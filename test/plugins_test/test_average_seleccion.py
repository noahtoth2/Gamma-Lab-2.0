"""R41: Average promedia solo los trials que el usuario selecciona."""
import numpy as np
import pytest
from PyQt5 import QtCore

from core.model.trial_dataset import TrialDataset
from plugins.analysis.time.average import compute as ca
from test_average_plugin import AverageDouble

N_TRIALS, N_MUESTRAS = 6, 50


def _trials():
    # el trial k vale k en todas las muestras: el promedio delata cuáles entraron
    datos = np.tile(np.arange(1, N_TRIALS + 1, dtype=float), (N_MUESTRAS, 1))
    return TrialDataset(source="x.abf", sampling_rate=50.0, channel_index=0, channel_name="a", unit="mV",
                        t0=0.0, t1=1.0, time_rel=np.linspace(0, 1, N_MUESTRAS), trials=datos,
                        onsets_s=list(range(N_TRIALS)))


@pytest.fixture
def plug():
    p = AverageDouble()
    p.construir_ui()
    p.set_active_signal(object())
    p.set_active_trials(_trials())
    return p


def _promedio(p):
    p._captured_avg = None
    p._on_calculate_average()
    return None if p._captured_avg is None else p._captured_avg[0]


def test_compute_con_indices_promedia_solo_esos_trials():
    datos = _trials().trials
    assert ca.promedio_trials(datos, idx=[2, 4])[0] == 3.0
    assert ca.promedio_trials(datos)[0] == 3.5
    with pytest.raises(ValueError):
        ca.promedio_trials(datos, idx=[])
    with pytest.raises(ValueError):
        ca.promedio_trials(datos, idx=[7])


def test_por_defecto_promedia_todos(plug):
    assert _promedio(plug) == 3.5
    assert plug._trials_used["mode"] == "average"


def test_un_solo_trial(plug):
    plug.ui.chkSingleTrial.setChecked(True)
    plug.ui.spnSingleTrial.setValue(5)
    assert _promedio(plug) == 5.0
    assert plug._trials_used["positions"] == [5]


def test_rango(plug):
    plug.ui.chkUseRange.setChecked(True)
    plug.ui.spnFrom.setValue(2)
    plug.ui.spnTo.setValue(4)
    assert _promedio(plug) == 3.0
    assert plug._trials_used["positions"] == [2, 3, 4]
    assert plug._trials_used["label"].startswith("promedio de trials 2–4")


def test_lista_manual(plug):
    plug._ensure_trials_list(N_TRIALS)
    plug.ui.chkSelectAll.setChecked(False)
    for i in range(N_TRIALS):
        plug.ui.lstTrials.item(i).setCheckState(QtCore.Qt.Checked if i in (0, 5) else QtCore.Qt.Unchecked)
    assert _promedio(plug) == 3.5
    assert plug._trials_used["positions"] == [1, 6]


def test_seleccion_vacia_no_calcula(plug):
    plug._ensure_trials_list(N_TRIALS)
    plug.ui.chkSelectAll.setChecked(False)
    for i in range(N_TRIALS):
        plug.ui.lstTrials.item(i).setCheckState(QtCore.Qt.Unchecked)
    assert _promedio(plug) is None


def test_la_seleccion_se_guarda_y_se_restaura(plug):
    plug.ui.chkUseRange.setChecked(True)
    plug.ui.spnFrom.setValue(3)
    plug.ui.spnTo.setValue(5)
    _promedio(plug)
    params = plug.get_analysis_params()
    assert params["mode"] == "range" and (params["range_from"], params["range_to"]) == (3, 5)

    otro = AverageDouble()
    otro.construir_ui()
    otro.set_active_signal(object())
    otro.set_active_trials(_trials())
    otro.apply_analysis_params(params)
    assert otro._captured_avg[0] == 4.0


def test_un_proyecto_antiguo_sin_modo_promedia_todos(plug):
    plug.apply_analysis_params({"used": True})
    assert plug._captured_avg[0] == 3.5

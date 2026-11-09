"""Regresiones de trials, descartes, artefactos y PSD promedio.

- `add_trial_dataset(activar=False)` guarda un canal sin cambiar el activo.
- Trials fijos con S >= 2 e ISI > 0 agrupaban dos veces (40 estímulos y S=2
  daban 10 trials en vez de 20, sin onsets).
- Cortar los trials de un canal borraba los descartes de todos; descartar usaba
  el canal del combo y no el de los trials que se veían.
- «Blank Interval» con B = 0 borraba desde el inicio hasta A: B = 0 se tomaba
  como «sin B».
- PSD promedio quitaba la media de cada segmento (detrend 'constant' de SciPy);
  MATLAB y el plugin PSD no.
"""
import numpy as np
import pytest
from scipy.signal import welch

from core.filters.artifacts import (calcular_modificacion, punto_b_de_receta,
                                    reaplicar_modificaciones, receta)
from core.filters.trials import cut_trials_single_channel
from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset

FS = 1000.0
ARCHIVO = "prueba.abf"


def senal(estimulos_s, dur_s):
    n = int(dur_s * FS)
    t = np.arange(n) / FS
    estimulo = np.zeros(n)
    for s in estimulos_s:
        i = int(round(s * FS))
        estimulo[i:i + 5] = 1.0
    datos = np.random.default_rng(0).normal(size=n)
    return SignalDataset(
        name=ARCHIVO, format="abf", source_path=f"C:/datos/{ARCHIVO}", sampling_rate=FS,
        time=t, signals=np.vstack([datos, np.cos(2 * np.pi * 7 * t), estimulo]),
        channel_names=["CA1", "IN 7", "STIM"], units=["mV", "mV", "V"], metadata={})


def juego(canal, n=3):
    return TrialDataset(source=f"C:/datos/{ARCHIVO}", sampling_rate=FS, channel_index=0,
                        channel_name=canal, unit="mV", t0=0.0, t1=0.1,
                        time_rel=np.arange(100) / FS, trials=np.zeros((100, n)),
                        onsets_s=list(range(n)))


# ============================================================
#   El canal activo
# ============================================================
def activo(ds):
    return ds.get_active_trials(ds.name, None).channel_name


def test_guardar_sin_activar_conserva_el_canal_activo():
    ds = senal([1.0], 3.0)
    ds.add_trial_dataset(juego("CA1"))
    ds.add_trial_dataset(juego("IN 7"), activar=False)
    assert activo(ds) == "CA1"
    assert ds.get_active_trials(ds.name, "IN 7") is not None


def test_reemplazar_el_activo_sin_activar_lo_deja_activo():
    ds = senal([1.0], 3.0)
    ds.add_trial_dataset(juego("IN 7"))
    ds.add_trial_dataset(juego("CA1"))
    ds.add_trial_dataset(juego("CA1", n=5), activar=False)
    assert activo(ds) == "CA1"
    assert ds.get_active_trials(ds.name, "CA1").trials.shape[1] == 5


def test_el_primer_juego_queda_activo_aunque_no_se_active():
    ds = senal([1.0], 3.0)
    ds.add_trial_dataset(juego("IN 7"), activar=False)
    assert activo(ds) == "IN 7"


def test_por_defecto_el_ultimo_guardado_es_el_activo():
    ds = senal([1.0], 3.0)
    ds.add_trial_dataset(juego("CA1"))
    ds.add_trial_dataset(juego("IN 7"))
    assert activo(ds) == "IN 7"


# ============================================================
#   Trials fijos con varios estímulos por trial
# ============================================================
def test_fixed_con_varios_estimulos_agrupa_una_sola_vez():
    # 20 pares de estímulos separados 0,1 s: 40 estímulos, S = 2
    primeros = [1.0 + 2.0 * k for k in range(20)]
    ds = senal([s for p in primeros for s in (p, p + 0.1)], 43.0)
    td = cut_trials_single_channel(
        ds=ds, channel=0, stim_channel=2, threshold=0.5, t0=-0.02, t1=0.08,
        end_mode="fixed", stim_expected=2, inter_stim_time=0.1, debug=False)

    assert td.metadata["stim_detected"] == 40
    assert td.trials.shape == (200, 20)              # cabeza de 0,1 s + una ventana de 0,1 s
    assert np.allclose(td.onsets_s, primeros)
    # Con ISI igual a la ventana, el trial ensamblado es el tramo continuo del par
    a = int(round((primeros[3] - 0.02) * FS))
    assert np.allclose(td.trials[:, 3], ds.signals[0][a:a + 200])


def test_until_next_onset_sigue_igual():
    primeros = [1.0 + 2.0 * k for k in range(5)]
    ds = senal([s for p in primeros for s in (p, p + 0.1)], 12.0)
    td = cut_trials_single_channel(
        ds=ds, channel=0, stim_channel=2, threshold=0.5, t0=-0.02, t1=0.08,
        end_mode="until_next_onset", stim_expected=2, inter_stim_time=0.1, debug=False)
    assert td.trials.shape[1] == 5
    assert np.allclose(td.onsets_s, primeros)


# ============================================================
#   Descartes en el plugin Trials
# ============================================================
class _Kernel:
    def __init__(self):
        self.eventos = []

    def emit_event(self, tema, datos=None):
        self.eventos.append((tema, datos))


class _Alertas:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


class _Combo:
    def __init__(self, texto):
        self._t = texto

    def currentText(self):
        return self._t


def trials_plugin(ds, combo="CA1"):
    from plugins.preprocessing.trials.trials_plugin import TrialsPlugin
    p = object.__new__(TrialsPlugin)
    p.kernel = _Kernel()
    p.alerts = _Alertas()
    p.ui = type("Ui", (), {"channelComboBox": _Combo(combo)})()
    p.last_td = None
    p.visible_trials = [0]
    p.get_active_signal = lambda *a, **k: ds
    p.mark_project_dirty = lambda: None
    p.navigate_trial = lambda d: None
    p._update_trial_ui = lambda *a, **k: None
    p._notify = lambda *a, **k: None
    p._log = lambda *a, **k: None
    return p


def test_cortar_un_canal_no_borra_los_descartes_de_otro():
    ds = senal([1.0, 1.5, 2.0], 3.0)
    ds.add_trial_dataset(juego("CA1"))
    ds.discard_trial(ds.name, "CA1", 1)
    p = trials_plugin(ds)
    p._on_trials_cut(ds, {"channel": 1}, "0.5 mV", juego("IN 7"))
    assert ds.is_trial_discarded(ds.name, "CA1", 1)


def test_volver_a_cortar_un_canal_olvida_sus_propios_descartes():
    ds = senal([1.0, 1.5, 2.0], 3.0)
    ds.add_trial_dataset(juego("IN 7"))
    ds.discard_trial(ds.name, "IN 7", 1)
    p = trials_plugin(ds)
    p._on_trials_cut(ds, {"channel": 1}, "0.5 mV", juego("IN 7"))
    assert not ds.is_trial_discarded(ds.name, "IN 7", 1)


def test_descartar_marca_el_canal_de_los_trials_que_se_ven():
    ds = senal([1.0, 1.5, 2.0], 3.0)
    ds.add_trial_dataset(juego("CA1"))
    ds.add_trial_dataset(juego("IN 7"))
    p = trials_plugin(ds, combo="CA1")              # el combo dice otra cosa
    p.last_td = ds.get_active_trials(ds.name, "IN 7")
    p._on_discard_trial(2, 3)
    assert ds.is_trial_discarded(ds.name, "IN 7", 2)
    assert not ds.is_trial_discarded(ds.name, "CA1", 2)


# ============================================================
#   Blank Interval con B = 0
# ============================================================
T_REL = np.arange(-0.1, 0.4, 1 / FS)


def trials_rampa():
    """Una senoidal con un pico en [-0,03; -0,02] y otro en [-0,09; -0,08]: el relleno
    de un tramo anulado no puede reproducir un pico, así que se nota si se tocó."""
    y = np.sin(2 * np.pi * 3 * T_REL) + 1.0
    y[(T_REL > -0.03) & (T_REL < -0.02)] += 5.0
    y[(T_REL > -0.09) & (T_REL < -0.08)] += 5.0
    return np.tile(y[:, None], (1, 3))


def test_blank_interval_con_b_cero_toca_solo_ese_tramo():
    antes = trials_rampa()
    out = calcular_modificacion(T_REL, antes, mode="blank", point_a=-0.05, point_b=0.0)
    fuera = (T_REL < -0.052) | (T_REL > 0.002)
    assert np.allclose(out[fuera], antes[fuera])          # el pico de -0,09 sigue ahí
    dentro = (T_REL > -0.03) & (T_REL < -0.02)
    assert not np.allclose(out[dentro], antes[dentro])    # el de -0,03 se fue


def test_sin_b_sigue_anulando_desde_el_inicio_hasta_a():
    antes = trials_rampa()
    out = calcular_modificacion(T_REL, antes, mode="blank", point_a=-0.05, point_b=None)
    despues = T_REL > -0.048
    assert np.allclose(out[despues], antes[despues])
    antes_de_a = (T_REL > -0.09) & (T_REL < -0.08)
    assert not np.allclose(out[antes_de_a], antes[antes_de_a])


def test_interpolar_sin_b_lo_dice():
    with pytest.raises(ValueError, match="punto B"):
        calcular_modificacion(T_REL, trials_rampa(), mode="interpolate", point_a=0.1, point_b=None)


def test_la_receta_nueva_distingue_b_cero_de_sin_b():
    assert punto_b_de_receta(receta("blank", -0.05, 0.0, [])) == 0.0
    assert punto_b_de_receta(receta("blank", 0.1, None, [])) is None


def test_una_receta_vieja_con_b_cero_se_reaplica_como_se_guardo():
    vieja = {"mode": "blank", "point_a": 0.1, "point_b": 0.0, "discarded_indices": []}
    assert punto_b_de_receta(vieja) is None
    vieja_interpolar = {"mode": "interpolate", "point_a": -0.05, "point_b": 0.0, "discarded_indices": []}
    assert punto_b_de_receta(vieja_interpolar) == 0.0


def test_reaplicar_una_receta_con_b_cero_da_lo_mismo_que_aplicarla():
    td = TrialDataset(source=f"C:/datos/{ARCHIVO}", sampling_rate=FS, channel_index=0,
                      channel_name="CA1", unit="mV", t0=-0.1, t1=0.4, time_rel=T_REL,
                      trials=trials_rampa(), onsets_s=[0, 1, 2])
    esperado = calcular_modificacion(T_REL, trials_rampa(), mode="blank", point_a=-0.05, point_b=0.0)
    assert reaplicar_modificaciones(td, [receta("blank", -0.05, 0.0, [])]) == 1
    assert np.allclose(td.trials, esperado)


# ============================================================
#   PSD promedio sin quitar la tendencia
# ============================================================
def test_psd_promedio_no_quita_la_tendencia():
    from plugins.analysis.frequency.psd_average.psd_average_plugin import calcular_psd
    t = np.arange(4000) / FS
    X = np.column_stack([2.0 + np.sin(2 * np.pi * 10 * t) + 0.5 * t, 1.0 + np.cos(2 * np.pi * 25 * t)])
    _, potencia, _ = calcular_psd(X, FS, FS, "hamming", 512, 128, 512)
    _, esperado = welch(X, fs=FS, window="hamming", nperseg=512, noverlap=128, nfft=512,
                        detrend=False, scaling="density", axis=0)
    assert np.allclose(potencia, esperado)

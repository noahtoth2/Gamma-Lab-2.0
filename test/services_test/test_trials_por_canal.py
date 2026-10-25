"""Pedir los trials de **un canal concreto**, no solo los del último generado.

Fase 2 del plan de PPC. `SignalDataset.get_active_trials` recibía el nombre del
canal y lo tiraba:

    '''Change in future developments'''
    channel_name = self.__trials_dataset[-1].channel_name

La lista ya guardaba un juego por canal; lo que faltaba era poder pedirlos. PPC
necesita dos a la vez, así que ahora el nombre se honra.

Las dos mitades importan por igual: que **se pueda** pedir por nombre, y que
pedir **sin** nombre siga devolviendo el último canal, porque así es como lo
llaman los nueve plugins de análisis que ya existen.
"""
import numpy as np
import pytest

from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta

ARCHIVO = "17308005.abf"
FS = 1000.0
NS, T = 50, 4


def señal():
    return SignalDataset(
        name=ARCHIVO, format="abf", source_path=f"C:/datos/{ARCHIVO}",
        sampling_rate=FS, time=np.arange(200) / FS,
        signals=np.random.default_rng(0).normal(size=(2, 200)),
        channel_names=["CA1", "IN 7"], units=["mV", "mV"], metadata={})


def trials_de(canal, indice, semilla):
    """Un juego de trials con valores propios, para distinguirlos luego."""
    rng = np.random.default_rng(semilla)
    return TrialDataset(
        source=f"C:/datos/{ARCHIVO}", sampling_rate=FS,
        channel_index=indice, channel_name=canal, unit="mV",
        t0=-0.1, t1=0.4, time_rel=np.linspace(-0.1, 0.4, NS),
        trials=rng.normal(size=(NS, T)),
        onsets_s=[1.0, 2.0, 3.0, 4.0])


# ============================================================
#   Pedir por nombre
# ============================================================
def test_los_dos_canales_se_guardan_y_los_dos_se_pueden_pedir():
    ds = señal()
    ca1, in7 = trials_de("CA1", 0, 1), trials_de("IN 7", 1, 2)
    ds.add_trial_dataset(ca1)
    ds.add_trial_dataset(in7)

    assert ds.get_active_trials(ARCHIVO, "CA1") is ca1
    assert ds.get_active_trials(ARCHIVO, "IN 7") is in7


def test_el_canal_que_no_es_el_ultimo_tambien_se_alcanza():
    """Es el caso que estaba roto: CA1 se generó primero, así que antes de la
    Fase 2 pedirlo devolvía IN 7."""
    ds = señal()
    ca1 = trials_de("CA1", 0, 1)
    ds.add_trial_dataset(ca1)
    ds.add_trial_dataset(trials_de("IN 7", 1, 2))

    recuperado = ds.get_active_trials(ARCHIVO, "CA1")
    assert recuperado.channel_name == "CA1"
    assert np.array_equal(recuperado.trials, ca1.trials)


def test_un_canal_sin_trials_devuelve_none():
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0, 1))

    assert ds.get_active_trials(ARCHIVO, "IN 7") is None


def test_regenerar_un_canal_no_borra_el_otro():
    """`add_trial_dataset` reemplaza por (archivo, canal). Volver a cortar CA1
    tiene que dejar IN 7 donde estaba."""
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0, 1))
    in7 = trials_de("IN 7", 1, 2)
    ds.add_trial_dataset(in7)

    ca1_nuevo = trials_de("CA1", 0, 99)
    ds.add_trial_dataset(ca1_nuevo)

    assert ds.get_active_trials(ARCHIVO, "CA1") is ca1_nuevo
    assert ds.get_active_trials(ARCHIVO, "IN 7") is in7
    assert len(ds.get_all_trials_datasets()) == 2


# ============================================================
#   Sin nombre: lo de siempre, que no se puede romper
# ============================================================
def test_sin_nombre_sigue_devolviendo_el_ultimo_canal():
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0, 1))
    in7 = trials_de("IN 7", 1, 2)
    ds.add_trial_dataset(in7)

    assert ds.get_active_trials(ARCHIVO) is in7
    assert ds.get_active_trials(ARCHIVO, None) is in7


def test_sin_nombre_sigue_el_orden_de_generacion():
    """Regenerar CA1 lo convierte en el activo, aunque se generara antes."""
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0, 1))
    ds.add_trial_dataset(trials_de("IN 7", 1, 2))

    ca1_nuevo = trials_de("CA1", 0, 99)
    ds.add_trial_dataset(ca1_nuevo)

    assert ds.get_active_trials(ARCHIVO) is ca1_nuevo


def test_sin_trials_devuelve_none_con_y_sin_nombre():
    ds = señal()
    assert ds.get_active_trials(ARCHIVO) is None
    assert ds.get_active_trials(ARCHIVO, "CA1") is None


# ============================================================
#   Los descartes siguen siendo por canal
# ============================================================
def test_los_descartes_de_un_canal_no_tocan_al_otro():
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0, 1))
    ds.add_trial_dataset(trials_de("IN 7", 1, 2))

    ds.discard_trial(ARCHIVO, "CA1", 0)

    assert ds.get_active_trials(ARCHIVO, "CA1").trials.shape[1] == T - 1
    assert ds.get_active_trials(ARCHIVO, "IN 7").trials.shape[1] == T


def test_la_cache_no_mezcla_los_dos_canales():
    """Dos lecturas seguidas de canales distintos: la segunda no puede devolver
    lo que cacheó la primera."""
    ds = señal()
    ca1, in7 = trials_de("CA1", 0, 1), trials_de("IN 7", 1, 2)
    ds.add_trial_dataset(ca1)
    ds.add_trial_dataset(in7)

    for _ in range(2):
        assert ds.get_active_trials(ARCHIVO, "CA1").channel_name == "CA1"
        assert ds.get_active_trials(ARCHIVO, "IN 7").channel_name == "IN 7"

    ds.discard_trial(ARCHIVO, "CA1", 1)
    assert ds.get_active_trials(ARCHIVO, "CA1").trials.shape[1] == T - 1
    assert ds.get_active_trials(ARCHIVO, "IN 7").trials.shape[1] == T


# ============================================================
#   El acceso desde un plugin
# ============================================================
class _PluginDePrueba(IPlugin):
    """Lo mínimo para instanciar IPlugin: los tres métodos abstractos vacíos."""
    def stop(self): pass
    def get_widget(self, parent=None): return None
    def process(self, data): return None


def plugin_con(ds):
    meta = PluginMeta(id="prueba", name="Prueba", category="Analysis",
                      subcategory="Connectivity", version="1.0", icon="x.png",
                      logic_class="_PluginDePrueba")
    p = _PluginDePrueba(meta)
    p.active_signal = ds
    return p


def test_el_plugin_alcanza_los_dos_canales():
    ds = señal()
    ca1, in7 = trials_de("CA1", 0, 1), trials_de("IN 7", 1, 2)
    ds.add_trial_dataset(ca1)
    ds.add_trial_dataset(in7)
    p = plugin_con(ds)

    assert p.get_trials_de_canal("CA1") is ca1
    assert p.get_trials_de_canal("IN 7") is in7


def test_el_plugin_avisa_cuando_el_canal_no_tiene_trials(monkeypatch):
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0, 1))
    p = plugin_con(ds)

    avisos = []
    monkeypatch.setattr(p.alerts, "warning", lambda m: avisos.append(m))

    assert p.get_trials_de_canal("IN 7") is None
    assert len(avisos) == 1
    assert "IN 7" in avisos[0], "el aviso tiene que decir de qué canal habla"


def test_get_active_trials_del_plugin_no_cambio():
    """El método que usan los nueve plugins de análisis sigue dando el último."""
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0, 1))
    in7 = trials_de("IN 7", 1, 2)
    ds.add_trial_dataset(in7)
    p = plugin_con(ds)

    assert p.get_active_trials() is in7

"""R11, R52: al cerrar el proyecto o cargar otra señal, la anterior y sus derivados se sueltan."""
import gc
import weakref
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from app.view.main_window import MainWindow
from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.services.data_store import DataStore


def _senal(nombre="s.abf", n=1000):
    t = np.arange(n) / 100.0
    return SignalDataset(name=nombre, format="abf", source_path=f"C:/{nombre}", sampling_rate=100.0, time=t,
                         signals=np.vstack([t]), channel_names=["a"], units=["mV"])


def test_release_signals_quita_las_senales_y_lo_que_depende_de_ellas():
    store = DataStore()
    store.set_active_signal(store.add_signal(_senal("a.abf"), "a.abf"))
    store.add_signal(_senal("b.abf"), "b.abf")
    store.set("measurements", [{"x": 1}])
    store.set("current_trial", {"i": 3})
    store.set("last_dir", "C:/datos")

    quitadas = store.release_signals()

    assert sorted(quitadas) == ["a.abf", "b.abf"]
    assert store.get_signals() == {} and store.get_active_signal() is None
    assert not store.has("current_trial") and store.get("measurements") == []
    assert store.get("last_dir") == "C:/datos", "lo que no es de la señal se queda"


def test_release_signals_puede_conservar_una():
    store = DataStore()
    store.add_signal(_senal("a.abf"), "a.abf")
    store.set_active_signal(store.add_signal(_senal("b.abf"), "b.abf"))
    assert store.release_signals(conservar="b.abf") == ["a.abf"]
    assert list(store.get_signals()) == ["b.abf"] and store.get_active_signal_key() == "b.abf"


class PluginDeprueba(IPlugin):
    def process(self, data): pass
    def stop(self): pass
    def get_widget(self, parent=None): return None


def test_olvidar_senal_suelta_datasets_y_resultados_del_plugin():
    p = PluginDeprueba(PluginMeta(id="p", name="P", category="Analysis", subcategory="x", version="1",
                                  icon="i", logic_class="C"))
    ds = _senal()
    p.active_signal = ds
    p._trials_used = {"label": "x"}
    p.current_ds = ds
    p.last_td = TrialDataset.__new__(TrialDataset)
    p._ultimo = {"resultado": np.zeros(10)}
    p._contexto = {"señal": "s.abf"}
    p.parametros = {"se": "queda"}

    p.olvidar_senal()

    assert p.active_signal is None and p._trials_used is None
    assert p.current_ds is None and p.last_td is None and p._ultimo is None
    assert p._contexto == {} and p.parametros == {"se": "queda"}


def test_la_senal_anterior_queda_sin_referencias():
    store = DataStore()
    ds = _senal()
    store.set_active_signal(store.add_signal(ds, ds.name))
    p = PluginDeprueba(PluginMeta(id="p", name="P", category="Analysis", subcategory="x", version="1",
                                  icon="i", logic_class="C"))
    p.active_signal = p.current_ds = ds
    viva = weakref.ref(ds)
    del ds

    p.olvidar_senal()
    store.release_signals()
    gc.collect()

    assert viva() is None


def test_liberar_senal_anterior_orquesta_los_pasos():
    pasos = []
    plugin = SimpleNamespace(olvidar_senal=lambda: pasos.append("olvidar"))
    store = MagicMock()
    store.release_signals.side_effect = lambda: pasos.append("store")
    stub = SimpleNamespace(
        kernel=SimpleNamespace(get_plugins=lambda: ["P"], get_plugin=lambda n: plugin,
                               get_service=lambda n: store),
        _stop_all_background_workers=lambda: pasos.append("cancelar"),
        _reset_all_plugin_widgets=lambda conservar=None: pasos.append(f"widgets:{conservar}"),
    )
    MainWindow.liberar_senal_anterior(stub, conservar_plugin="Open Signal")
    assert pasos == ["cancelar", "widgets:Open Signal", "olvidar", "store"]

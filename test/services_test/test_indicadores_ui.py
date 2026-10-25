"""Indicadores de la interfaz: severidad de los mensajes, trial actual,
trials usados por cada operacion y lectura X/Y bajo el cursor.

Se prueba la logica sin levantar ventanas: los textos, la numeracion de los
trials (posicion entre los validos, base 1), el enrutado de `PluginAlerts` y
la conversion pixel -> datos de un grafico.
"""
import numpy as np
import pytest
import vtk

from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.services.data_store import DataStore
from core.utils import plugin_alerts as pa
from core.utils.chart_coords import screen_to_plot, chart_at_pixel
from core.utils.cursor_readout import format_readout, format_value
from core.utils.trial_labels import compress_ranges, describe_trials, trials_used

ARCHIVO = "17308005.abf"
FS = 1000.0
NS, T = 50, 6


def señal():
    return SignalDataset(
        name=ARCHIVO, format="abf", source_path=f"C:/datos/{ARCHIVO}",
        sampling_rate=FS, time=np.arange(200) / FS,
        signals=np.zeros((2, 200)),
        channel_names=["CA1", "IN 7"], units=["mV", "mV"], metadata={})


def trials_de(canal, indice):
    return TrialDataset(
        source=f"C:/datos/{ARCHIVO}", sampling_rate=FS,
        channel_index=indice, channel_name=canal, unit="mV",
        t0=-0.1, t1=0.4, time_rel=np.linspace(-0.1, 0.4, NS),
        trials=np.zeros((NS, T)), onsets_s=[float(i) for i in range(T)])


# ============================================================
#   Textos de trials
# ============================================================
def test_compress_ranges_agrupa_consecutivos():
    assert compress_ranges([1, 2, 3, 5, 8, 9]) == "1–3, 5, 8–9"
    assert compress_ranges([4]) == "4"
    assert compress_ranges([]) == ""


@pytest.mark.parametrize("posiciones, total, esperado", [
    (None, 18, "todos (18)"),
    (list(range(1, 19)), 18, "todos (18)"),
    ([3], 18, "trial 3 de 18"),
    ([1, 2, 3, 4, 5, 8], 18, "trials 1–5, 8 (6 de 18)"),
    ([], 18, "ninguno (0 de 18)"),
])
def test_describe_trials(posiciones, total, esperado):
    assert describe_trials(posiciones, total) == esperado


def test_trials_used_es_serializable_y_completo():
    u = trials_used([2, 3], 10, channel="CA1")
    assert u["positions"] == [2, 3]
    assert u["count"] == 2 and u["total_valid"] == 10
    assert u["mode"] == "selection"
    assert u["channel"] == "CA1"
    assert u["numbering"] == "valid_position_1based"
    todos = trials_used(None, 4, "average")
    assert todos["positions"] == [1, 2, 3, 4]
    assert todos["label"] == "promedio de todos (4)"


# ============================================================
#   Indices originales de los trials validos
# ============================================================
def test_indices_validos_sin_descartes():
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0))
    assert ds.get_active_trial_indices(ARCHIVO) == list(range(T))


def test_indices_validos_con_descartes_y_por_canal():
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0))
    ds.add_trial_dataset(trials_de("IN 7", 1))
    ds.discard_trial(ARCHIVO, "CA1", 1)
    ds.discard_trial(ARCHIVO, "CA1", 4)
    assert ds.get_active_trial_indices(ARCHIVO, "CA1") == [0, 2, 3, 5]
    # Sin nombre: el ultimo canal generado, que no tiene descartes
    assert ds.get_active_trial_indices(ARCHIVO) == list(range(T))
    # Coincide con las columnas que devuelve get_active_trials
    assert ds.get_active_trials(ARCHIVO, "CA1").trials.shape[1] == 4


def test_indices_validos_sin_trials():
    assert señal().get_active_trial_indices(ARCHIVO) == []


# ============================================================
#   Estado del trial actual en los plugins
# ============================================================
class _Kernel:
    def __init__(self, store):
        self._store = store
        self.eventos = []

    def get_service(self, key):
        return self._store if key == "DataStore" else None

    def emit_event(self, topic, payload=None):
        self.eventos.append((topic, payload))


class _PluginDePrueba(IPlugin):
    def stop(self): pass
    def get_widget(self, parent=None): return None
    def process(self, data): return None


@pytest.fixture
def plugin():
    ds = señal()
    ds.add_trial_dataset(trials_de("CA1", 0))
    store = DataStore()
    store.add_signal(ds, ds.name)
    store.set_active_signal(ds.name)
    meta = PluginMeta(id="prueba", name="Prueba", category="Analysis",
                      subcategory="Time", version="1.0", icon="x.png",
                      logic_class="_PluginDePrueba")
    p = _PluginDePrueba(meta)
    p.kernel = _Kernel(store)
    return p, ds, store


def test_estado_por_defecto_son_todos_los_validos(plugin):
    p, ds, _ = plugin
    ds.discard_trial(ARCHIVO, "CA1", 0)
    st = p.current_trial_state()
    assert st["mode"] == "all"
    assert st["total"] == T - 1
    assert st["channel"] == "CA1"


def test_estado_sigue_a_la_ultima_operacion(plugin):
    p, _, _ = plugin
    p._trials_used = trials_used([2, 3], T, channel="CA1")
    st = p.current_trial_state()
    assert st["mode"] == "selection" and st["positions"] == [2, 3]


def test_estado_ignora_una_operacion_de_otros_trials(plugin):
    """Si los trials cambiaron desde la ultima operacion, no se muestra lo viejo."""
    p, _, _ = plugin
    p._trials_used = trials_used([2], T + 10, channel="CA1")
    assert p.current_trial_state()["mode"] == "all"


def test_publicar_guarda_y_emite(plugin):
    p, _, store = plugin
    st = p.publish_current_trial("single", position=3)
    assert store.get("current_trial") == st
    assert p.kernel.eventos[-1] == ("current_trial_changed", st)
    assert st["plugin"] == "Prueba" and st["position"] == 3 and st["total"] == T


def test_texto_del_indicador():
    from app.view.main_window import MainWindow
    fmt = MainWindow.format_trial_state
    assert fmt({"mode": "single", "position": 3, "total": 18, "channel": "CA1"}) == "CA1 · Trial 3 / 18"
    assert fmt({"mode": "average", "total": 18}) == "Promedio de 18 trials"
    assert fmt({"mode": "all", "total": 18}) == "Todos los trials (18)"
    assert fmt({"mode": "single", "discarded": True, "original_index": 4, "total": 17}) \
        == "Trial descartado (original 5)"
    assert fmt({"mode": "selection", "positions": [1, 2, 3], "total": 9}) == "Trials 1–3 (3 de 9)"
    assert fmt({"mode": "none"}) == "Sin trials generados"
    assert fmt(None) == ""


# ============================================================
#   Severidad de los mensajes
# ============================================================
class _Centro:
    def __init__(self):
        self.mostrados = []

    def show_message(self, level, title, message):
        self.mostrados.append((level, title, message))

    def window(self):
        return None


@pytest.fixture
def centro(monkeypatch):
    c = _Centro()
    monkeypatch.setattr(pa.PluginAlerts, "_center", c)
    criticos = []
    monkeypatch.setattr(pa.QMessageBox, "critical",
                        staticmethod(lambda parent, t, m: criticos.append((t, m))))
    return c, criticos


def test_info_y_warning_no_son_modales(centro):
    c, criticos = centro
    a = pa.PluginAlerts()
    a.info("hecho")
    a.warning("falta un paso")
    assert [m[0] for m in c.mostrados] == ["info", "warning"]
    assert criticos == []


def test_error_es_modal(centro):
    c, criticos = centro
    a = pa.PluginAlerts(parent=object())
    a.error("fallo")
    assert c.mostrados == []
    assert criticos == [("Error", "fallo")]


def test_show_por_nivel(centro):
    c, _ = centro
    pa.PluginAlerts().show("warning", "x")
    assert c.mostrados == [("warning", "Warning", "x")]
    with pytest.raises(ValueError):
        pa.PluginAlerts().show("debug", "x")


def test_sin_centro_ni_ventana_no_falla(monkeypatch):
    monkeypatch.setattr(pa.PluginAlerts, "_center", None)
    a = pa.PluginAlerts()
    a.info("x"); a.warning("y"); a.error("z")


# ============================================================
#   Lectura X/Y bajo el cursor
# ============================================================
class _Eje:
    def __init__(self, lo, hi, log=False, titulo=""):
        self.lo, self.hi, self.log, self.titulo = lo, hi, log, titulo

    def GetMinimum(self): return self.lo
    def GetMaximum(self): return self.hi
    def GetLogScaleActive(self): return self.log
    def GetTitle(self): return self.titulo


class _Grafico:
    """Area de trazado de (100,50) a (300,250) px; x en [0,2], y en [-10,10]."""
    def __init__(self, p1=(100, 50), p2=(300, 250), ejes=None):
        self.p1, self.p2 = p1, p2
        self.ejes = ejes or {vtk.vtkAxis.BOTTOM: _Eje(0.0, 2.0, titulo="Time (s)"),
                             vtk.vtkAxis.LEFT: _Eje(-10.0, 10.0, titulo="mV")}

    def GetPoint1(self): return self.p1
    def GetPoint2(self): return self.p2
    def GetAxis(self, i): return self.ejes[i]


def test_pixel_a_datos():
    g = _Grafico()
    assert screen_to_plot(g, 100, 50) == pytest.approx((0.0, -10.0))
    assert screen_to_plot(g, 200, 150) == pytest.approx((1.0, 0.0))
    assert screen_to_plot(g, 300, 250) == pytest.approx((2.0, 10.0))


def test_fuera_del_area_no_hay_lectura():
    g = _Grafico()
    assert screen_to_plot(g, 99, 150) is None
    assert screen_to_plot(g, 200, 251) is None


def test_eje_logaritmico():
    g = _Grafico(ejes={vtk.vtkAxis.BOTTOM: _Eje(0.0, 2.0),
                       vtk.vtkAxis.LEFT: _Eje(0.0, 2.0, log=True)})
    _, y = screen_to_plot(g, 200, 150)
    assert y == pytest.approx(10.0)


def test_graficos_apilados():
    arriba = _Grafico(p1=(10, 210), p2=(200, 400))
    abajo = _Grafico(p1=(10, 10), p2=(200, 190))
    assert chart_at_pixel([arriba, abajo], 50, 300) is arriba
    assert chart_at_pixel([arriba, abajo], 50, 100) is abajo
    assert chart_at_pixel([arriba, abajo], 50, 200) is None


def test_formato_de_la_lectura():
    assert format_value(0.234112) == "0.23411"
    assert format_value(1.23e-5) == "1.23e-05"
    assert format_value(0.0) == "0"
    assert format_readout(1.0, -12.08, "Time (s)", "mV") == "X = 1  [Time (s)]     Y = -12.08  [mV]"

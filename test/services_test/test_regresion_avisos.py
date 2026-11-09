"""Regresiones de los avisos que faltaban y de la barra de progreso.

- Trials no avisaba de estímulos irregulares (umbral en el ruido; sin antirrebote)
  ni de trials que se solapan.
- Un canal desconectado no es plano —el conversor sigue dando un paso arriba o
  abajo—, así que el «desviación cero» de PPC no lo veía, y PAC no miraba nada.
- Los avisos del índice de modulación solo iban al log.
- La magnitud del vector medio de PAC se mostraba como «acoplamiento», como si
  fuera un índice; escala con la amplitud de la señal.
- `task_started` se emitía al encolar: la barra seguía a la tarea de la cola y su
  Cancelar cancelaba esa en vez de la que corría.
"""
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from PyQt5.QtCore import QCoreApplication

from core.filters.trials import canal_sin_senal, revisar_corte
from core.model.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from core.services.task_service import TaskService

FS = 1000.0


def juego(onsets, n_muestras=100, trials=None, canal="CA1", unidad="mV", modo="fixed", t0=0.0):
    datos = trials if trials is not None else np.random.default_rng(0).normal(size=(n_muestras, len(onsets)))
    return TrialDataset(source="C:/datos/x.abf", sampling_rate=FS, channel_index=0, channel_name=canal,
                        unit=unidad, t0=t0, t1=t0 + datos.shape[0] / FS, time_rel=t0 + np.arange(datos.shape[0]) / FS,
                        trials=datos, onsets_s=list(onsets), metadata={"end_mode": modo})


# ============================================================
#   Estímulos irregulares y trials que se solapan
# ============================================================
def test_estimulos_irregulares_avisan_y_sugieren_un_umbral():
    td = juego([0.0, 0.0006, 5.0, 5.0007, 10.0, 15.0])
    estimulo = np.r_[np.full(100, 0.05), np.full(10, 5.0)]          # un canal en V con pulsos de 5 V
    avisos = revisar_corte(td, estimulo, "V", 0.0007)
    assert len(avisos) == 1
    assert "no son regulares" in avisos[0]
    assert "2500 mV" in avisos[0]                                     # la mitad del pulso


def test_estimulos_regulares_no_avisan():
    assert revisar_corte(juego([0.0, 5.0, 10.0, 15.0])) == []


def test_trials_que_se_solapan_avisan_con_el_tiempo_final_que_cabe():
    td = juego([1.0, 4.0, 7.0, 10.0], n_muestras=4050, t0=-0.05)      # trials de 4,05 s cada 3 s
    avisos = revisar_corte(td)
    assert len(avisos) == 1 and "se solapan" in avisos[0]
    assert "2.95" in avisos[0]


def test_cortar_hasta_el_siguiente_estimulo_no_se_solapa():
    td = juego([1.0, 4.0, 7.0, 10.0], n_muestras=4050, modo="until_next_onset")
    assert revisar_corte(td) == []


# ============================================================
#   Canal sin señal
# ============================================================
PASO = 0.0025          # 2,5 µV en mV, como los ABF de test/data


def cuantizado(desviacion_en_pasos, forma=(3000, 5)):
    x = np.random.default_rng(1).normal(scale=desviacion_en_pasos * PASO, size=forma)
    return np.round(x / PASO) * PASO


def test_un_canal_que_solo_trae_el_ruido_del_conversor_se_detecta():
    aviso = canal_sin_senal(juego(range(5), trials=cuantizado(0.7), canal="STR"))
    assert aviso and "'STR' parece no tener señal" in aviso


def test_un_canal_vivo_no_se_marca():
    assert canal_sin_senal(juego(range(5), trials=cuantizado(8.0))) is None


def test_unos_artefactos_no_esconden_un_canal_muerto():
    x = cuantizado(0.7)
    x[:5, :] = 2.0                                                     # el artefacto de cada estímulo
    assert canal_sin_senal(juego(range(5), trials=x)) is not None


def test_un_canal_constante_se_detecta():
    assert "es constante" in canal_sin_senal(juego(range(5), trials=np.zeros((100, 5))))


def test_sin_pasos_de_conversor_no_se_marca():
    # Datos ya filtrados o promediados: no hay pasos que medir y no se arriesga
    assert canal_sin_senal(juego(range(5), trials=np.random.default_rng(2).normal(scale=1e-6, size=(500, 5)))) is None


# ============================================================
#   Los plugins lo dicen
# ============================================================
def test_trials_avisa_al_cortar_un_canal_sin_senal():
    from core.model.signal_dataset import SignalDataset
    from plugins.preprocessing.trials.trials_plugin import TrialsPlugin
    ds = SignalDataset(name="x.abf", format="abf", source_path="C:/datos/x.abf", sampling_rate=FS,
                       time=np.arange(100) / FS, signals=np.zeros((2, 100)), channel_names=["CA1", "IN 7"],
                       units=["mV", "V"], metadata={})
    p = object.__new__(TrialsPlugin)
    p.kernel = SimpleNamespace(emit_event=lambda *a, **k: None)
    p.alerts = MagicMock()
    p.ui = SimpleNamespace(channelComboBox=SimpleNamespace(currentText=lambda: "CA1"))
    p.last_td, p.visible_trials = None, [0]
    p.mark_project_dirty = p.navigate_trial = p._notify = p._log = lambda *a, **k: None
    p._on_trials_cut(ds, {"channel": 0}, "0.5 mV", juego([0.0, 1.0, 2.0], trials=cuantizado(0.6, (100, 3))))
    p.alerts.warning.assert_called_once()
    assert "parece no tener señal" in p.alerts.warning.call_args.args[0]


def _plugin(clase):
    return clase(PluginMeta(id="x", name="X", category="Analysis", subcategory="Time-Frequency",
                            version="1.0", icon="x.png", logic_class=clase.__name__))


def test_pac_avisa_de_un_canal_de_amplitud_sin_senal():
    from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin
    onsets = [0.0, 1.0, 2.0, 3.0]
    fase = juego(onsets, n_muestras=1000, canal="CA1")
    amplitud = juego(onsets, n_muestras=1000, trials=cuantizado(0.6, (1000, 4)), canal="STR")
    p = _plugin(Pac_plugin)
    tareas = MagicMock()
    p.kernel = SimpleNamespace(get_service=lambda clave: tareas)
    p.alerts = MagicMock()
    p.get_active_signal = lambda *a, **k: SimpleNamespace(name="x.abf")
    p.get_active_trials = lambda *a, **k: fase
    p.get_trials_de_canal = lambda canal, *a, **k: amplitud
    p._actualizar_selector_trial = lambda: None
    p.ui = MagicMock()
    for nombre, valor in (("sampleDensitySpinBox", 500), ("lowFrequencySpinBox", 3.0),
                          ("highFrequencySpinBox", 8.0), ("ampLowFrequencySpinBox", 25.0),
                          ("ampHighFrequencySpinBox", 120.0), ("trialSpinBox", 1)):
        getattr(p.ui, nombre).value.return_value = valor
    p.ui.pacTypeComboBox.currentText.return_value = Pac_plugin.PSEL_INTER
    p.ui.ampChannelComboBox.currentText.return_value = "STR"
    p.on_create_pac()
    textos = [c.args[0] for c in p.alerts.warning.call_args_list]
    assert any("'STR' parece no tener señal" in t for t in textos)
    tareas.submit.assert_called_once()                 # avisa, pero calcula igual


def test_los_avisos_del_indice_de_modulacion_se_ven():
    from plugins.analysis.time_frequency.modulation_index.modulation_index_plugin import (
        Modulation_index_plugin)
    p = _plugin(Modulation_index_plugin)
    p.alerts = MagicMock()
    r = SimpleNamespace(frecuencias_amplitud=np.arange(20.0, 200.0, 5.0), bandas_calculadas=36,
                        limite_matlab=False, ciclos_banda_lenta=0.3, duracion_s=3.05,
                        frecuencias_fase=np.array([0.1, 1.1]), fs_efectiva=2000.0)
    p._avisar_de_los_limites(r)
    p.alerts.warning.assert_called_once()
    assert "0.3 ciclos" in p.alerts.warning.call_args.args[0]


def test_la_magnitud_del_vector_medio_dice_que_no_esta_normalizada():
    from plugins.analysis.time_frequency.pac.pac_plugin import titulo_de
    assert "no normalizada" in titulo_de(0.03 + 0.01j)


# ============================================================
#   La barra de progreso sigue a la tarea que corre
# ============================================================
@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


def esperar(condicion, ms=10000):
    app = QCoreApplication.instance()
    limite = time.monotonic() + ms / 1000.0
    while time.monotonic() < limite:
        app.processEvents()
        if condicion():
            return True
        time.sleep(0.005)
    app.processEvents()
    return condicion()


def test_task_started_llega_cuando_la_tarea_empieza_a_correr(qt_app):
    tareas = TaskService()
    empezadas = []
    tareas.task_started.connect(lambda h: empezadas.append(h.owner))

    def lenta(ctx):
        for _ in range(60):
            if ctx.cancelled:
                return None
            time.sleep(0.005)
        return 1

    tareas.submit(lenta, owner="pac")
    tareas.submit(lambda: 2, owner="ppc")             # queda en cola
    assert empezadas == ["pac"], "la de la cola todavía no corre"
    assert esperar(lambda: empezadas == ["pac", "ppc"])

import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PyQt5.QtCore import QCoreApplication

from core.kernel import Kernel
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService
from core.services.task_service import TaskService
from core.filters import trials as tr
from core.plugins.meta import PluginMeta
from plugins.analysis.time_frequency.wavelet.wavelet_plugin import Wavelet_plugin


BASE_DIR = Path(__file__).resolve().parents[1] / "data"
ABF_PATH = BASE_DIR / "17308005.abf"

pytestmark = pytest.mark.skipif(not ABF_PATH.exists(),
                                reason="no se encontro el archivo ABF de prueba")


@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture(scope="module")
def kernel():
    k = Kernel()
    k.register_service("DataStore", DataStore())
    k.register_service("FileIO", FileIOService())
    k.register_service("TaskService", TaskService())
    return k


@pytest.fixture(scope="module")
def trial_real(kernel):
    fio = kernel.get_service("FileIO")
    sd = fio.load_abf(str(ABF_PATH))
    sd.signals = sd.signals.astype(np.float64, copy=False)
    sd.time = sd.time.astype(np.float64, copy=False)
    td = tr.cut_trials_single_channel(
        ds=sd, channel=0, stim_channel=1, threshold=0.7, t0=-0.05, t1=4.00,
        end_mode="until_next_onset", stim_expected=1, inter_stim_time=0.0,
        pad_value=0.0, debug=False)
    X = np.nan_to_num(np.asarray(td.trials, dtype=np.float64))
    t = np.asarray(td.time_rel, dtype=np.float64)
    return X[:, 0], round(1.0 / (t[1] - t[0]), 3)


def wait_for(predicate, timeout_ms=30000):
    app = QCoreApplication.instance()
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return predicate()


def test_un_plugin_calcula_el_wavelet_por_el_orquestador(qt_app, kernel, trial_real):
    sig, fs_calculado = trial_real

    plug = Wavelet_plugin(PluginMeta(
        id="wavelet", name="Wavelet", category="analysis", subcategory="tf",
        version="0", icon="", logic_class="Wavelet_plugin"))

    esperado, _, _ = plug.compute_wavelet(sig, fs_calculado, 1000.0, 1.0, 500.0, 2.0)

    tasks = kernel.get_service("TaskService")
    assert tasks is not None, "el plugin debe poder obtener el servicio del kernel"

    recibido = {}
    hilo_del_slot = {}

    handle = tasks.submit(
        plug.compute_wavelet, owner="wavelet",
        sig=sig, fs_calculado=fs_calculado, fs=1000.0,
        fmin=1.0, fmax=500.0, num_cycles=2.0,
    )

    def al_terminar(resultado):
        recibido["escalograma"] = resultado[0]
        hilo_del_slot["id"] = threading.get_ident()

    handle.finished.connect(al_terminar)
    handle.failed.connect(lambda msg: pytest.fail(f"la tarea fallo: {msg}"))

    assert wait_for(lambda: "escalograma" in recibido), "nunca llego el resultado"

    obtenido = recibido["escalograma"]
    assert obtenido.shape == esperado.shape == (998, 3051)
    assert np.array_equal(obtenido, esperado), \
        "el escalograma por el orquestador debe ser identico al sincrono"

    assert hilo_del_slot["id"] == threading.get_ident(), \
        "finished debe entregarse en el hilo de la interfaz"


def test_la_interfaz_sigue_viva_durante_el_calculo(qt_app, kernel, trial_real):
    sig, fs_calculado = trial_real
    plug = Wavelet_plugin(PluginMeta(
        id="wavelet", name="Wavelet", category="analysis", subcategory="tf",
        version="0", icon="", logic_class="Wavelet_plugin"))

    tasks = kernel.get_service("TaskService")
    listo = {}
    handle = tasks.submit(
        plug.compute_wavelet, owner="wavelet",
        sig=sig, fs_calculado=fs_calculado, fs=1000.0,
        fmin=1.0, fmax=500.0, num_cycles=2.0,
    )
    handle.finished.connect(lambda r: listo.setdefault("ok", True))

    vueltas = 0
    t0 = time.monotonic()
    while "ok" not in listo and time.monotonic() - t0 < 30:
        qt_app.processEvents()
        vueltas += 1
        time.sleep(0.001)

    assert "ok" in listo, "el calculo nunca termino"
    assert vueltas > 20, (
        f"el bucle de eventos solo dio {vueltas} vueltas: la interfaz estuvo bloqueada")

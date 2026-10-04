import copy
import re
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
from plugins.preprocessing.prepare.artifact_remove.artifact_logic import (
    apply_modification_to_all_valid, escribir_modificacion, preparar_modificacion)
from plugins.preprocessing.prepare.artifact_remove.compute import calcular_modificacion


REPO = Path(__file__).resolve().parents[2]
ABF_PATH = REPO / "test" / "data" / "17308005.abf"


@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture(scope="module")
def senal_real():
    if not ABF_PATH.exists():
        pytest.skip("no se encontro el archivo ABF de prueba")
    sd = FileIOService().load_abf(str(ABF_PATH))
    sd.signals = sd.signals.astype(np.float64, copy=False)
    sd.time = sd.time.astype(np.float64, copy=False)
    return sd


def entorno(senal_real, descartes=(), canal=0):
    """Kernel con DataStore y TaskService, y una copia nueva de la senal con sus trials."""
    sd = copy.deepcopy(senal_real)
    td = tr.cut_trials_single_channel(
        ds=sd, channel=canal, stim_channel=1, threshold=0.7, t0=-0.05, t1=4.00,
        end_mode="until_next_onset", stim_expected=1, inter_stim_time=0.0,
        pad_value=0.0, debug=False)
    sd.add_trial_dataset(td)
    for i in descartes:
        sd.discard_trial(Path(td.source).name, td.channel_name, i)
    kernel = Kernel()
    store = DataStore()
    kernel.register_service("DataStore", store)
    kernel.register_service("TaskService", TaskService())
    store.set_active_signal(store.add_signal(sd))
    return kernel, sd, td


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


PARAMS = dict(mode="interpolate", point_a=1.00, point_b=1.20)


def test_por_el_orquestador_da_lo_mismo_que_sin_el(qt_app, senal_real):
    kernel_a, _, td_a = entorno(senal_real, descartes=(3, 10, 25))
    assert apply_modification_to_all_valid(kernel_a, **PARAMS) is True

    kernel_b, _, td_b = entorno(senal_real, descartes=(3, 10, 25))
    prep = preparar_modificacion(kernel_b)
    tasks = kernel_b.get_service("TaskService")
    h = tasks.submit(calcular_modificacion, owner="artifact_remove", t=prep.t, trials=prep.trials, **PARAMS)
    escrito = []
    h.finished.connect(lambda out: (escribir_modificacion(kernel_b, prep, out, PARAMS["mode"]),
                                    escrito.append(True)))
    assert wait_for(lambda: escrito)

    assert np.array_equal(td_a.trials, td_b.trials, equal_nan=True)
    assert td_a.metadata["modified_trials"] == td_b.metadata["modified_trials"]
    assert not {3, 10, 25} & td_b.metadata["modified_trials"], "los descartados no se modifican"


def test_el_calculo_no_toca_los_datos_compartidos(qt_app, senal_real):
    kernel, _, td = entorno(senal_real)
    antes = td.trials.copy()
    prep = preparar_modificacion(kernel)
    assert not np.shares_memory(prep.trials, td.trials), "el calculo debe recibir una copia"

    tasks = kernel.get_service("TaskService")
    h = tasks.submit(calcular_modificacion, owner="artifact_remove", t=prep.t, trials=prep.trials, **PARAMS)
    resultado = []
    h.finished.connect(resultado.append)
    assert wait_for(lambda: resultado)

    assert resultado[0] is not None
    assert np.array_equal(antes, td.trials), "solo escribir_modificacion puede cambiar los trials"


def test_no_escribe_si_los_trials_cambiaron_mientras_calculaba(qt_app, senal_real):
    kernel, sd, td = entorno(senal_real)
    prep = preparar_modificacion(kernel)
    out = calcular_modificacion(prep.t, prep.trials, **PARAMS)
    sd.discard_trial(Path(td.source).name, td.channel_name, 7)
    antes = td.trials.copy()

    with pytest.raises(RuntimeError, match="Los trials cambiaron"):
        escribir_modificacion(kernel, prep, out, PARAMS["mode"])
    assert np.array_equal(antes, td.trials)


def test_cancelar_no_escribe_nada(qt_app, senal_real):
    kernel, _, td = entorno(senal_real)
    antes = td.trials.copy()
    prep = preparar_modificacion(kernel)
    tasks = kernel.get_service("TaskService")
    h = tasks.submit(calcular_modificacion, owner="artifact_remove", t=prep.t, trials=prep.trials, **PARAMS)
    senales = []
    h.finished.connect(lambda out: senales.append("finished"))
    h.cancelled.connect(lambda: senales.append("cancelled"))

    tasks.cancel_all_from("artifact_remove")

    assert wait_for(lambda: senales and not tasks.has_active_tasks())
    assert senales == ["cancelled"]
    assert np.array_equal(antes, td.trials)


def test_funciona_con_trials_de_otro_canal(qt_app, senal_real):
    # Hasta el 30 de septiembre de 2026 siempre se usaba el primer canal de la
    # senal, y con trials de otro canal fallaba al buscar el TrialDataset base.
    kernel, sd, td = entorno(senal_real, canal=1)
    assert td.channel_name == sd.channel_names[1]
    antes = td.trials.copy()
    esperado = calcular_modificacion(td.time_rel, antes, **PARAMS)

    assert apply_modification_to_all_valid(kernel, **PARAMS) is True
    assert np.array_equal(td.trials, esperado, equal_nan=True)
    assert not np.array_equal(td.trials, antes)


def test_ningun_plugin_crea_hilos_propios():
    # Fase 3: todo trabajo en segundo plano pasa por core/services/task_service.py.
    patron = re.compile(r"\bQThread\b|moveToThread|threading\.Thread")
    culpables = [str(p.relative_to(REPO)) for p in (REPO / "plugins").rglob("*.py")
                 if patron.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert not culpables, f"estos plugins crean hilos propios en vez de usar el TaskService: {culpables}"

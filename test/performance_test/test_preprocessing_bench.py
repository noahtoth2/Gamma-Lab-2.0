# test/performance_test/test_preprocessing_bench.py
"""
Benchmark del cómputo de preprocesamiento que corre antes de cualquier análisis:
el filtro pasa-banda Butterworth de plugins/preprocessing/prepare/filter/
filter_plugin.py (run_filter -> scipy.signal.butter + sosfiltfilt).

Es una función pura (señal in, señal filtrada out), así que se benchmarkea
directamente sin necesidad de UI ni de un Kernel real -- Filter_plugin.__init__
no crea ningún widget de Qt/VTK, solo dejar atributos en None (confirmado
leyendo el código), por eso alcanza con instanciar el plugin real.

No se benchmarkea artifact_remove_plugin/artifact_logic.py en este archivo: su
lógica pública (apply_modification_to_all_valid) requiere un Kernel + DataStore
+ SignalDataset con trials ya generados y un historial de descartes armado, lo
cual la acopla fuertemente a un flujo de UI completo. Es, junto con el resto de
plugins/preprocessing/, uno de los puntos sin cobertura de test señalados en
docs/reporte_tests.tex (sección "Cobertura") -- extenderlo requeriría primero
extraer su lógica numérica (la búsqueda de índices por ventana de tiempo y el
relleno con spline/lineal) a una función pura, igual que ya está aquí para
run_filter.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pytest

from core.services.fileio_service import FileIOService
from core.filters import trials as tr
from core.plugins.meta import PluginMeta
from plugins.preprocessing.prepare.filter.filter_plugin import Filter_plugin

from bench_common import time_block, record

BASE_DIR = Path(__file__).resolve().parents[1] / "data"
ABF_PATH = BASE_DIR / "17308005.abf"

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(not ABF_PATH.exists(), reason="No se encontró el archivo ABF"),
]


def _meta():
    return PluginMeta(
        id="filter", name="Filter", category="Preprocessing", subcategory="Prepare",
        version="1.0", icon="", logic_class="Filter_plugin",
    )


@pytest.fixture(scope="module")
def ds():
    fio = FileIOService()
    sd = fio.load_abf(str(ABF_PATH))
    sd.signals = sd.signals.astype(np.float64, copy=False)
    sd.time = sd.time.astype(np.float64, copy=False)
    return sd


@pytest.fixture(scope="module")
def td(ds):
    return tr.cut_trials_single_channel(
        ds=ds, channel=0, stim_channel=1, threshold=0.7,
        t0=-0.05, t1=4.00, end_mode="until_next_onset",
        stim_expected=1, inter_stim_time=0.0, pad_value=0.0, debug=False,
    )


def test_bench_filter_run_filter_full_signal(ds):
    """Filtro Butterworth pasa-banda aplicado a la señal cruda completa (un canal)."""
    plug = Filter_plugin(_meta())
    signal = np.nan_to_num(ds.signals[0, :], nan=0.0, posinf=0.0, neginf=0.0)
    fs = float(ds.sampling_rate)

    stats = time_block(
        plug.run_filter, signal, 0.5, 4.0, 8, fs, "butterworth",
        reps=10, warmup=2,
    )
    record(f"filter.run_filter (señal completa, {signal.shape[0]} muestras)", stats)


def test_bench_filter_run_filter_single_trial(td):
    """Mismo filtro, pero sobre un único trial ya cortado (lo que dispara on_apply_filter por cada clic)."""
    plug = Filter_plugin(_meta())
    trial = np.nan_to_num(np.asarray(td.trials[:, 0], dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    fs = float(td.sampling_rate)

    stats = time_block(
        plug.run_filter, trial, 0.5, 4.0, 8, fs, "butterworth",
        reps=20, warmup=2,
    )
    record(f"filter.run_filter (1 trial, {trial.shape[0]} muestras)", stats)

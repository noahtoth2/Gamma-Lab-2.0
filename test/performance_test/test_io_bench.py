# test/performance_test/test_io_bench.py
"""
Benchmarks de carga de archivos (core/services/fileio_service.py), corte de
trials (core/filters/trials.py) y del almacén en memoria (core/services/
data_store.py). Estas tres cosas corren siempre en el hilo principal de Qt --
cargar un archivo y generar trials son, junto con el CWT de wavelet
(ver test_compute_bench.py), las operaciones que más tiempo real le hacen
esperar al usuario antes de poder ver cualquier gráfico.

Usa el mismo ABF real de test/data/ que el resto de la suite. No se benchmarkea
FileIOService.load_edf/load_mat porque test/data/ no tiene ningún archivo .edf
o .mat de referencia -- agregar uno es la forma más directa de extender esta
cobertura (ver docs).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pytest

from core.services.fileio_service import FileIOService
from core.services.data_store import DataStore
from core.filters import trials as tr

from bench_common import time_block, record

BASE_DIR = Path(__file__).resolve().parents[1] / "data"
ABF_PATH = BASE_DIR / "17308005.abf"

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(not ABF_PATH.exists(), reason="No se encontró el archivo ABF"),
]


# ---------------------------------------------------------------------
# FileIOService.load_abf -- lectura real de disco + parseo con pyabf
# ---------------------------------------------------------------------

def test_bench_load_abf():
    fio = FileIOService()
    stats = time_block(fio.load_abf, str(ABF_PATH), reps=5, warmup=1)
    ds = stats["result"]
    record(f"fileio.load_abf ({ds.signals.shape[0]} canales x {ds.signals.shape[1]} muestras)", stats)


# ---------------------------------------------------------------------
# core.filters.trials.cut_trials_single_channel -- detección de estímulos y
# corte de la señal continua en trials
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def ds():
    fio = FileIOService()
    sd = fio.load_abf(str(ABF_PATH))
    sd.signals = sd.signals.astype(np.float64, copy=False)
    sd.time = sd.time.astype(np.float64, copy=False)
    return sd


def test_bench_cut_trials_single_channel(ds):
    def run_once():
        return tr.cut_trials_single_channel(
            ds=ds, channel=0, stim_channel=1, threshold=0.7,
            t0=-0.05, t1=4.00, end_mode="until_next_onset",
            stim_expected=1, inter_stim_time=0.0, pad_value=0.0, debug=False,
        )

    stats = time_block(run_once, reps=10, warmup=2)
    td = stats["result"]
    record(f"trials.cut_trials_single_channel ({td.trials.shape[0]}x{td.trials.shape[1]})", stats)


# ---------------------------------------------------------------------
# DataStore -- diccionario central en memoria (todo el flujo de la app pasa
# por acá: cada señal cargada, cada juego de trials generado)
# ---------------------------------------------------------------------

def test_bench_datastore_add_signal(ds):
    """
    Costo de agregar N señales al DataStore con clave autogenerada
    (raw_signal_1, _2, _3...) -- el bucle while de add_signal() es O(n) por
    inserción en el peor caso, así que este número también sirve para ver si
    esa función deja de escalar con muchas señales cargadas en la misma sesión.
    """
    n = 500

    def run_once():
        store = DataStore()
        for _ in range(n):
            store.add_signal(ds)
        return store

    stats = time_block(run_once, reps=5, warmup=1)
    record(f"data_store.add_signal (x{n} señales, clave autogenerada)", stats)


def test_bench_datastore_set_get(ds):
    n = 2000

    def run_once():
        store = DataStore()
        for i in range(n):
            store.set(f"clave_{i}", ds)
        total = 0
        for i in range(n):
            if store.get(f"clave_{i}") is not None:
                total += 1
        return total

    stats = time_block(run_once, reps=5, warmup=1)
    record(f"data_store.set+get (x{n} pares clave/valor)", stats)

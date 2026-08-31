# test/performance_test/test_vtk_adapters_bench.py
"""
Benchmarks del camino de conversión a VTK que SÍ está vectorizado
(core/utils/adapters.py), y un micro-benchmark sintético que aísla, en forma
genérica, el costo del patrón "bucle de Python + InsertNextValue" contra
"vtk.util.numpy_support.numpy_to_vtk".

Por qué existe este archivo, junto a test_render_bench.py:

  - test_render_bench.py mide el costo REAL de wavelet/wavelet_average/erp, que
    hoy construyen su vtkImageData con un doble bucle de Python
    (SetScalarComponentFromFloat por píxel) -- el patrón LENTO.
  - Este archivo mide el costo REAL de dataset_to_vtk_table y
    trials_matrix_to_vtk_table, que ya usan numpy_to_vtk -- el patrón RÁPIDO,
    ya presente y probado en el propio repositorio.
  - El micro-benchmark sintético del final cuantifica la diferencia entre
    ambos patrones de forma aislada (sin CWT, sin ABF, solo la conversión a
    VTK en sí), así que también sirve para estimar el ahorro esperado si se
    vectoriza wavelet/wavelet_average/erp en Gamma Lab 2.0, y aplica igual a
    otro caso con el mismo patrón encontrado en filter_plugin.py
    (_render_filtered, líneas 251-254: arr_time.InsertNextValue /
    arr_signal.InsertNextValue dentro de un for por muestra).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pytest
import vtk
from vtkmodules.util import numpy_support

from core.services.fileio_service import FileIOService
from core.filters import trials as tr
from core.utils.adapters import dataset_to_vtk_table, trials_matrix_to_vtk_table

from bench_common import time_block, record

BASE_DIR = Path(__file__).resolve().parents[1] / "data"
ABF_PATH = BASE_DIR / "17308005.abf"

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(not ABF_PATH.exists(), reason="No se encontró el archivo ABF"),
]


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


# ---------------------------------------------------------------------
# core.utils.adapters -- ya vectorizado con numpy_to_vtk (patrón de referencia)
# ---------------------------------------------------------------------

def test_bench_dataset_to_vtk_table(ds):
    """
    dataset_to_vtk_table() cachea su resultado en ds.vtk_table -- se limpia el
    cache antes de cada repetición para medir el costo real de construir la
    tabla, no el de devolver el objeto cacheado.
    """
    def run_once():
        ds.vtk_table = None
        return dataset_to_vtk_table(ds)

    stats = time_block(run_once, reps=10, warmup=2)
    table = stats["result"]
    record(f"adapters.dataset_to_vtk_table ({table.GetNumberOfRows()}x{table.GetNumberOfColumns()}, vectorizado)", stats)


def test_bench_trials_matrix_to_vtk_table(td):
    t = np.asarray(td.time_rel, dtype=float)
    trials = np.nan_to_num(np.asarray(td.trials, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)

    stats = time_block(trials_matrix_to_vtk_table, t, trials, reps=10, warmup=2)
    table = stats["result"]
    record(
        f"adapters.trials_matrix_to_vtk_table ({table.GetNumberOfRows()}x{table.GetNumberOfColumns()}, vectorizado)",
        stats,
    )


# ---------------------------------------------------------------------
# Micro-benchmark sintético: bucle Python (InsertNextValue) vs numpy_to_vtk,
# para el mismo volumen de datos que maneja un escalograma real (~3M puntos)
# ---------------------------------------------------------------------

def _construir_con_bucle_python(x: np.ndarray) -> vtk.vtkFloatArray:
    arr = vtk.vtkFloatArray()
    arr.SetNumberOfComponents(1)
    for v in x:
        arr.InsertNextValue(float(v))
    return arr


def _construir_vectorizado(x: np.ndarray) -> vtk.vtkFloatArray:
    return numpy_support.numpy_to_vtk(x, deep=True)


@pytest.mark.parametrize("n_puntos", [50_000, 300_000])
def test_bench_vtk_array_bucle_vs_vectorizado(n_puntos):
    rng = np.random.default_rng(0)
    x = rng.random(n_puntos).astype(np.float64)

    stats_bucle = time_block(_construir_con_bucle_python, x, reps=5, warmup=1)
    record(f"vtk_array.bucle_python (x{n_puntos} puntos, patrón lento actual)", stats_bucle)

    stats_vec = time_block(_construir_vectorizado, x, reps=5, warmup=1)
    record(f"vtk_array.numpy_to_vtk (x{n_puntos} puntos, patrón vectorizado)", stats_vec)

    speedup = stats_bucle["median_s"] / stats_vec["median_s"]
    print(f"[perf] vectorizar {n_puntos} puntos es {speedup:.1f}x más rápido que el bucle de Python")

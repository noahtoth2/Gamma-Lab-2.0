# test/performance_test/test_compute_bench.py
"""
Benchmarks del tiempo de cómputo numérico puro que corre cada plugin de análisis
al hacer clic en "Calcular". Hoy fft, fft_average, psd, psd_average, relative_psd
y wavelet (individual) corren todos en el hilo principal de Qt, sin QThread -- así
que estos números son una medida directa de "cuánto se congela la interfaz por
cada clic en Calcular".

Usa el archivo ABF real de test/data/ y los métodos de cómputo reales de cada
plugin (nada de la matemática está mockeada), con el mismo pipeline de corte de
trials que los tests de comparación contra MATLAB de test/plugins_test/.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pytest

from core.services.fileio_service import FileIOService
from core.filters import trials as tr
from core.plugins.meta import PluginMeta

from plugins.analysis.frequency.fft.fft_plugin import Fft_plugin
from plugins.analysis.frequency.fft_average.fft_average_plugin import Fft_average_plugin
from plugins.analysis.frequency.psd.psd_plugin import Psd_plugin
from plugins.analysis.frequency.psd_average.psd_average_plugin import Psd_average_plugin
from plugins.analysis.frequency.relative_psd.relative_psd_plugin import Relative_psd_plugin
from plugins.analysis.time_frequency.wavelet.wavelet_plugin import Wavelet_plugin
from plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin import Wavelet_average_plugin

from bench_common import time_block, record

BASE_DIR = Path(__file__).resolve().parents[1] / "data"
ABF_PATH = BASE_DIR / "17308005.abf"

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(not ABF_PATH.exists(), reason="No se encontró el archivo ABF"),
]


def _meta(id_, name, subcat, cls):
    return PluginMeta(
        id=id_, name=name, category="analysis", subcategory=subcat,
        version="0.0.0", icon="", logic_class=cls,
    )


@pytest.fixture(scope="module")
def ds():
    """Carga el ABF real una única vez para todo el archivo (fixture de módulo)."""
    fio = FileIOService()
    sd = fio.load_abf(str(ABF_PATH))
    sd.signals = sd.signals.astype(np.float64, copy=False)
    sd.time = sd.time.astype(np.float64, copy=False)
    return sd


@pytest.fixture(scope="module")
def td(ds):
    """Corta los trials una única vez, con los mismos parámetros que plugins_test."""
    return tr.cut_trials_single_channel(
        ds=ds, channel=0, stim_channel=1, threshold=0.7,
        t0=-0.05, t1=4.00, end_mode="until_next_onset",
        stim_expected=1, inter_stim_time=0.0, pad_value=0.0, debug=False,
    )


@pytest.fixture(scope="module")
def X(td):
    """Matriz de trials (Ns, T) real, todos los trials, float64, sin NaN."""
    x = np.asarray(td.trials, dtype=np.float64).copy()
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


@pytest.fixture(scope="module")
def fs(td):
    return float(td.sampling_rate)


@pytest.fixture(scope="module")
def t_rel(td):
    return np.asarray(td.time_rel, dtype=np.float64)


# ---------------------------------------------------------------------
# FFT (espectro de magnitud sin ventana, sin QThread hoy)
# ---------------------------------------------------------------------

def test_bench_fft_compute(X, fs):
    plug = Fft_plugin(_meta("fft", "FFT", "frequency", "Fft_plugin"))
    stats = time_block(plug._compute_fft, X, fs, 1000.0, reps=5, warmup=1)
    record("fft._compute_fft (todos los trials)", stats)


def test_bench_fft_average_compute(X, fs):
    plug = Fft_average_plugin(_meta("fft_average", "FFT Average", "frequency", "Fft_average_plugin"))
    stats = time_block(plug._compute_fft_average, X, fs, 1000.0, reps=5, warmup=1)
    record("fft_average._compute_fft_average (todos los trials)", stats)


# ---------------------------------------------------------------------
# PSD (Welch, sin QThread hoy)
# ---------------------------------------------------------------------

def test_bench_psd_compute(X, fs):
    plug = Psd_plugin(_meta("psd", "PSD", "frequency", "Psd_plugin"))
    stats = time_block(
        plug._compute_psd, X, fs, 1000.0, "hamming", 256, 128, 256, "none",
        reps=5, warmup=1,
    )
    record("psd._compute_psd (todos los trials, Welch)", stats)


def test_bench_psd_average_compute(X, fs):
    # Nota: a diferencia de psd/relative_psd, psd_average._compute_psd no tiene
    # parámetro `detrend`, y limpia los NaN de su entrada in-place (copy=False) --
    # por eso se le pasa una copia fresca de X en cada repetición, en vez de
    # reutilizar la fixture `X` compartida.
    plug = Psd_average_plugin(_meta("psd_average", "PSD Average", "frequency", "Psd_average_plugin"))

    def run_once():
        return plug._compute_psd(X.copy(), fs, 1000.0, "hamming", 256, 128, 256)

    stats = time_block(run_once, reps=5, warmup=1)
    record("psd_average._compute_psd (todos los trials, Welch)", stats)


def test_bench_relative_psd_compute(X, fs):
    plug = Relative_psd_plugin(_meta("relative_psd", "Relative PSD", "frequency", "Relative_psd_plugin"))
    freq, pxx_all, fs_eff = plug._compute_psd(X.copy(), fs, 1000.0, "hamming", 256, 128, 256, "none")
    stats = time_block(plug._compute_relative_psd, freq, pxx_all, 8.0, 12.0, 1, reps=5, warmup=1)
    record("relative_psd._compute_relative_psd (solo la razón)", stats)

    stats_full = time_block(
        plug._compute_psd, X, fs, 1000.0, "hamming", 256, 128, 256, "none",
        reps=5, warmup=1,
    )
    record("relative_psd._compute_psd (todos los trials, Welch)", stats_full)


# ---------------------------------------------------------------------
# Wavelet CWT (el plugin individual no tiene QThread; el promedio sí)
# ---------------------------------------------------------------------

def test_bench_wavelet_single_trial_cwt(X, t_rel):
    plug = Wavelet_plugin(_meta("wavelet", "Wavelet", "time_frequency", "Wavelet_plugin"))
    sig = X[:, 0]
    fs_calc = round(1.0 / (t_rel[1] - t_rel[0]), 3)
    stats = time_block(
        plug.compute_wavelet, sig, fs_calc, 1000.0, 1.0, 500.0, 2.0,
        reps=3, warmup=1,
    )
    record("wavelet.compute_wavelet (1 trial, hilo principal hoy)", stats)


def test_bench_wavelet_average_cwt_all_trials(X, t_rel):
    """
    Reproduce lo que WaveletWorker.run() hace por cada trial (hoy ya corre fuera
    del hilo principal, vía QThread) -- útil para ver si el CWT en sí se vuelve
    más rápido en 2.0, independientemente del arreglo de threading.
    """
    plug = Wavelet_average_plugin(_meta("wavelet_average", "Wavelet Average", "time_frequency", "Wavelet_average_plugin"))
    fs_calc = round(1.0 / (t_rel[1] - t_rel[0]), 3)
    n_trials = min(X.shape[1], 20)  # tope para que la suite se mantenga rápida; ajustar si hace falta

    def compute_all_trials():
        for k in range(n_trials):
            plug.compute_wavelet(X[:, k], fs_calc, 1000.0, 1.0, 500.0, 2.0)

    stats = time_block(compute_all_trials, reps=2, warmup=1)
    record(f"wavelet_average.compute_wavelet (x{n_trials} trials, hilo secundario hoy)", stats)

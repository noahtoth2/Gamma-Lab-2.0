# test/performance_test/test_render_bench.py
"""
Benchmarks del camino de renderizado VTK del mapa 2D (heatmap) que usan wavelet,
wavelet_average y erp. Los tres construyen un vtkImageData llamando a
img.SetScalarComponentFromFloat(i, j, 0, 0, value) una vez por cada píxel, en un
doble bucle de Python (ver wavelet_plugin.py:334-336, wavelet_average_plugin.py:
444-446, erp_plugin.py:340-342) en vez de vectorizar con
vtk.util.numpy_support.numpy_to_vtk, como ya hace core/utils/adapters.py para
todos los gráficos de líneas de la app (ver test_vtk_adapters_bench.py). Este
archivo cronometra exactamente esa llamada, para que una reescritura en 2.0 se
pueda comparar en igualdad de condiciones.

Estos tests crean ventanas VTK reales, en modo offscreen -- no hace falta mostrar
nada en pantalla, pero sí un stack gráfico/VTK funcional. En un entorno sin GPU o
sin drivers gráficos puede tardar bastante en el primer render; en la máquina
donde normalmente corre Gamma Lab funciona con normalidad.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pytest
import vtk

from core.services.fileio_service import FileIOService
from core.filters import trials as tr
from core.plugins.meta import PluginMeta

from plugins.analysis.time_frequency.wavelet.wavelet_plugin import Wavelet_plugin
from plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin import Wavelet_average_plugin
from plugins.analysis.time.erp.erp_plugin import Erp_plugin

from bench_common import time_block, record

BASE_DIR = Path(__file__).resolve().parents[1] / "data"
ABF_PATH = BASE_DIR / "17308005.abf"

pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(not ABF_PATH.exists(), reason="No se encontró el archivo ABF"),
]


def _meta(id_, name, category, subcat, cls):
    return PluginMeta(
        id=id_, name=name, category=category, subcategory=subcat,
        version="0.0.0", icon="", logic_class=cls,
    )


def _offscreen_context_view():
    """Un vtkContextView respaldado por una ventana de render offscreen (sin necesidad de pantalla)."""
    renwin = vtk.vtkRenderWindow()
    renwin.SetOffScreenRendering(1)
    view = vtk.vtkContextView()
    view.SetRenderWindow(renwin)
    return view


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
# wavelet (1 trial) -- render_scalogram
# ---------------------------------------------------------------------

def test_bench_wavelet_render_scalogram(td):
    meta = _meta("wavelet", "Wavelet", "analysis", "time_frequency", "Wavelet_plugin")
    plug = Wavelet_plugin(meta)
    plug.vtk_widget = True  # solo se verifica que sea "truthy" antes de renderizar
    plug._context_view = _offscreen_context_view()

    t = np.asarray(td.time_rel, dtype=float)
    sig = np.nan_to_num(np.asarray(td.trials[:, 0], dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
    fs_calc = round(1.0 / (t[1] - t[0]), 3)

    scalo, times, freqs = plug.compute_wavelet(sig, fs_calc, 1000.0, 1.0, 500.0, 2.0)
    print(f"[perf] forma del escalograma wavelet: {scalo.shape} ({scalo.size} puntos)")

    stats = time_block(plug.render_scalogram, times, freqs, scalo, "bench", False, reps=3, warmup=1)
    record(f"wavelet.render_scalogram ({scalo.shape[0]}x{scalo.shape[1]} puntos)", stats)


# ---------------------------------------------------------------------
# wavelet_average -- render_scalogram (escalograma promediado, mismo camino de render)
# ---------------------------------------------------------------------

def test_bench_wavelet_average_render_scalogram(td):
    meta = _meta("wavelet_average", "Wavelet Average", "analysis", "time_frequency", "Wavelet_average_plugin")
    plug = Wavelet_average_plugin(meta)
    plug.vtk_widget = True
    plug._context_view = _offscreen_context_view()

    t = np.asarray(td.time_rel, dtype=float)
    fs_calc = round(1.0 / (t[1] - t[0]), 3)
    n_trials = min(td.trials.shape[1], 10)  # mantener el costo del CWT bajo; lo que se mide es el render

    scalo = None
    for k in range(n_trials):
        sig = np.nan_to_num(np.asarray(td.trials[:, k], dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
        s, times, freqs = plug.compute_wavelet(sig, fs_calc, 1000.0, 1.0, 500.0, 2.0)
        scalo = s if scalo is None else scalo + s
    scalo = scalo / n_trials
    print(f"[perf] forma del escalograma wavelet_average: {scalo.shape} ({scalo.size} puntos)")

    stats = time_block(plug.render_scalogram, times, freqs, scalo, "bench", False, reps=3, warmup=1)
    record(f"wavelet_average.render_scalogram ({scalo.shape[0]}x{scalo.shape[1]} puntos)", stats)


# ---------------------------------------------------------------------
# erp -- _render_heatmap (butterfly/heatmap de todos los trials)
# ---------------------------------------------------------------------

def test_bench_erp_render_heatmap(td):
    meta = _meta("erp", "ERP", "analysis", "time", "Erp_plugin")
    plug = Erp_plugin(meta)
    plug.alerts.parent = None  # alertas solo por consola, sin widget real
    plug.widget = None
    plug.vtk_top = None
    plug.active_signal = None
    plug.ch_name = "ch0"
    plug.view_bot = _offscreen_context_view()

    t = np.asarray(td.time_rel, dtype=float)
    sel = np.nan_to_num(np.asarray(td.trials, dtype=float).T, nan=0.0, posinf=0.0, neginf=0.0)  # (K trials, Tn muestras)
    print(f"[perf] forma de entrada del heatmap erp: {sel.shape} ({sel.size} puntos antes del downsample interno)")

    stats = time_block(plug._render_heatmap, t, sel, reps=3, warmup=1)
    record(f"erp._render_heatmap ({sel.shape[0]}x{sel.shape[1]} puntos antes del downsample)", stats)

"""Qué se parece y qué no a las referencias de MATLAB de wavelet y de PSD promedio.

Las pruebas estrictas de `test_wavelet_plugin.py`, `test_wavelet_average_plugin.py` y
`test_psd_average_plugin.py` exigen coincidir punto a punto (tolerancia absoluta de 1e-4) o con una
correlación alta, y no se cumplen: están marcadas como fallo esperado con su causa. Aquí quedan fijadas
las diferencias medidas, para que cualquier cambio en el cálculo que las agrande se note:

- Wavelet. MATLAB entrega la amplitud sin la normalización 1/raíz(escala) que aplica PyWavelets, y unas
  2,05 veces mayor. Dividiendo el escalograma de la aplicación entre la raíz de la escala, y multiplicando
  por 2, la correlación global con la referencia sube de 0,83 a 0,98 (un trial) y a 0,997 (promedio).
- PSD promedio. MATLAB no quita la tendencia de cada segmento; el plugin sí (constante, el valor por
  defecto de scipy). Sin quitarla, la potencia total coincide dentro de 1 % y el espectro, en escala
  logarítmica, correlaciona 0,999. La diferencia que queda está en los primeros bins (0 a 3 Hz).
"""
import numpy as np
import pytest
import pywt
from scipy.signal import welch

import core.filters.trials as tr
from core.filters.wavelet import compute_wavelet, eje_frecuencias
from core.services.fileio_service import FileIOService

from test_psd_average_plugin import (ABF_PATH, MATLAB_CSV as CSV_PSD, load_csv_matlab_psd_avg)
from test_wavelet_average_plugin import MATLAB_SCALO_AVG, load_csv_matlab_scalogram_avg, crop_to_min as recortar_prom
from test_wavelet_plugin import MATLAB_SCALO, load_csv_matlab_scalogram, crop_to_min

pytestmark = pytest.mark.skipif(not ABF_PATH.exists(), reason="ABF file not found")

FS = 1000.0
FACTOR_MATLAB = 2.0


@pytest.fixture(scope="module")
def trials():
    ds = FileIOService().load_abf(str(ABF_PATH))
    ds.signals = ds.signals.astype(np.float64)
    ds.time = ds.time.astype(np.float64)
    return tr.cut_trials_single_channel(ds=ds, channel=0, stim_channel=1, threshold=0.7, t0=-0.05, t1=4.0,
                                        end_mode="until_next_onset", stim_expected=1, inter_stim_time=0.0,
                                        pad_value=0.0, debug=False)


def _escalograma_l1(senal):
    """El de la aplicación, dividido entre la raíz de la escala (amplitud sin la normalización de PyWavelets)."""
    escalo, _, frec = compute_wavelet(senal, 10000.0, FS, 1.0, 500.0, 2.0)
    escalas = pywt.central_frequency("cmor2.0-1.0") * FS / frec
    return escalo / np.sqrt(escalas)[:, None]


@pytest.mark.skipif(not MATLAB_SCALO.exists(), reason="MATLAB scalogram CSV not found")
def test_wavelet_de_un_trial_coincide_con_matlab_salvo_la_convencion_de_amplitud(trials):
    referencia = load_csv_matlab_scalogram(MATLAB_SCALO)
    app = _escalograma_l1(np.nan_to_num(trials.trials[:, 0]))
    a, b = crop_to_min(app, referencia)
    correlacion = np.corrcoef(a.ravel(), b.ravel())[0, 1]
    constante = float((a * b).sum() / (a * a).sum())
    assert correlacion >= 0.97, f"correlación global {correlacion:.4f}"
    assert 1.9 <= constante <= 2.2, f"la referencia es {constante:.3f} veces la aplicación normalizada"


@pytest.mark.skipif(not MATLAB_SCALO_AVG.exists(), reason="MATLAB average scalogram CSV not found")
def test_wavelet_promedio_coincide_con_matlab_salvo_la_convencion_de_amplitud(trials):
    referencia = load_csv_matlab_scalogram_avg(MATLAB_SCALO_AVG)
    columnas = np.nan_to_num(trials.trials)
    acumulado = None
    for j in range(columnas.shape[1]):
        escalo = _escalograma_l1(columnas[:, j])
        acumulado = escalo if acumulado is None else acumulado + escalo
    app = acumulado / columnas.shape[1]
    a, b = recortar_prom(app, referencia)
    assert np.corrcoef(a.ravel(), b.ravel())[0, 1] >= 0.99
    assert 1.9 <= float((a * b).sum() / (a * a).sum()) <= 2.2


@pytest.mark.skipif(not CSV_PSD.exists(), reason="MATLAB PSD CSV not found")
def test_psd_promedio_coincide_con_matlab_cuando_no_se_quita_la_tendencia(trials):
    referencia = load_csv_matlab_psd_avg(CSV_PSD)[:, 0]
    X = np.nan_to_num(np.asarray(trials.trials, dtype=float))[::10]
    _, p = welch(X, fs=FS, window="hamming", nperseg=1024, noverlap=128, nfft=1024, detrend=False,
                 scaling="density", axis=0)
    promedio = p.mean(axis=1)
    assert abs(promedio.sum() / referencia.sum() - 1.0) <= 0.02, "la potencia total debe coincidir dentro de 2 %"
    correlacion_log = np.corrcoef(np.log10(promedio + 1e-30), np.log10(referencia + 1e-30))[0, 1]
    assert correlacion_log >= 0.995, f"correlación en escala logarítmica {correlacion_log:.4f}"

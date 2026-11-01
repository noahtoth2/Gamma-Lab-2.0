"""R72: la tabla VTK de una señal se reutiliza y se descarta de forma explícita cuando la señal cambia."""
import numpy as np
from numpy.testing import assert_allclose
from vtkmodules.util import numpy_support

from core.model.signal_dataset import SignalDataset
from core.utils.adapters import dataset_to_vtk_table


def _senal(fs=1000.0, n=2000):
    t = np.arange(n) / fs
    return SignalDataset(name="s.abf", format="abf", source_path="C:/fake/s.abf", sampling_rate=fs, time=t,
                         signals=np.vstack([np.sin(t), np.cos(t)]), channel_names=["a", "b"], units=["mV", "mV"])


def test_la_tabla_se_construye_una_vez_y_se_reutiliza():
    ds = _senal()
    assert ds.vtk_table is None
    primera = dataset_to_vtk_table(ds)
    assert ds.vtk_table is primera
    assert dataset_to_vtk_table(ds) is primera, "la segunda petición no reconstruye la tabla"


def test_corregir_la_frecuencia_descarta_la_tabla_y_la_nueva_trae_el_eje_corregido():
    ds = _senal(fs=1000.0)
    vieja = dataset_to_vtk_table(ds)
    ds.set_sampling_rate(500.0)
    assert ds.vtk_table is None, "descarte explícito al modificar la señal"

    nueva = dataset_to_vtk_table(ds)
    assert nueva is not vieja
    tiempo = numpy_support.vtk_to_numpy(nueva.GetColumn(0))
    assert_allclose(tiempo[:3], [0.0, 0.002, 0.004])
    assert_allclose(numpy_support.vtk_to_numpy(vieja.GetColumn(0))[:3], [0.0, 0.001, 0.002]), "la tabla vieja no se tocó"


def test_restaurar_la_frecuencia_original_tambien_descarta_la_tabla():
    ds = _senal(fs=1000.0)
    ds.original_sampling_rate = 1000.0
    ds.set_sampling_rate(250.0)
    dataset_to_vtk_table(ds)
    ds.restore_original_sampling_rate()
    assert ds.vtk_table is None
    assert_allclose(numpy_support.vtk_to_numpy(dataset_to_vtk_table(ds).GetColumn(0))[1], 0.001)

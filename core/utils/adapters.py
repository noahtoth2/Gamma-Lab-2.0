import vtk
import numpy as np
from vtkmodules.util import numpy_support
from core.services.fileio_service import SignalDataset

def dataset_to_vtk_table(ds: SignalDataset) -> vtk.vtkTable:
    """
    Convert the dataset to a vtkTable:
    - Column 0: time
    - Columns 1..C: each channel
    Cached in ds.vtk_table to avoid repeated work.
    """
    if ds.vtk_table is not None:
        return ds.vtk_table

    C, N = ds.signals.shape
    assert ds.time.shape[0] == N, "time and signals lengths do not match"

    table = vtk.vtkTable()

    # time column
    arr_time = numpy_support.numpy_to_vtk(ds.time.astype(np.float64), deep=True)
    arr_time.SetName("time")
    table.AddColumn(arr_time)

    # per-channel columns
    for ch in range(C):
        arr = numpy_support.numpy_to_vtk(ds.signals[ch].astype(np.float64), deep=True)
        name = ds.channel_names[ch] if ch < len(ds.channel_names) else f"ch{ch}"
        arr.SetName(name)
        table.AddColumn(arr)

    table.SetNumberOfRows(N)
    ds.vtk_table = table
    return table

def trials_matrix_to_vtk_table(time_rel: np.ndarray, trials: np.ndarray) -> vtk.vtkTable:
    """
    Create a vtkTable: col 0 = 'time', cols 1..T = trial_j
    trials: (Ns, T)
    """
    Ns, T = trials.shape
    table = vtk.vtkTable()

    arr_t = numpy_support.numpy_to_vtk(time_rel.astype(np.float64), deep=True)
    arr_t.SetName("time")
    table.AddColumn(arr_t)

    for j in range(T):
        arr = numpy_support.numpy_to_vtk(trials[:, j].astype(np.float64), deep=True)
        arr.SetName(f"trial_{j+1}")
        table.AddColumn(arr)

    table.SetNumberOfRows(Ns)
    return table

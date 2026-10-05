"""El llenado vectorizado de VTK en el mapa de calor de ERP da lo mismo que el bucle.

El problema nº 23: `_render_heatmap` llenaba la imagen punto por punto desde
Python, el patrón que el paso 1.3 ya había reemplazado en los dos plugins de
wavelet. Estas pruebas fijan que el reemplazo no cambia ni un valor.

No hace falta OpenGL: vtkImageData es una estructura de datos, no una ventana.
"""
import numpy as np
import pytest
import vtk
from vtkmodules.util import numpy_support


def llenar_con_bucle(X, dt, t0):
    """El código original, antes del arreglo del nº 23."""
    K, Tn = X.shape
    img = vtk.vtkImageData()
    img.SetDimensions(Tn, K, 1)
    img.SetSpacing(dt, 1.0, 1.0)
    img.SetOrigin(t0, 0.0, 0.0)
    img.AllocateScalars(vtk.VTK_FLOAT, 1)
    for j in range(K):
        for i in range(Tn):
            img.SetScalarComponentFromFloat(i, j, 0, 0, X[j, i])
    img.Modified()
    return img


def llenar_vectorizado(X, dt, t0):
    """El código de hoy, copiado de _render_heatmap."""
    K, Tn = X.shape
    img = vtk.vtkImageData()
    img.SetDimensions(Tn, K, 1)
    img.SetSpacing(dt, 1.0, 1.0)
    img.SetOrigin(t0, 0.0, 0.0)
    X_plano = np.ascontiguousarray(X, dtype=np.float32).ravel()
    arr = numpy_support.numpy_to_vtk(X_plano, deep=True, array_type=vtk.VTK_FLOAT)
    img.GetPointData().SetScalars(arr)
    img.Modified()
    return img


def _escalares(img):
    return numpy_support.vtk_to_numpy(img.GetPointData().GetScalars()).copy()


@pytest.mark.parametrize("n_trials,n_muestras", [(1, 10), (3, 500), (20, 2000), (60, 2000), (7, 13)])
def test_mismos_escalares_que_el_bucle(n_trials, n_muestras):
    rng = np.random.default_rng(n_trials * 100 + n_muestras)
    X = rng.standard_normal((n_trials, n_muestras)).astype(np.float32)
    dt, t0 = 0.00152, -0.05

    a = llenar_con_bucle(X, dt, t0)
    b = llenar_vectorizado(X, dt, t0)

    assert np.array_equal(_escalares(a), _escalares(b)), "el llenado vectorizado cambio algun valor"
    assert a.GetDimensions() == b.GetDimensions()
    assert a.GetScalarRange() == b.GetScalarRange()
    assert a.GetSpacing() == b.GetSpacing()
    assert a.GetOrigin() == b.GetOrigin()


def test_el_tiempo_queda_en_la_x():
    """Si se invirtiera el orden, la imagen saldria transpuesta: es el riesgo
    que el plan anoto para la vectorizacion del paso 1.3."""
    X = np.array([[1.0, 2.0, 3.0],
                  [4.0, 5.0, 6.0]], dtype=np.float32)
    img = llenar_vectorizado(X, 1.0, 0.0)

    # (x=tiempo, y=trial): el valor en (i, j) debe ser X[j, i]
    for j in range(X.shape[0]):
        for i in range(X.shape[1]):
            assert img.GetScalarComponentAsFloat(i, j, 0, 0) == X[j, i], \
                f"el punto ({i}, {j}) no corresponde a X[{j}, {i}]"


def test_los_nan_se_conservan():
    X = np.array([[1.0, np.nan], [np.nan, 4.0]], dtype=np.float32)
    a, b = llenar_con_bucle(X, 1.0, 0.0), llenar_vectorizado(X, 1.0, 0.0)
    sa, sb = _escalares(a), _escalares(b)
    assert np.array_equal(np.isnan(sa), np.isnan(sb)), "los NaN no quedaron en los mismos puntos"
    assert np.array_equal(sa[~np.isnan(sa)], sb[~np.isnan(sb)])

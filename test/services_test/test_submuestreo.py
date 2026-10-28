"""R73: se dibujan a lo sumo 2000 puntos por serie, sin alterar los datos."""
import gc

import numpy as np
import vtk

from core.utils import submuestreo as sm
from core.utils.submuestreo import agregar_linea, indices_reducidos, recortar, tabla_de

N = 200_000


def _senal():
    x = np.arange(N) / 1000.0
    y = np.sin(x * 2) + 0.01 * np.random.default_rng(1).standard_normal(N)
    y[N // 3] = 9.0
    y[2 * N // 3] = -9.0
    return x, y


def test_reducir_conserva_extremos_y_limita_los_puntos():
    x, y = _senal()
    idx = indices_reducidos(y)
    assert len(idx) <= sm.MAX_PUNTOS + 2
    assert idx[0] == 0 and idx[-1] == N - 1 and np.all(np.diff(idx) > 0)
    assert y[idx].max() == 9.0 and y[idx].min() == -9.0, "los picos no se pierden"


def test_una_serie_corta_no_se_toca():
    y = np.arange(500.0)
    assert np.array_equal(indices_reducidos(y), np.arange(500))


def test_nan_no_rompe_la_reduccion():
    y = np.sin(np.arange(10_000) / 50.0)
    y[100:900] = np.nan
    y[5000:6000] = np.nan
    idx = indices_reducidos(y)
    assert len(idx) <= sm.MAX_PUNTOS + 2


def test_recortar_al_rango_visible_da_resolucion_completa_si_cabe():
    x, y = _senal()
    xs, ys = recortar(x, y, 10.0, 11.0)
    assert 1000 <= len(xs) <= 1004, "1 s a 1 kHz son 1000 muestras: se dibujan todas"
    assert xs[0] <= 10.0 and xs[-1] >= 11.0


def test_la_serie_dibujada_es_corta_y_los_datos_completos_siguen_disponibles():
    x, y = _senal()
    chart = vtk.vtkChartXY()
    plot = agregar_linea(chart, x, y, "Time (s)", "CA1")
    assert plot.GetInput().GetNumberOfRows() <= sm.MAX_PUNTOS + 2
    completa = tabla_de(plot)
    assert completa.GetNumberOfRows() == N
    assert completa.GetColumn(1).GetName() == "CA1"
    assert np.array_equal(np.array([completa.GetColumn(1).GetValue(i) for i in (0, 1234, N - 1)]),
                          y[[0, 1234, N - 1]])


def test_una_serie_corta_se_dibuja_completa_sin_controlador():
    chart = vtk.vtkChartXY()
    plot = agregar_linea(chart, np.arange(100.0), np.arange(100.0), "x", "y")
    assert plot.GetInput().GetNumberOfRows() == 100
    assert getattr(chart, "_submuestreo", None) is None


def test_al_acercar_el_eje_se_recupera_el_detalle_y_al_alejar_vuelve_la_vista_general():
    x, y = _senal()
    chart = vtk.vtkChartXY()
    plot = agregar_linea(chart, x, y, "Time (s)", "CA1")
    eje = chart.GetAxis(vtk.vtkAxis.BOTTOM)

    eje.SetRange(0.0, 7.0)          # rango por defecto del eje: no es un zoom
    assert plot.GetInput().GetNumberOfRows() <= sm.MAX_PUNTOS + 2
    assert plot.GetInput().GetColumn(0).GetRange()[1] > 150, "sigue mostrando toda la serie"

    eje.SetRange(0.0, x[-1])        # el eje abarca los datos: se arma
    eje.SetRange(10.0, 10.5)        # zoom: 500 muestras
    tabla = plot.GetInput()
    assert 500 <= tabla.GetNumberOfRows() <= 504
    assert tabla.GetColumn(0).GetRange()[0] <= 10.0

    eje.SetRange(0.0, x[-1])
    assert plot.GetInput().GetNumberOfRows() <= sm.MAX_PUNTOS + 2
    assert tabla_de(plot).GetNumberOfRows() == N, "los datos nunca cambian"


def test_el_registro_se_limpia_cuando_se_destruye_el_plot():
    x, y = _senal()
    antes = len(sm._COMPLETAS)
    chart = vtk.vtkChartXY()
    agregar_linea(chart, x, y, "t", "y")
    assert len(sm._COMPLETAS) == antes + 1
    del chart
    gc.collect()
    assert len(sm._COMPLETAS) == antes


def test_agregar_columna_toma_x_de_la_columna_cero():
    from core.utils.adapters import trials_matrix_to_vtk_table
    t = np.arange(5000) / 100.0
    tabla = trials_matrix_to_vtk_table(t, np.vstack([np.sin(t), np.cos(t)]).T)
    chart = vtk.vtkChartXY()
    p = sm.agregar_columna(chart, tabla, 2)
    assert tabla_de(p).GetColumn(1).GetName() == "trial_2"
    assert p.GetInput().GetNumberOfRows() <= sm.MAX_PUNTOS + 2

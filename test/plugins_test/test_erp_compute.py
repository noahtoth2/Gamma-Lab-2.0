"""Pruebas de preparar_mapa_calor, el cálculo que la Fase 4 sacó de _render_heatmap.

El mapa de calor de ERP no lo cubría ninguna prueba: la lógica vivía dentro del
método de dibujo, y sin pantalla no se puede dibujar. Al extraerla a compute.py
queda comprobable, y el oráculo es el código original tal como estaba.
"""
import numpy as np
import pytest

from plugins.analysis.time.erp.compute import MAX_MUESTRAS, preparar_mapa_calor


def oraculo(t, sel, max_muestras=MAX_MUESTRAS):
    """El cálculo original, copiado literalmente de _render_heatmap antes de la Fase 4."""
    X = np.asarray(sel, dtype=np.float32)
    K, Tn = X.shape
    t = np.asarray(t)
    if Tn > max_muestras:
        factor = int(np.ceil(Tn / max_muestras))
        X = X[:, ::factor]
        t = t[::factor]
        Tn = X.shape[1]
    finite = np.isfinite(X)
    if finite.any():
        p2, p98 = np.nanpercentile(X[finite], (2, 98))
        if p98 <= p2:
            vmin = float(X[finite].min())
            vmax = float(X[finite].max()) if float(X[finite].max()) > vmin else (vmin + 1.0)
        else:
            vmin, vmax = float(p2), float(p98)
    else:
        vmin, vmax = 0.0, 1.0
    t0 = float(t[0]) if t.size > 0 else 0.0
    t_end = float(t[-1]) if t.size > 0 else 1.0
    dt = (t_end - t0) / Tn if Tn > 0 else 1.0
    return X, t, vmin, vmax, t0, t_end, dt


def _datos(n_trials, n_muestras, semilla=0):
    rng = np.random.default_rng(semilla)
    t = np.linspace(-0.05, 3.0, n_muestras)
    sel = rng.standard_normal((n_trials, n_muestras)).astype(np.float32)
    return t, sel


@pytest.mark.parametrize("n_trials,n_muestras", [(3, 500), (10, 2000), (5, 2001), (60, 30510), (1, 7)])
def test_coincide_con_el_codigo_original(n_trials, n_muestras):
    t, sel = _datos(n_trials, n_muestras)
    X, tt, vmin, vmax, t0, t_end, dt, factor = preparar_mapa_calor(t, sel)
    eX, et, evmin, evmax, et0, et_end, edt = oraculo(t, sel)

    assert np.array_equal(X, eX), "la matriz submuestreada no coincide con la original"
    assert np.array_equal(tt, et), "el eje de tiempo no coincide"
    assert (vmin, vmax) == (evmin, evmax), "el rango de color no coincide"
    assert (t0, t_end, dt) == (et0, et_end, edt), "los parametros de tiempo no coinciden"
    assert factor == max(1, int(np.ceil(n_muestras / MAX_MUESTRAS)))


def test_sin_submuestreo_debajo_del_limite():
    t, sel = _datos(4, MAX_MUESTRAS)
    X, tt, _, _, _, _, _, factor = preparar_mapa_calor(t, sel)
    assert factor == 1
    assert X.shape == (4, MAX_MUESTRAS)
    assert tt.size == MAX_MUESTRAS


def test_submuestrea_por_encima_del_limite():
    t, sel = _datos(4, 30510)
    X, tt, _, _, _, _, _, factor = preparar_mapa_calor(t, sel)
    assert factor == 16
    assert X.shape[1] <= MAX_MUESTRAS
    assert X.shape[1] == tt.size, "la matriz y el eje de tiempo deben quedar del mismo largo"


def test_eje_de_tiempo_y_dt():
    t = np.linspace(-0.05, 3.0, 100)
    sel = np.zeros((2, 100), dtype=np.float32)
    _, _, _, _, t0, t_end, dt, _ = preparar_mapa_calor(t, sel)
    assert t0 == pytest.approx(-0.05)
    assert t_end == pytest.approx(3.0)
    assert dt == pytest.approx((3.0 - (-0.05)) / 100)


def test_datos_constantes_no_dan_rango_vacio():
    t = np.linspace(0, 1, 50)
    sel = np.full((3, 50), 7.0, dtype=np.float32)
    _, _, vmin, vmax, _, _, _, _ = preparar_mapa_calor(t, sel)
    assert vmax > vmin, "con datos constantes el rango de color no puede quedar degenerado"


def test_todo_nan_cae_en_el_rango_por_defecto():
    t = np.linspace(0, 1, 50)
    sel = np.full((3, 50), np.nan, dtype=np.float32)
    _, _, vmin, vmax, _, _, _, _ = preparar_mapa_calor(t, sel)
    assert (vmin, vmax) == (0.0, 1.0)


def test_nan_parciales_no_contaminan_el_rango():
    t = np.linspace(0, 1, 100)
    sel = np.zeros((2, 100), dtype=np.float32)
    sel[0, :10] = np.nan
    sel[1, :] = np.linspace(-5, 5, 100)
    _, _, vmin, vmax, _, _, _, _ = preparar_mapa_calor(t, sel)
    assert np.isfinite(vmin) and np.isfinite(vmax)
    assert vmin < vmax


def test_una_matriz_de_una_dimension_es_error_en_espanol():
    with pytest.raises(ValueError, match="trials, muestras"):
        preparar_mapa_calor(np.linspace(0, 1, 10), np.zeros(10, dtype=np.float32))


def test_devuelve_t_end_que_el_dibujo_necesita():
    """Regresion: al extraer el calculo, t_end se quedo sin devolver y
    _render_heatmap lo usa para fijar el eje horizontal."""
    t, sel = _datos(3, 500)
    resultado = preparar_mapa_calor(t, sel)
    assert len(resultado) == 8, "preparar_mapa_calor debe devolver 8 valores, t_end incluido"
    assert resultado[5] == pytest.approx(float(t[-1]))

"""R40: las medidas del segmento se calculan, y se piden confirmar, antes de modificar."""
import numpy as np
import pytest

from core.filters.artifacts import calcular_modificacion, medidas_del_segmento

FS = 1000.0
T = np.arange(0, 1.0, 1 / FS)


def _trials():
    base = np.zeros((T.size, 4))
    base[200:210, :] = 5.0           # el artefacto, entre 0,200 y 0,209 s
    base[205, :] = 9.0
    return base


def test_las_medidas_describen_el_segmento_elegido():
    m = medidas_del_segmento(T, _trials(), mode="blank", point_a=0.2, point_b=0.21)
    assert m["inicio_s"] == pytest.approx(0.2) and m["fin_s"] == pytest.approx(0.21)
    assert m["n_muestras"] == 11 and m["n_trials"] == 4
    assert m["y_max"] == 9.0 and m["x_en_max"] == pytest.approx(0.205)
    assert m["y_min"] == 0.0
    assert m["amplitud_pp"] == pytest.approx(9.0)


def test_calcular_las_medidas_no_modifica_los_datos():
    datos = _trials()
    copia = datos.copy()
    medidas_del_segmento(T, datos, mode="interpolate", point_a=0.2, point_b=0.21)
    assert np.array_equal(datos, copia)


def test_un_rango_fuera_del_trial_no_tiene_medidas():
    assert medidas_del_segmento(T, _trials(), mode="blank", point_a=5.0, point_b=6.0) is None


def test_cortar_desde_el_inicio_mide_de_cero_hasta_A():
    m = medidas_del_segmento(T, _trials(), mode="blank", point_a=0.1)
    assert m["inicio_s"] == pytest.approx(0.0) and m["n_muestras"] == 100


def test_el_orden_de_A_y_B_no_importa():
    a = medidas_del_segmento(T, _trials(), mode="interpolate", point_a=0.21, point_b=0.2)
    b = medidas_del_segmento(T, _trials(), mode="interpolate", point_a=0.2, point_b=0.21)
    assert a == b


def test_las_medidas_coinciden_con_lo_que_la_modificacion_toca():
    """El segmento medido es el mismo que se anula."""
    datos = _trials()
    m = medidas_del_segmento(T, datos, mode="blank", point_a=0.2, point_b=0.21)
    out = calcular_modificacion(T, datos, mode="blank", point_a=0.2, point_b=0.21)
    cambiadas = np.where(~np.isclose(out[:, 0], datos[:, 0]))[0]
    assert cambiadas.size and T[cambiadas[0]] >= m["inicio_s"] - 1e-9 and T[cambiadas[-1]] <= m["fin_s"] + 1e-9

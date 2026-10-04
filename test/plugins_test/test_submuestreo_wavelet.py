"""El submuestreo del wavelet (problema nº 18).

El problema original tenía dos partes y terminaron en sitios distintos:

  1. **El eje se corría** cuando la densidad pedida no dividía a la del archivo,
     porque el código seguía usando la pedida en lugar de la que de verdad
     quedaba. Era un bug nuestro —MATLAB usa `srate/srt` y nuestro propio
     `fft_average` también—, así que está **corregido** y aquí se verifica.

  2. **No se filtra antes de descartar muestras**, así que hay aliasing. MATLAB
     tiene el mismo defecto (`downsample` en 14 funciones, `decimate` en
     ninguna) y la referencia se generó con él dentro: filtrar corrige el
     aliasing pero aparta el resultado de la referencia —en el promedio, de 5 a
     371 filas discordantes—. Se decidió **no filtrar**, para coincidir con
     MATLAB. La última prueba de este archivo documenta ese aliasing para que
     quede como limitación conocida y no como olvido.

Las frecuencias se comprueban con tonos puros: si el escalograma pone el máximo
en otra parte, el error es medible.
"""
import numpy as np
import pytest

from core.filters.wavelet import compute_wavelet, tasa_efectiva

FS_ARCHIVO = 10000.0
CICLOS = 2.0


def tono(f_hz, dur=2.0, fs=FS_ARCHIVO):
    t = np.arange(int(fs * dur)) / fs
    return np.sin(2 * np.pi * f_hz * t)


def pico(sig, densidad, fmin, fmax):
    """Frecuencia donde el escalograma concentra más energía."""
    Z, _, freqs = compute_wavelet(sig, FS_ARCHIVO, densidad, fmin, fmax, CICLOS)
    return float(freqs[int(np.argmax(Z.mean(axis=1)))])


# --------------------------------------------------------------- tasa efectiva

@pytest.mark.parametrize("densidad,factor_esperado,tasa_esperada", [
    (1000.0, 10, 1000.0),      # divide exacto
    (2000.0, 5, 2000.0),       # divide exacto
    (2500.0, 4, 2500.0),       # divide exacto
    (3000.0, 3, 10000.0 / 3),  # no divide: 3333,33
    (4000.0, 2, 5000.0),       # no divide
    (7000.0, 1, 10000.0),      # no divide; el factor no puede bajar de 1
    (20000.0, 1, 10000.0),     # mayor que la del archivo
])
def test_tasa_efectiva(densidad, factor_esperado, tasa_esperada):
    tasa, factor = tasa_efectiva(FS_ARCHIVO, densidad)
    assert factor == factor_esperado
    assert tasa == pytest.approx(tasa_esperada)


def test_la_tasa_efectiva_es_la_del_archivo_dividida_por_el_factor():
    for densidad in (300.0, 777.0, 1000.0, 3000.0, 9999.0):
        tasa, factor = tasa_efectiva(FS_ARCHIVO, densidad)
        assert tasa == pytest.approx(FS_ARCHIVO / factor)


# ------------------------------------------- el eje ya no se corre (corregido)

@pytest.mark.parametrize("densidad", [1000.0, 2000.0, 2500.0, 3000.0, 4000.0, 7000.0])
def test_un_tono_cae_en_su_frecuencia_con_cualquier_densidad(densidad):
    """Regresión del nº 18. Antes del arreglo, un tono de 100 Hz caía en 89,1 Hz
    con densidad 3000 y en 69,1 Hz con 7000."""
    p = pico(tono(100.0), densidad, 20.0, 300.0)
    assert p == pytest.approx(100.0, abs=3.0), \
        f"con densidad {densidad:g} Hz el tono de 100 Hz cayo en {p:.1f} Hz"


def test_el_corrimiento_es_el_mismo_en_todo_el_eje():
    """Si quedara algun corrimiento, se veria crecer con la frecuencia."""
    for f in (50.0, 100.0, 200.0, 400.0):
        p = pico(tono(f), 3000.0, f * 0.5, f * 1.6)
        assert abs(p / f - 1) < 0.05, f"el tono de {f:g} Hz cayo en {p:.1f} Hz"


def test_las_densidades_que_dividen_no_cambiaron():
    """El arreglo debe ser inerte donde el factor ya era exacto, que es el caso
    de las pruebas contra MATLAB (10.000 -> 1.000, factor 10)."""
    tasa, factor = tasa_efectiva(FS_ARCHIVO, 1000.0)
    assert (tasa, factor) == (1000.0, 10)


# ------------------------------------------- el Nyquist se valida bien ahora

def test_rechaza_fmax_por_encima_del_nyquist_real():
    """Con 3.800 Hz el factor sale 3 y el Nyquist real es 1.666. Antes del
    arreglo se validaba contra 1.900 y dejaba pasar un fmax de 1.800."""
    tasa, _ = tasa_efectiva(FS_ARCHIVO, 3800.0)
    assert tasa == pytest.approx(10000.0 / 3)
    with pytest.raises(ValueError, match="densidad efectiva"):
        compute_wavelet(tono(100.0), FS_ARCHIVO, 3800.0, 1.0, 1800.0, CICLOS)


def test_acepta_fmax_justo_por_debajo_del_nyquist_real():
    Z, _, _ = compute_wavelet(tono(100.0), FS_ARCHIVO, 3800.0, 1.0, 1600.0, CICLOS)
    assert Z.shape[0] > 0


# ------------------------------------- el aliasing, como limitacion conocida

def test_el_aliasing_existe_y_es_el_mismo_que_en_matlab():
    """**Esta prueba documenta un defecto, no lo corrige.**

    Al submuestrear sin filtrar, un tono de 800 Hz no cabe a 1.000 Hz (Nyquist
    500) pero reaparece cerca de 200 Hz, donde no se distingue de uno real. Se
    decidió conservar este comportamiento porque es el de MATLAB, que es la
    referencia, y porque filtrar aparta el resultado de ella (en el promedio, de
    5 a 371 filas discordantes).

    Si algún día se decide corregirlo, esta prueba debe fallar: es la señal de
    que el filtro antialias entró. Detalle en el problema nº 18.
    """
    p = pico(tono(800.0), 1000.0, 20.0, 480.0)
    assert p == pytest.approx(200.0, abs=10.0), \
        (f"el alias de 800 Hz aparecio en {p:.1f} Hz y se esperaba cerca de 200. "
         f"Si esto cambio por haber anadido un filtro antialias, es intencional "
         f"y hay que actualizar el problema nº 18.")


def test_una_frecuencia_que_cabe_se_ubica_bien():
    """Contraste de la anterior: lo que sí está bajo el Nyquist no se mueve."""
    p = pico(tono(200.0), 1000.0, 20.0, 480.0)
    assert p == pytest.approx(200.0, abs=5.0)

"""Los cargadores no duplican los datos en memoria (problema nº 12).

El Escenario de Calidad 2 del SAD exige cargar «sin duplicación innecesaria de
datos». Medido, `load_abf` hacía crecer el working set al **doble** del tamaño de
los arreglos resultantes, y `load_edf` tenía el mismo patrón —peor en su camino
de remuestreo, donde los canales crudos seguían vivos mientras se construía la
matriz remuestreada—.

La causa no era la que parecía al leer el código. No era el `np.stack`: era que
**pyabf ya tiene el archivo entero en memoria** (`abf.data` y `abf.sweepX`) y
nosotros lo copiábamos otra vez. La corrección es quedarse con esos arreglos en
lugar de copiarlos, ya que el objeto `abf` muere al salir del cargador.

`load_edf` no tenía ninguna prueba y no hay archivos EDF en el proyecto, así que
aquí se generan sintéticos con `pyedflib` y se comparan contra la lógica
original, usada como oráculo.
"""
import io
import sys
from pathlib import Path

import numpy as np
import pytest

from core.services.fileio_service import FileIOService

REPO = Path(__file__).resolve().parents[2]
ABF_PATH = REPO / "test" / "data" / "17308005.abf"

pyedflib = pytest.importorskip("pyedflib")


def _silencio(fn, *a, **k):
    """Los cargadores imprimen bastante; no interesa en las pruebas."""
    buf, orig = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        return fn(*a, **k)
    finally:
        sys.stdout = orig


# ------------------------------------------------------------------- ABF

@pytest.mark.skipif(not ABF_PATH.exists(), reason="no se encontro el archivo ABF de prueba")
def test_abf_no_copia_las_senales():
    """Las señales devueltas deben ser los mismos arreglos que trae pyabf, no copias."""
    import pyabf

    sd = _silencio(FileIOService().load_abf, str(ABF_PATH))
    abf = _silencio(pyabf.ABF, str(ABF_PATH))

    assert sd.signals.shape == abf.data.shape
    assert sd.signals.dtype == abf.data.dtype
    assert np.array_equal(sd.signals, abf.data), \
        "las senales deben coincidir con abf.data"


@pytest.mark.skipif(not ABF_PATH.exists(), reason="no se encontro el archivo ABF de prueba")
def test_abf_el_resultado_sigue_siendo_el_esperado():
    """Regresión: el cambio de memoria no debe alterar ni los datos ni los metadatos."""
    sd = _silencio(FileIOService().load_abf, str(ABF_PATH))

    assert sd.signals.shape == (2, 1800000)
    assert sd.signals.dtype == np.float32
    assert sd.sampling_rate == 10000.0
    assert list(sd.channel_names) == ["CA1", "IN 7"]
    assert sd.time.shape == (1800000,)
    assert sd.time[0] == pytest.approx(0.0)
    assert sd.time[-1] == pytest.approx(179.9999, abs=1e-4)
    assert np.all(np.isfinite(sd.signals))


@pytest.mark.skipif(not ABF_PATH.exists(), reason="no se encontro el archivo ABF de prueba")
def test_abf_los_arreglos_son_escribibles_y_propios():
    """Tras cargar, el objeto `abf` ya no existe: los arreglos deben ser usables
    y modificables sin tocar nada ajeno."""
    sd = _silencio(FileIOService().load_abf, str(ABF_PATH))
    assert sd.signals.flags.writeable
    primero = float(sd.signals[0, 0])
    sd.signals[0, 0] = primero + 1.0
    assert float(sd.signals[0, 0]) == pytest.approx(primero + 1.0)


# ------------------------------------------------------------------- EDF

def _generar_edf(ruta, canales):
    """canales: lista de (nombre, unidad, fs, duracion_s)."""
    w = pyedflib.EdfWriter(str(ruta), len(canales), file_type=pyedflib.FILETYPE_EDFPLUS)
    cabeceras, datos = [], []
    for i, (nombre, unidad, fs, dur) in enumerate(canales):
        n = int(fs * dur)
        t = np.arange(n) / fs
        y = 100.0 * np.sin(2 * np.pi * (5 + 3 * i) * t) + 10.0 * np.sin(2 * np.pi * 50 * t)
        cabeceras.append({
            "label": nombre, "dimension": unidad, "sample_frequency": fs,
            "physical_max": 500.0, "physical_min": -500.0,
            "digital_max": 32767, "digital_min": -32768,
            "transducer": "", "prefilter": "",
        })
        datos.append(y)
    w.setSignalHeaders(cabeceras)
    w.writeSamples(datos)
    w.close()


def _oraculo_edf(file_path):
    """La lógica de load_edf anterior al cambio, copiada literalmente."""
    edf = pyedflib.EdfReader(str(file_path))
    try:
        C = edf.signals_in_file
        signals_raw, nombres, unidades, fs_list, duraciones = [], [], [], [], []
        for i in range(C):
            sig = edf.readSignal(i)
            fs_i = float(edf.samplefrequency(i))
            signals_raw.append(np.asarray(sig, dtype=np.float64))
            nombres.append(str(edf.getLabel(i).strip() or f"ch{i}"))
            unidades.append(str(edf.getPhysicalDimension(i).strip() or "uV"))
            fs_list.append(fs_i)
            duraciones.append(len(sig) / fs_i)

        same_fs = all(abs(f - fs_list[0]) < 1e-9 for f in fs_list)
        same_len = len({len(s) for s in signals_raw}) == 1

        if same_fs and same_len:
            fs = fs_list[0]
            N = len(signals_raw[0])
            tiempo = np.arange(N, dtype=np.float64) / fs
            senales = np.stack(signals_raw, axis=0)
        else:
            fs = float(min(fs_list))
            N = int(np.floor(float(min(duraciones)) * fs))
            tiempo = np.arange(N, dtype=np.float64) / fs
            remuestreadas = []
            for sig, fs_i in zip(signals_raw, fs_list):
                t_i = np.arange(sig.shape[0], dtype=np.float64) / fs_i
                remuestreadas.append(np.interp(tiempo, t_i, sig).astype(np.float64))
            senales = np.stack(remuestreadas, axis=0)
        return senales, tiempo, nombres, unidades, fs
    finally:
        edf.close()


CASOS_EDF = {
    "uniforme": [("Fp1", "uV", 256, 10.0), ("Fp2", "uV", 256, 10.0), ("Cz", "uV", 256, 10.0)],
    "fs_distintas": [("Fp1", "uV", 256, 10.0), ("EOG", "uV", 128, 10.0), ("ECG", "mV", 512, 8.0)],
    "un_canal": [("Cz", "uV", 200, 5.0)],
    "dos_canales_fs_iguales_duracion_distinta": [("A", "uV", 256, 10.0), ("B", "uV", 256, 6.0)],
}


@pytest.mark.parametrize("caso", list(CASOS_EDF))
def test_edf_da_lo_mismo_que_la_version_anterior(tmp_path, caso):
    ruta = tmp_path / f"{caso}.edf"
    _generar_edf(ruta, CASOS_EDF[caso])

    e_sig, e_t, e_nom, e_uni, e_fs = _oraculo_edf(ruta)
    sd = _silencio(FileIOService().load_edf, str(ruta))

    assert np.array_equal(sd.signals, e_sig), "las senales no coinciden con la version anterior"
    assert np.array_equal(sd.time, e_t), "el eje de tiempo no coincide"
    assert list(sd.channel_names) == e_nom
    assert list(sd.units) == e_uni
    assert sd.sampling_rate == e_fs


def test_edf_uniforme_arma_la_matriz_esperada(tmp_path):
    ruta = tmp_path / "uniforme.edf"
    _generar_edf(ruta, CASOS_EDF["uniforme"])
    sd = _silencio(FileIOService().load_edf, str(ruta))

    assert sd.signals.shape == (3, 2560)
    assert sd.signals.dtype == np.float64
    assert sd.sampling_rate == 256.0
    assert sd.metadata["uniform"] is True


def test_edf_con_fs_distintas_remuestrea_a_la_menor(tmp_path):
    ruta = tmp_path / "mixto.edf"
    _generar_edf(ruta, CASOS_EDF["fs_distintas"])
    sd = _silencio(FileIOService().load_edf, str(ruta))

    # fs comun = la menor (128); duracion comun = la menor (8 s) -> 1024 muestras
    assert sd.sampling_rate == 128.0
    assert sd.signals.shape == (3, 1024)
    assert sd.metadata["uniform"] is False
    assert np.all(np.isfinite(sd.signals))


def test_edf_no_deja_el_archivo_abierto(tmp_path):
    """El cargador cierra el EdfReader en su `finally`; si no, en Windows el
    archivo quedaria bloqueado y no se podria borrar."""
    ruta = tmp_path / "cierre.edf"
    _generar_edf(ruta, CASOS_EDF["un_canal"])
    _silencio(FileIOService().load_edf, str(ruta))
    ruta.unlink()          # falla con PermissionError si quedo abierto
    assert not ruta.exists()

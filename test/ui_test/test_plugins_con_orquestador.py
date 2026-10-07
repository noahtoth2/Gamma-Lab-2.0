"""Comportamiento de interfaz de los plugins que usan el orquestador (Fases 3 y 4).

Cada archivo de escenarios corre en un proceso aparte: necesita una QApplication
con widgets, y el resto de la suite crea QCoreApplication, que no se puede
reemplazar dentro del mismo proceso. Además, si Qt abortara el proceso, falla
esta prueba y no toda la sesión de pytest.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[1]
ABF_PATH = REPO / "test" / "data" / "17308005.abf"

pytestmark = pytest.mark.skipif(not ABF_PATH.exists(), reason="no se encontro el archivo ABF de prueba")


def correr_escenarios(nombre):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_FORCE_STDERR_LOGGING="1",
               PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(AQUI / nombre)], cwd=REPO, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=600)
    casos = [linea.split("|", 3) for linea in r.stdout.splitlines() if linea.startswith("CASO|")]
    assert "QThread: Destroyed" not in r.stderr, "Qt destruyo un hilo que seguia corriendo"
    assert r.returncode == 0, f"el proceso de escenarios termino con {r.returncode}:\n{r.stderr[-1500:]}"
    assert casos, f"no se ejecuto ningun escenario:\n{r.stderr[-1500:]}"
    fallas = [f"{c[2]} ({c[3]})" for c in casos if c[1] != "OK"]
    assert not fallas, "fallaron estos escenarios:\n- " + "\n- ".join(fallas)
    return len(casos)


def test_modulation_index_en_la_interfaz():
    assert correr_escenarios("escenarios_modulation_index.py") >= 30


def test_pac_en_la_interfaz():
    assert correr_escenarios("escenarios_pac.py") >= 28


def test_open_signal_en_la_interfaz():
    assert correr_escenarios("escenarios_open_signal.py") >= 11


def test_barra_de_progreso():
    assert correr_escenarios("escenarios_progreso.py") >= 15


def test_wavelet_en_la_interfaz():
    assert correr_escenarios("escenarios_wavelet.py") >= 17


def test_wavelet_average_en_la_interfaz():
    assert correr_escenarios("escenarios_wavelet_average.py") >= 15


def test_artifact_remove_en_la_interfaz():
    assert correr_escenarios("escenarios_artifact_remove.py") >= 22

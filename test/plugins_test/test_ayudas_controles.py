"""R42: todos los controles de cada módulo muestran una descripción emergente."""
import glob
import importlib
import inspect
import os

import pytest
from PyQt5 import QtWidgets

from core.utils.ayudas import AYUDAS, completar_ayudas, sin_ayuda

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")


def _interfaces():
    """(nombre, clase) de cada interfaz de módulo que se arma con `setupUi(widget)`."""
    salida = []
    for ruta in sorted(glob.glob(os.path.join(RAIZ, "plugins", "**", "*_ui.py"), recursive=True)):
        rel = os.path.relpath(ruta, RAIZ)[:-3].replace(os.sep, ".")
        try:
            mod = importlib.import_module(rel)
        except ImportError:        # la ayuda necesita QtWebEngine, que pide inicializarse antes de QApplication
            continue
        for nombre, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ == mod.__name__ and hasattr(cls, "setupUi"):
                salida.append((f"{rel.split('.')[-1]}:{nombre}", cls))
    return salida


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize("nombre,cls", _interfaces(), ids=lambda v: v if isinstance(v, str) else "")
def test_ningun_control_queda_sin_descripcion(app, nombre, cls):
    if issubclass(cls, QtWidgets.QWidget):      # las interfaces que son su propio widget
        widget = cls()
        widget.setupUi()
    else:
        widget = QtWidgets.QWidget()
        cls().setupUi(widget)
    completar_ayudas(widget)
    pendientes = [c.objectName() or type(c).__name__ for c in sin_ayuda(widget)]
    assert pendientes == [], f"{nombre}: controles sin descripción {pendientes}"


def test_no_se_pisa_una_descripcion_propia(app):
    caja = QtWidgets.QSpinBox()
    caja.setObjectName("npersegSpinBox")
    caja.setToolTip("la del módulo")
    padre = QtWidgets.QWidget()
    caja.setParent(padre)
    completar_ayudas(padre)
    assert caja.toolTip() == "la del módulo"


def test_los_controles_habituales_tienen_texto_propio(app):
    for nombre in ("npersegSpinBox", "lowFrequencySpinBox", "headerGenerateButton", "windowComboBox"):
        assert AYUDAS[nombre].strip()

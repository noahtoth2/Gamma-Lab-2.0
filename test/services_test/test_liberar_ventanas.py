"""R45: al salir de un módulo pesado se finaliza su ventana OpenGL, sin tocar el resto."""
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from app.view.main_window import MainWindow
from core.plugins.loader import discover
from core.plugins.meta import PluginMeta
from core.utils.vtk_ventanas import liberar_ventanas

RAIZ = Path(__file__).resolve().parents[2] / "plugins"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Ventana:
    def __init__(self):
        self.finalizada = 0

    def Finalize(self):
        self.finalizada += 1


def _modulo(n_vtk=1):
    """Un widget con `n_vtk` widgets VTK (su ventana es un espía) y un QLabel."""
    raiz = QWidget()
    layout = QVBoxLayout(raiz)
    ventanas = []
    for _ in range(n_vtk):
        v = Ventana()
        w = QVTKRenderWindowInteractor(raiz)
        w.GetRenderWindow = lambda v=v: v
        layout.addWidget(w)
        ventanas.append(v)
    layout.addWidget(QLabel("no vtk"))
    return raiz, ventanas


def test_finaliza_cada_ventana_vtk_del_modulo(qapp):
    raiz, ventanas = _modulo(2)
    assert liberar_ventanas(raiz) == 2
    assert [v.finalizada for v in ventanas] == [1, 1]


def test_un_modulo_sin_ventanas_vtk_no_hace_nada(qapp):
    assert liberar_ventanas(QWidget()) == 0


def _ventana_principal(raiz, libera):
    meta = SimpleNamespace(free_graphics=libera, id="x")
    stub = SimpleNamespace(
        active_plugin_widget=raiz,
        active_plugin=SimpleNamespace(meta=meta, stop=lambda: None),
        _cancel_tasks_of=lambda p: None,
        alerts=MagicMock(),
        _update_background_logo_visibility=lambda: None,
    )
    stub._liberar_graficos = partial(MainWindow._liberar_graficos, stub)
    return stub


def test_al_salir_se_libera_despues_de_mostrar_el_siguiente(qapp):
    raiz, (v,) = _modulo()
    stub = _ventana_principal(raiz, libera=True)
    MainWindow.clear_plugin_area(stub)
    assert v.finalizada == 0, "no se libera dentro del cambio de modulo, sino despues"
    qapp.processEvents()
    assert v.finalizada == 1


def test_un_plugin_que_lo_excluye_conserva_su_ventana(qapp):
    raiz, (v,) = _modulo()
    MainWindow.clear_plugin_area(_ventana_principal(raiz, libera=False))
    qapp.processEvents()
    assert v.finalizada == 0


def test_si_el_usuario_vuelve_antes_no_se_libera(qapp):
    raiz, (v,) = _modulo()
    stub = _ventana_principal(raiz, libera=True)
    MainWindow.clear_plugin_area(stub)
    stub.active_plugin_widget = raiz        # volvio al modulo antes de que corriera
    qapp.processEvents()
    assert v.finalizada == 0


def test_por_defecto_se_libera_y_se_excluyen_los_que_tardan_al_volver():
    metas = {m.name: m for m, _ in discover(RAIZ)}
    excluidos = {n for n, m in metas.items() if not m.free_graphics}
    assert excluidos == {"PSD Average", "Average", "Event Related Potential", "Wavelet", "Wavelet Average",
                         "PAC", "Trials", "Filter", "Remove Artifact", "Open Signal"},         "se excluyen los modulos cuya vuelta, 3 veces mas lenta, pasa de 500 ms (R50)"
    assert PluginMeta(id="x", name="x", category="c", subcategory="s", version="1", icon="i",
                      logic_class="C").free_graphics is True
    assert PluginMeta(id="x", name="x", category="c", subcategory="s", version="1", icon="i",
                      logic_class="C", free_graphics=False).free_graphics is False

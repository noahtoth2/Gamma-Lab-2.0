"""R58: los observadores de VTK se retiran al salir del módulo y se reponen al volver."""
import pytest
import vtk
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from core.utils.vtk_observers import (observar, retirar_observadores, reponer_observadores,
                                      contar_observadores, retirar_de, reponer_en)


@pytest.fixture
def entorno():
    app = QApplication.instance() or QApplication([])
    cont = QWidget()
    lay = QVBoxLayout(cont)
    w = QVTKRenderWindowInteractor(cont)
    lay.addWidget(w)
    yield cont, w
    w.Finalize()


def test_retirar_deja_cero_observadores_y_reponer_los_devuelve(entorno):
    cont, w = entorno
    llamadas = []
    observar(w, "LeftButtonPressEvent", lambda o, e: llamadas.append(1))
    observar(w, "MouseMoveEvent", lambda o, e: llamadas.append(2), -1.0)
    assert contar_observadores(w) == 2
    assert retirar_observadores(w) == 2
    assert contar_observadores(w) == 0
    iren = w.GetRenderWindow().GetInteractor()
    iren.InvokeEvent("LeftButtonPressEvent")
    assert llamadas == [], "retirado: el callback ya no se invoca"
    assert reponer_observadores(w) == 2
    assert contar_observadores(w) == 2
    iren.InvokeEvent("LeftButtonPressEvent")
    assert llamadas == [1]


def test_es_idempotente(entorno):
    _, w = entorno
    observar(w, "MouseMoveEvent", lambda o, e: None)
    assert retirar_observadores(w) == 1
    assert retirar_observadores(w) == 0
    assert reponer_observadores(w) == 1
    assert reponer_observadores(w) == 0
    assert contar_observadores(w) == 1


def test_un_observador_nuevo_con_el_modulo_fuera_no_se_ata(entorno):
    _, w = entorno
    retirar_observadores(w)
    observar(w, "MouseMoveEvent", lambda o, e: None)
    assert contar_observadores(w) == 0
    reponer_observadores(w)
    assert contar_observadores(w) == 1


def test_retirar_de_y_reponer_en_recorren_el_contenedor(entorno):
    cont, w = entorno
    observar(w, "MouseMoveEvent", lambda o, e: None)
    observar(w, "LeftButtonPressEvent", lambda o, e: None)
    assert retirar_de(cont) == 2 and contar_observadores(w) == 0
    assert reponer_en(cont) == 2 and contar_observadores(w) == 2


def test_el_menu_contextual_y_la_lectura_del_cursor_usan_el_registro(entorno):
    from core.utils.vtk_context_menu import VTKContextMenu
    cont, w = entorno
    menu = VTKContextMenu(chart=None, vtk_widget=w, plugin_name="t", measurements_enabled=True,
                          measure_scope={"view_id": "t", "graph_id": "t", "trial_id": None,
                                         "channel_name": None, "plugin": "t", "domain": "time"},
                          parent=cont)
    antes = contar_observadores(w)
    assert antes >= 3
    retirar_de(cont)
    assert contar_observadores(w) == 0
    reponer_en(cont)
    assert contar_observadores(w) == antes

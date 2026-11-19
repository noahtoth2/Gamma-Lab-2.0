"""File > New project en esta ventana: si ya hay trabajo cargado, el proyecto nuevo se añade
al Explorer debajo de los abiertos y el activo no cambia."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from app.view import main_window as mw
from app.view.main_window import MainWindow
from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore


def _senal():
    t = np.arange(100) / 100.0
    return SignalDataset(name="s.abf", format="abf", source_path="C:/s.abf", sampling_rate=100.0, time=t,
                         signals=np.vstack([t]), channel_names=["a"], units=["mV"])


def _ventana(store, glab_activo=None, abiertos=()):
    project_service = SimpleNamespace(
        glab_path=glab_activo, is_open=glab_activo is not None, dirty=False)
    win = SimpleNamespace(
        kernel=SimpleNamespace(get_service=lambda nombre: store if nombre == "DataStore" else None),
        project_service=project_service,
        alerts=MagicMock(),
        _proyectos_abiertos=[Path(p) for p in abiertos],
        _refrescar_explorer=MagicMock(),
        _abrir_proyecto_creado=MagicMock(),
        _confirm_discard_unsaved_changes=MagicMock(return_value=True),
        _proyecto_ocupado=lambda: False,
        _ubicacion_por_defecto=lambda: "C:/",
        statusBar=lambda: MagicMock(),
    )
    for nombre in ("_hay_trabajo_cargado", "_agregar_al_explorer", "_indice_proyecto_abierto"):
        setattr(win, nombre, getattr(MainWindow, nombre).__get__(win))
    return win


def _crear(monkeypatch, win, tmp_path, ventana_nueva=False):
    monkeypatch.setattr(mw.DialogoProyectoNuevo, "pedir",
                        staticmethod(lambda *a, **k: (tmp_path / "B", "B", ventana_nueva)))
    MainWindow.on_new_project_clicked(win)
    return tmp_path / "B" / "B.glab"


def test_con_proyecto_abierto_el_nuevo_va_debajo_y_el_activo_no_cambia(monkeypatch, tmp_path):
    activo = tmp_path / "A" / "A.glab"
    store = DataStore()
    store.set_active_signal(store.add_signal(_senal(), "s.abf"))
    win = _ventana(store, glab_activo=activo, abiertos=[activo])

    nuevo = _crear(monkeypatch, win, tmp_path)

    assert nuevo.is_file()
    assert win._proyectos_abiertos == [activo, nuevo]
    assert win.project_service.glab_path == activo
    win._abrir_proyecto_creado.assert_not_called()
    win._confirm_discard_unsaved_changes.assert_not_called()
    win._refrescar_explorer.assert_called_once()


def test_con_senal_sin_guardar_no_se_descarga(monkeypatch, tmp_path):
    store = DataStore()
    store.set_active_signal(store.add_signal(_senal(), "s.abf"))
    win = _ventana(store)

    nuevo = _crear(monkeypatch, win, tmp_path)

    assert win._proyectos_abiertos == [nuevo]
    assert store.get_active_signal() is not None
    win._abrir_proyecto_creado.assert_not_called()


def test_sin_nada_cargado_el_nuevo_se_abre(monkeypatch, tmp_path):
    win = _ventana(DataStore())

    nuevo = _crear(monkeypatch, win, tmp_path)

    win._abrir_proyecto_creado.assert_called_once_with(nuevo, False)


def test_en_ventana_nueva_se_abre_alli(monkeypatch, tmp_path):
    activo = tmp_path / "A" / "A.glab"
    store = DataStore()
    store.set_active_signal(store.add_signal(_senal(), "s.abf"))
    win = _ventana(store, glab_activo=activo, abiertos=[activo])

    nuevo = _crear(monkeypatch, win, tmp_path, ventana_nueva=True)

    win._abrir_proyecto_creado.assert_called_once_with(nuevo, True)
    assert win._proyectos_abiertos == [activo]

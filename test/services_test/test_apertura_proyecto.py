"""R04: abrir un proyecto lee el archivo fuera del hilo de la interfaz; guardar no recopia la señal."""
import json
import shutil
from pathlib import Path

import numpy as np

from core.kernel import Kernel
from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore
from core.services.project_service import ProjectService


class FileIOFalso:
    def __init__(self):
        self.lecturas = 0

    def load_abf(self, ruta):
        self.lecturas += 1
        t = np.arange(100) / 100.0
        return SignalDataset(name=Path(ruta).name, format="abf", source_path=str(ruta), sampling_rate=100.0,
                             time=t, signals=np.vstack([t, t]), channel_names=["a", "b"], units=["mV", "mV"])


def _proyecto(tmp_path):
    (tmp_path / "s.abf").write_bytes(b"x" * 64)
    (tmp_path / "p.glab").write_text(json.dumps({
        "schema_version": 1, "project_name": "p",
        "signal": {"filename": "s.abf", "format": "abf", "name": "s.abf", "sampling_rate": 100.0},
        "measurements": [], "trials": [], "analysis": {}}), encoding="utf-8")
    kernel, store, io = Kernel(), DataStore(), FileIOFalso()
    kernel.register_service("DataStore", store)
    kernel.register_service("FileIO", io)
    return ProjectService(kernel), store, io, tmp_path / "p.glab"


def test_preparar_apertura_lee_sin_tocar_el_datastore(tmp_path):
    ps, store, io, glab = _proyecto(tmp_path)
    manifest, ds = ps.preparar_apertura(str(glab))
    assert ds is not None and manifest["project_name"] == "p" and io.lecturas == 1
    assert store.get_active_signal() is None, "registrar la señal es cosa del hilo de la interfaz"
    assert not ps.is_open


def test_open_con_lo_preparado_registra_la_senal_sin_volver_a_leer(tmp_path):
    ps, store, io, glab = _proyecto(tmp_path)
    prep = ps.preparar_apertura(str(glab))
    ps.open(str(glab), preparado=prep)
    assert io.lecturas == 1
    assert store.get_active_signal() is prep[1]
    assert ps.is_open and ps.project_name == "p" and not ps.dirty


def test_open_sin_preparar_sigue_funcionando(tmp_path):
    ps, store, io, glab = _proyecto(tmp_path)
    ps.open(str(glab))
    assert store.get_active_signal() is not None and io.lecturas == 1


def test_si_falta_el_archivo_de_la_senal_se_abre_sin_senal(tmp_path):
    ps, store, io, glab = _proyecto(tmp_path)
    (tmp_path / "s.abf").unlink()
    manifest, ds = ps.preparar_apertura(str(glab))
    assert ds is None
    ps.open(str(glab), preparado=(manifest, ds))
    assert store.get_active_signal() is None and ps.is_open


def test_guardar_dos_veces_no_vuelve_a_copiar_la_senal(tmp_path, monkeypatch):
    origen = tmp_path / "origen"
    destino = tmp_path / "proyecto"
    origen.mkdir(), destino.mkdir()
    (origen / "s.abf").write_bytes(b"x" * 1000)
    kernel, store = Kernel(), DataStore()
    kernel.register_service("DataStore", store)
    ps = ProjectService(kernel)
    ds = FileIOFalso().load_abf(str(origen / "s.abf"))
    ps.project_dir = destino

    copias = []
    real = shutil.copy2
    monkeypatch.setattr(shutil, "copy2", lambda a, b: (copias.append(1), real(a, b))[1])
    assert ps._copy_signal_into_project(ds) == "s.abf"
    assert ps._copy_signal_into_project(ds) == "s.abf"
    assert len(copias) == 1, "la segunda vez la copia ya está al día"

    (origen / "s.abf").write_bytes(b"y" * 2000)      # la señal cambió
    ps._copy_signal_into_project(ds)
    assert len(copias) == 2

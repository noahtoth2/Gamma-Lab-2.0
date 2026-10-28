"""R04: guardar un proyecto en pasos; la copia de la señal sale del hilo de la interfaz."""
import json
from pathlib import Path

import numpy as np
import pytest
from PyQt5.QtWidgets import QFileDialog

from core.kernel import Kernel
from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore
from core.services.project_service import ProjectService


class Ctx:
    def __init__(self, cancelar_en=None):
        self.cancelled = False
        self.avances = []
        self._en = cancelar_en

    def progress(self, pct, msg=""):
        self.avances.append(pct)
        if self._en is not None and pct >= self._en:
            self.cancelled = True


def _entorno(tmp_path, tam=3000):
    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "s.abf").write_bytes(bytes(range(256)) * (tam // 256 + 1))
    t = np.arange(10) / 10.0
    ds = SignalDataset(name="s.abf", format="abf", source_path=str(origen / "s.abf"), sampling_rate=10.0,
                       time=t, signals=np.vstack([t]), channel_names=["a"], units=["mV"])
    kernel, store = Kernel(), DataStore()
    kernel.register_service("DataStore", store)
    store.set_active_signal(store.add_signal(ds))
    destino = tmp_path / "proyecto"
    destino.mkdir()
    return ProjectService(kernel), ds, origen / "s.abf", destino


@pytest.fixture
def carpeta(monkeypatch):
    elegida = {}
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: elegida.get("ruta", "")))
    return elegida


def test_iniciar_guardado_pide_copiar_la_senal_la_primera_vez(tmp_path, carpeta):
    ps, ds, src, destino = _entorno(tmp_path)
    carpeta["ruta"] = str(destino)
    job = ps.iniciar_guardado(None, como=True)
    assert job.copia == (src, destino / "s.abf")
    assert not (destino / "s.abf").exists(), "iniciar solo decide: no copia ni escribe nada"
    assert not (destino / "s.glab").exists() and not list(destino.glob("*.glab"))


def test_si_el_usuario_cancela_el_selector_no_hay_trabajo(tmp_path, carpeta):
    ps, *_ = _entorno(tmp_path)
    carpeta["ruta"] = ""
    assert ps.iniciar_guardado(None, como=True) is None
    assert not ps.is_open


def test_copiar_senal_copia_por_bloques_con_progreso_y_conserva_fecha(tmp_path):
    ps, ds, src, destino = _entorno(tmp_path, tam=20_000_000)
    ctx = Ctx()
    assert ps.copiar_senal(src, destino / "s.abf", ctx) is True
    assert (destino / "s.abf").read_bytes() == src.read_bytes()
    assert int((destino / "s.abf").stat().st_mtime) == int(src.stat().st_mtime)
    assert not list(destino.glob("*.part"))
    assert len(ctx.avances) >= 3 and ctx.avances[-1] == 100 and ctx.avances == sorted(ctx.avances)


def test_cancelar_a_mitad_no_deja_un_archivo_roto(tmp_path):
    ps, ds, src, destino = _entorno(tmp_path, tam=40_000_000)
    ctx = Ctx(cancelar_en=30)
    assert ps.copiar_senal(src, destino / "s.abf", ctx) is False
    assert not (destino / "s.abf").exists()
    assert not list(destino.glob("*.part"))


def test_el_manifiesto_se_escribe_solo_al_completar(tmp_path, carpeta):
    ps, ds, src, destino = _entorno(tmp_path)
    carpeta["ruta"] = str(destino)
    job = ps.iniciar_guardado(None, como=True)
    ps.copiar_senal(*job.copia)
    assert not list(destino.glob("*.glab"))
    glab = ps.completar_guardado(job)
    manifiesto = json.loads(Path(glab).read_text(encoding="utf-8"))
    assert manifiesto["signal"]["filename"] == "s.abf"
    assert ps.is_open and not ps.dirty


def test_un_segundo_guardado_ya_no_pide_copia(tmp_path, carpeta):
    ps, ds, src, destino = _entorno(tmp_path)
    carpeta["ruta"] = str(destino)
    ps.completar_guardado(_con_copia(ps, ps.iniciar_guardado(None, como=True)))
    assert ps.iniciar_guardado(None, como=False).copia is None


def _con_copia(ps, job):
    ps.copiar_senal(*job.copia)
    return job


def test_revertir_deja_el_proyecto_donde_estaba(tmp_path, carpeta):
    ps, ds, src, destino = _entorno(tmp_path)
    carpeta["ruta"] = str(destino)
    job = ps.iniciar_guardado(None, como=True)
    assert ps.project_dir == destino
    ps.revertir_guardado(job)
    assert ps.project_dir is None and ps.glab_path is None and not ps.is_open


def test_save_y_save_as_siguen_funcionando_de_forma_sincrona(tmp_path, carpeta):
    ps, ds, src, destino = _entorno(tmp_path)
    carpeta["ruta"] = str(destino)
    glab = ps.save_as(None)
    assert Path(glab).exists() and (destino / "s.abf").read_bytes() == src.read_bytes()
    assert ps.save(None) == glab

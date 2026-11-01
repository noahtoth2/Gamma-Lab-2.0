"""R39: el programa instalado guarda sus ajustes en la carpeta del usuario y abre el .glab que recibe."""
import json
import sys
from types import SimpleNamespace

from app.view.main_window import MainWindow
import core.services.settings_service as settings_service
from core.services.settings_service import SettingsService
from core.utils.rutas import asegurar_salida_estandar, carpeta_de_datos, ruta_de_proyecto


def test_ruta_de_proyecto_encuentra_el_glab_entre_los_argumentos(tmp_path):
    glab = tmp_path / "Mi Proyecto.GLAB"
    glab.write_text("{}", encoding="utf-8")
    assert ruta_de_proyecto([str(glab)]) == str(glab)
    assert ruta_de_proyecto(["--algo", str(glab)]) == str(glab)


def test_ruta_de_proyecto_ignora_lo_que_no_es_un_glab_existente(tmp_path):
    otro = tmp_path / "datos.abf"
    otro.write_text("x", encoding="utf-8")
    assert ruta_de_proyecto([]) is None
    assert ruta_de_proyecto([str(otro)]) is None
    assert ruta_de_proyecto([str(tmp_path / "no_existe.glab")]) is None


def test_la_carpeta_de_datos_cuelga_de_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    ruta = carpeta_de_datos()
    assert ruta == str(tmp_path / "GammaLab") and (tmp_path / "GammaLab").is_dir()


def _sin_archivo_anterior(monkeypatch, tmp_path):
    """Que el SettingsService no encuentre el gamma_lab_settings.json que hay en la raíz del repositorio."""
    (tmp_path / "codigo" / "core" / "services").mkdir(parents=True)
    monkeypatch.setattr(settings_service, "__file__", str(tmp_path / "codigo" / "core" / "services" / "s.py"))


def test_los_ajustes_se_guardan_en_la_carpeta_del_usuario(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    _sin_archivo_anterior(monkeypatch, tmp_path)
    SettingsService().set("last_project_dir", "C:/datos")
    guardado = tmp_path / "GammaLab" / "gamma_lab_settings.json"
    assert json.loads(guardado.read_text(encoding="utf-8")) == {"last_project_dir": "C:/datos"}
    assert SettingsService().get("last_project_dir") == "C:/datos"


def test_el_archivo_de_una_version_anterior_se_copia_una_vez(tmp_path, monkeypatch):
    codigo = tmp_path / "codigo"
    (codigo / "core" / "services").mkdir(parents=True)
    (codigo / "gamma_lab_settings.json").write_text('{"last_open_dir": "D:/senales"}', encoding="utf-8")
    monkeypatch.setattr(settings_service, "__file__", str(codigo / "core" / "services" / "settings_service.py"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

    assert SettingsService().get("last_open_dir") == "D:/senales"

    (codigo / "gamma_lab_settings.json").write_text('{"last_open_dir": "otro"}', encoding="utf-8")
    SettingsService().set("x", 1)
    assert SettingsService().get("last_open_dir") == "D:/senales", "no se vuelve a copiar encima"


def test_abrir_desde_ruta_recuerda_la_carpeta_y_abre_el_proyecto(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    _sin_archivo_anterior(monkeypatch, tmp_path)
    abiertos = []
    ajustes = SettingsService()
    stub = SimpleNamespace(_abrir_proyecto=abiertos.append,
                           kernel=SimpleNamespace(get_service=lambda clave: ajustes if clave == "Settings" else None))
    MainWindow.abrir_proyecto_desde_ruta(stub, str(tmp_path / "datos" / "p.glab"))
    assert abiertos == [str(tmp_path / "datos" / "p.glab")]
    assert ajustes.get("last_project_dir") == str(tmp_path / "datos")


def test_sin_consola_la_salida_va_a_un_registro_y_flush_no_falla(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    ruta = asegurar_salida_estandar()
    print("hola desde un programa sin consola")
    sys.stdout.flush()
    sys.stdout.close()

    assert ruta == str(tmp_path / "GammaLab" / "gamma_lab.log")
    assert "hola desde un programa sin consola" in (tmp_path / "GammaLab" / "gamma_lab.log").read_text(encoding="utf-8")


def test_con_consola_no_se_toca_la_salida(monkeypatch):
    antes = (sys.stdout, sys.stderr)
    assert asegurar_salida_estandar() is None
    assert (sys.stdout, sys.stderr) == antes

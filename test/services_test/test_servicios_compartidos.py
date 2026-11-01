"""R69: los servicios de ajustes, exportación y medición son únicos y los registra el núcleo."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.kernel import Kernel
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.services.compartidos import registrar_servicios_compartidos
from core.services.data_store import DataStore
from core.services.export_service import Exportador, ExportService
from core.services.measurement_service import MeasurementService, SesionDeMedicion
from core.services.settings_service import SettingsService

RAIZ = Path(__file__).resolve().parents[2]
SERVICIOS = {"SettingsService", "ExportService", "MeasurementService"}
UNICO_LUGAR = Path("core/services/compartidos.py")


def _construcciones():
    """Archivos del programa (no de las pruebas) que construyen alguno de los tres servicios."""
    hallados = []
    archivos = [RAIZ / "main.py"] + [p for c in ("app", "core", "plugins") for p in (RAIZ / c).rglob("*.py")]
    for ruta in archivos:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in SERVICIOS:
                hallados.append((ruta.relative_to(RAIZ), nodo.func.id))
    return hallados


def test_solo_el_registro_del_nucleo_construye_los_servicios():
    fuera = [(r, s) for r, s in _construcciones() if r != UNICO_LUGAR]
    assert fuera == [], f"ningún módulo debe construir su propio servicio: {fuera}"
    assert {s for r, s in _construcciones() if r == UNICO_LUGAR} == SERVICIOS


@pytest.fixture
def kernel(tmp_path):
    k = Kernel()
    k.register_service("DataStore", DataStore())
    registrar_servicios_compartidos(k)
    return k


def test_el_registro_deja_una_instancia_de_cada_servicio(kernel):
    ajustes, exportacion, medicion = (kernel.get_service(c) for c in ("Settings", "Export", "Measurement"))
    assert isinstance(ajustes, SettingsService)
    assert isinstance(exportacion, ExportService)
    assert isinstance(medicion, MeasurementService)
    assert exportacion.settings is ajustes, "exportación y ajustes comparten la misma instancia de ajustes"
    assert exportacion.datastore is medicion.datastore is kernel.get_service("DataStore")


def test_cada_extension_obtiene_los_ajustes_del_kernel(kernel):
    meta = PluginMeta(id="x", name="X", category="Analysis", subcategory="s", version="1", icon="i", logic_class="C")

    class Plugin(IPlugin):
        def process(self, data): pass
        def stop(self): pass
        def get_widget(self, parent=None): return None

    uno, otro = Plugin(meta), Plugin(meta)
    assert uno.settings is None, "sin núcleo no hay ajustes, y tampoco los crea por su cuenta"
    uno.kernel = otro.kernel = kernel
    assert uno.settings is otro.settings is kernel.get_service("Settings")


def _vista():
    return dict(parent=None, vtk_widget=object(), get_active_chart=lambda: None, get_names=lambda: ("s", None, "p"))


def test_el_exportador_de_cada_ventana_sale_del_mismo_servicio(kernel):
    exportacion = kernel.get_service("Export")
    a, b = exportacion.para(**_vista()), exportacion.para(**_vista())
    assert isinstance(a, Exportador) and a is not b
    assert a._get_last_dir == b._get_last_dir == exportacion.carpeta_de_exportacion


def test_la_carpeta_de_exportacion_sigue_al_proyecto_abierto(tmp_path):
    ajustes = SettingsService(carpeta=str(tmp_path))
    almacen = DataStore()
    exportacion = ExportService(ajustes, almacen)
    elegida = str(tmp_path / "fuera")

    exportacion.recordar_carpeta(elegida)
    assert exportacion.carpeta_de_exportacion() == elegida

    proyecto = SimpleNamespace(is_open=True, archivos_dir=lambda: str(tmp_path / "proyecto"))
    almacen.set("_project_service", proyecto)
    assert exportacion.carpeta_de_exportacion() == str(tmp_path / "proyecto")
    exportacion.recordar_carpeta(str(tmp_path / "dentro"))
    assert ajustes.get("last_export_dir") == elegida, "una exportación dentro del proyecto no pisa la carpeta elegida"


def test_cada_ventana_tiene_su_sesion_de_medicion_y_todas_guardan_en_el_mismo_almacen(kernel):
    medicion = kernel.get_service("Measurement")
    ventana_1, ventana_2 = object(), object()
    s1 = medicion.sesion_para(None, ventana_1, lambda: None)
    s2 = medicion.sesion_para(None, ventana_2, lambda: None)
    assert isinstance(s1, SesionDeMedicion) and s1 is not s2
    assert medicion.sesion_de(ventana_1) is s1 and medicion.sesion_de(ventana_2) is s2

    s1.ds_set("measurements", [{"id": 1}])
    assert s2.ds_get("measurements") == [{"id": 1}]
    assert kernel.get_service("DataStore").get("measurements") == [{"id": 1}]


def test_una_sesion_nueva_en_la_misma_ventana_reemplaza_a_la_anterior(kernel):
    medicion = kernel.get_service("Measurement")
    ventana = object()
    vieja = medicion.sesion_para(None, ventana, lambda: None)
    nueva = medicion.sesion_para(None, ventana, lambda: None)
    assert medicion.sesion_de(ventana) is nueva and nueva is not vieja

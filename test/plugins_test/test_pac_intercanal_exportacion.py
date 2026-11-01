"""R65: el PAC entre canales exporta sus números, con el canal de amplitud entre los parámetros.

Sin esto, dos corridas con el mismo canal de fase y canales de amplitud distintos darían archivos
de parámetros idénticos. Se exporta de verdad (CSV, Excel y JSON) un resultado calculado con dos canales.
"""
import csv
import json
import zipfile
from unittest.mock import Mock

import pytest

from core.services.export_service import Exportador
from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin
from test_pac_intercanal import canal, correr

CANAL_AMPLITUD = "IN 7"


@pytest.fixture(scope="module")
def secciones():
    resultado = correr(canal(False, 0), canal(True, 1), canal_fase="CA1", canal_amplitud=CANAL_AMPLITUD)
    plugin = Pac_plugin.__new__(Pac_plugin)      # sin __init__: no levanta Qt ni VTK
    plugin.ui = None                             # sin casilla de unidades: grados
    plugin._ultimo = {
        "parametros": {"tipo": Pac_plugin.PSEL_INTER, "p1_hz": 3.0, "p2_hz": 8.0, "a1_hz": 25.0, "a2_hz": 60.0,
                       "trial": "todos", "canal_amplitud": CANAL_AMPLITUD},
        "resultado": resultado,
    }
    return plugin._secciones_resultado()


def _exportador(tmp_path):
    svc = Exportador(parent=Mock(), vtk_widget=Mock(), get_active_chart=lambda: None,
                        get_names=lambda: ("senal", "CA1", "PAC"),
                        last_dir_getter=lambda: str(tmp_path), last_dir_setter=lambda d: None)
    svc.alerts = Mock()
    return svc


def test_las_secciones_llevan_el_canal_de_amplitud(secciones):
    parametros = dict(secciones["Parametros"][1])
    assert parametros["canal_amplitud"] == CANAL_AMPLITUD
    assert set(secciones) == {"Parametros", "Resumen", "Histograma", "Mapa"}


def test_csv_incluye_el_canal_y_el_mapa(secciones, tmp_path):
    ruta = tmp_path / "pac.csv"
    _exportador(tmp_path).export_sections(secciones, "csv", str(ruta))
    filas = list(csv.reader(open(ruta, encoding="utf-8")))
    assert ["canal_amplitud", CANAL_AMPLITUD] in filas
    assert ["[Mapa]"] in filas and ["[Histograma]"] in filas


def test_json_incluye_el_canal_y_el_mapa(secciones, tmp_path):
    ruta = tmp_path / "pac.json"
    _exportador(tmp_path).export_sections(secciones, "json", str(ruta))
    datos = json.load(open(ruta, encoding="utf-8"))
    assert {"parametro": "canal_amplitud", "valor": CANAL_AMPLITUD} in datos["Parametros"]
    assert len(datos["Mapa"]) > 0


def test_excel_incluye_el_canal_en_su_hoja(secciones, tmp_path):
    ruta = tmp_path / "pac.xlsx"
    _exportador(tmp_path).export_sections(secciones, "xlsx", str(ruta))
    with zipfile.ZipFile(ruta) as z:
        hojas = [n for n in z.namelist() if n.startswith("xl/worksheets/")]
        assert len(hojas) == 4, "una hoja por sección"
        assert any(CANAL_AMPLITUD in z.read(h).decode("utf-8") for h in hojas)

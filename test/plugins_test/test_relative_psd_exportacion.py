"""R05: la PSD relativa exporta sus números (parámetros, potencias y fracción por banda)."""
import csv
import json
import zipfile
from unittest.mock import Mock

import numpy as np
import pytest

from core.services.export_service import Exportador
from plugins.analysis.frequency.relative_psd.relative_psd_plugin import Relative_psd_plugin, calcular_psd

FS = 1000.0
BANDAS = ["delta", "theta", "alpha", "beta", "gamma1", "gamma2", "HFO1", "HFO2"]


@pytest.fixture(scope="module")
def secciones():
    t = np.arange(0, 2.0, 1 / FS)
    trials = np.column_stack([np.sin(2 * np.pi * 10 * t) + 0.1 * np.random.default_rng(i).standard_normal(t.size)
                              for i in range(3)])
    freq, pxx, fs_eff = calcular_psd(trials, FS, FS, "hamming", 256, 128, 256, "none")
    plugin = Relative_psd_plugin.__new__(Relative_psd_plugin)      # sin __init__: no levanta Qt ni VTK
    plugin.ui = None
    plugin.meta = Mock(name="meta")
    plugin._trials_used = {"label": "3 trials"}
    abs_p, rel_p = plugin._compute_relative_psd(freq, pxx, 8.0, 12.0, 1)
    plugin._ultimo = dict(freq=freq, pxx=pxx, fs_eff=fs_eff, f1=8.0, f2=12.0, GF=1, ch_name="CA1",
                          abs_power=abs_p, rel_power=rel_p)
    return plugin._secciones_resultado(), rel_p


def _exportador(tmp_path):
    svc = Exportador(parent=Mock(), vtk_widget=Mock(), get_active_chart=lambda: None,
                     get_names=lambda: ("senal", "CA1", "Relative PSD"),
                     last_dir_getter=lambda: str(tmp_path), last_dir_setter=lambda d: None)
    svc.alerts = Mock()
    return svc


def test_las_secciones_traen_potencias_y_las_ocho_bandas(secciones):
    datos, rel = secciones
    assert set(datos) == {"Parametros", "Potencia", "Bandas"}
    assert [f[0] for f in datos["Bandas"][1]] == BANDAS
    potencia = dict(datos["Potencia"][1])
    assert potencia["potencia_relativa"] == pytest.approx(rel)
    assert dict(datos["Parametros"][1])["canal"] == "CA1"
    fracciones = dict((f[0], f[3]) for f in datos["Bandas"][1])
    assert fracciones["alpha"] > 0.5, "la señal de 10 Hz cae en alfa"


def test_csv_incluye_parametros_potencias_y_bandas(secciones, tmp_path):
    ruta = tmp_path / "psd.csv"
    _exportador(tmp_path).export_sections(secciones[0], "csv", str(ruta))
    filas = list(csv.reader(open(ruta, encoding="utf-8")))
    assert ["[Bandas]"] in filas and ["[Potencia]"] in filas
    assert any(f and f[0] == "alpha" for f in filas)
    assert any(f and f[0] == "banda_baja_hz" and float(f[1]) == 8.0 for f in filas)


def test_json_incluye_las_ocho_bandas(secciones, tmp_path):
    ruta = tmp_path / "psd.json"
    _exportador(tmp_path).export_sections(secciones[0], "json", str(ruta))
    datos = json.load(open(ruta, encoding="utf-8"))
    assert [f["banda"] for f in datos["Bandas"]] == BANDAS
    assert {f["medida"] for f in datos["Potencia"]} == {"potencia_absoluta", "potencia_relativa"}


def test_excel_tiene_una_hoja_por_seccion(secciones, tmp_path):
    ruta = tmp_path / "psd.xlsx"
    _exportador(tmp_path).export_sections(secciones[0], "xlsx", str(ruta))
    with zipfile.ZipFile(ruta) as z:
        assert len([n for n in z.namelist() if n.startswith("xl/worksheets/")]) == 3

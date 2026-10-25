"""Los paneles de resultados (Slope y Amplitude) exportan también a Excel."""
import pandas as pd
import pytest
from PyQt5.QtWidgets import QApplication

from plugins.measure.amplitude import amplitude_plugin
from plugins.measure.slope import slope_plugin


class _Modelo:
    def __init__(self, filas):
        self.filas = filas

    def get_all_rows(self):
        return self.filas


class _Alertas:
    def __init__(self):
        self.mensajes = []

    def error(self, m, *a):
        self.mensajes.append(("error", m))

    def warning(self, m, *a):
        self.mensajes.append(("warning", m))


FILAS = {
    slope_plugin.SlopePlugin: [{"id": 1, "p1x": 0.1, "p1y": 2.0, "p2x": 0.3, "p2y": 5.0, "dx": 0.2,
                                "dy": 3.0, "slope": 15.0, "dist": 3.0, "timestamp": "t"}],
    amplitude_plugin.AmplitudePlugin: [{"id": 1, "x1": 0.1, "x2": 0.2, "n": 10, "y_min": -1,
                                        "y_max": 2, "amp_pp": 3, "timestamp": "t"}],
}


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def _plugin(cls, filas, carpeta):
    p = cls.__new__(cls)
    p.model, p.alerts, p.widget = _Modelo(filas), _Alertas(), None
    p._export_dir = lambda: str(carpeta)
    p._notify = lambda m: None
    return p


@pytest.mark.parametrize("cls", list(FILAS))
def test_exporta_a_excel_las_mismas_columnas_que_el_csv(_app, tmp_path, monkeypatch, cls):
    ruta = str(tmp_path / "medidas.xlsx")
    monkeypatch.setattr(cls.__module__ + ".QFileDialog.getSaveFileName", lambda *a, **k: (ruta, ""))
    p = _plugin(cls, FILAS[cls], tmp_path)
    p.export_xlsx()
    df = pd.read_excel(ruta)
    headers, _ = p._tabla_exportable()
    assert list(df.columns) == headers
    assert len(df) == 1 and not p.alerts.mensajes


@pytest.mark.parametrize("cls", list(FILAS))
def test_sin_medidas_avisa_y_no_escribe(_app, tmp_path, cls):
    p = _plugin(cls, [], tmp_path)
    p.export_xlsx()
    assert p.alerts.mensajes and not list(tmp_path.iterdir())

"""R77: un plugin nuevo se guarda con el proyecto y se ordena declarándolo en su properties.yml."""
from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication

from core.kernel import Kernel
from core.plugins.loader import discover
from core.services.project_service import ProjectService

RAIZ = Path(__file__).resolve().parents[2] / "plugins"

ANTES = {"FFT", "FFT Average", "PSD", "PSD Average", "Relative PSD", "Average",
         "Event Related Potential", "Wavelet", "Wavelet Average", "PAC", "PPC"}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _metas():
    return {m.name: m for m, _ in discover(RAIZ)}


def test_los_plugins_que_se_guardaban_siguen_declarandolo():
    metas = _metas()
    assert {n for n, m in metas.items() if m.saves_analysis} == ANTES


def test_el_orden_de_botones_viene_de_los_metadatos():
    metas = _metas()
    tf = sorted((n for n, m in metas.items() if m.subcategory == "Time-Frequency"), key=lambda n: metas[n].order)
    assert tf == ["PAC", "Modulation Index", "Wavelet", "Wavelet Average"]
    med = sorted((n for n, m in metas.items() if m.subcategory == "Measurements"), key=lambda n: metas[n].order)
    assert med == ["Slope Results", "Amplitude Results"]
    assert metas["PPC"].subcategory_order is not None


def _plugin_falso(carpeta, nombre, extra):
    carpeta.mkdir()
    (carpeta / "properties.yml").write_text(
        f'id: "{nombre}"\nname: "{nombre}"\ncategory: "Analysis"\nsubcategory: "Nuevo"\n'
        f'version: "1.0"\nicon: "x.png"\nlogic_class: "Falso"\nui_class: ""\n{extra}', encoding="utf-8")
    (carpeta / "plugin.py").write_text(
        "from core.plugins.interfaces import IPlugin\n"
        "from PyQt5.QtWidgets import QWidget\n"
        "class Falso(IPlugin):\n"
        "    aplicado = None\n"
        "    def process(self, data): pass\n"
        "    def stop(self): pass\n"
        "    def get_widget(self, parent=None):\n"
        "        self.widget = self.widget or QWidget()\n"
        "        return self.widget\n"
        "    def get_analysis_params(self): return {'valor': 7}\n"
        "    def apply_analysis_params(self, p): Falso.aplicado = p\n", encoding="utf-8")


def test_plugin_nuevo_se_guarda_y_se_restaura_sin_tocar_el_nucleo(tmp_path, qapp):
    _plugin_falso(tmp_path / "nuevo", "Nuevo Guardado", "saves_analysis: true\norder: 1\n")
    _plugin_falso(tmp_path / "otro", "Nuevo Sin Guardar", "")
    kernel = Kernel()
    for meta, cls in discover(tmp_path):
        plugin = cls(meta)
        kernel.register_plugin(meta.name, plugin)
        plugin.get_widget()
    ps = ProjectService(kernel)
    guardado = ps._analysis_to_json()
    assert guardado == {"Nuevo Guardado": {"valor": 7}}
    ps._restore_analysis(guardado)
    assert kernel.get_plugin("Nuevo Guardado").aplicado == {"valor": 7}


def test_un_properties_sin_los_campos_nuevos_sigue_cargando(tmp_path):
    _plugin_falso(tmp_path / "viejo", "Viejo", "")
    (meta, _), = discover(tmp_path)
    assert meta.saves_analysis is False and meta.order is None and meta.subcategory_order is None

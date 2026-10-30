"""R02: cada situación usa el nivel de severidad que le corresponde.

Regla: `info` confirma o informa sin impedir nada; `warning` es una acción que no
puede seguir por algo que el usuario puede corregir (falta un paso, un parámetro
inválido, ya hay una operación en curso); `error` es un fallo o un dato dañado.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LLAMADA = re.compile(r"alerts\.(info|warning|error)\(\s*(f?)\"([^\"]*)\"")


def _llamadas():
    for ruta in list((RAIZ / "plugins").rglob("*.py")) + list((RAIZ / "core").rglob("*.py")) + \
            list((RAIZ / "app").rglob("*.py")):
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        for m in LLAMADA.finditer(texto):
            yield ruta.name, m.group(1), m.group(3)


def _niveles(fragmento):
    return {(archivo, nivel) for archivo, nivel, msg in _llamadas() if fragmento.lower() in msg.lower()}


def test_falta_un_paso_previo_es_advertencia():
    for fragmento in ("Primero genera", "Primero ejecuta"):
        encontrados = _niveles(fragmento)
        assert encontrados, fragmento
        assert {n for _, n in encontrados} == {"warning"}, encontrados


def test_no_hay_nada_que_exportar_es_advertencia():
    for fragmento in ("No measurements to export", "There is no chart to export",
                      "does not contain data to export", "There are no results to export"):
        encontrados = _niveles(fragmento)
        assert encontrados, fragmento
        assert {n for _, n in encontrados} == {"warning"}, (fragmento, encontrados)


def test_un_dataset_inconsistente_es_error():
    for fragmento in ("invalid dimensions", "does not match trials", "does not contain 'time_rel'"):
        assert {n for _, n in _niveles(fragmento)} == {"error"}, fragmento


def test_las_confirmaciones_son_informativas():
    for fragmento in ("successfully", "Project saved", "discarded.", "included."):
        encontrados = _niveles(fragmento)
        assert encontrados, fragmento
        assert {n for _, n in encontrados} == {"info"}, (fragmento, encontrados)


def test_un_fallo_inesperado_es_error():
    for fragmento in ("No se pudo calcular", "Error creating", "Error exporting"):
        assert {n for _, n in _niveles(fragmento)} == {"error"}, fragmento

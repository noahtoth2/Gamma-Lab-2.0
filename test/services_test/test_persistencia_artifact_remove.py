"""Las modificaciones de artifact_remove sobreviven a guardar y abrir el proyecto.

Problema nº 21: el proyecto guarda cómo se generaron los trials, no sus valores,
y no había nada que reaplicara las modificaciones de artefactos. Al reabrir, los
trials volvían a estar como antes de modificarlos y el trabajo se perdía.

La solución elegida fue la opción A, guardar la receta: el proyecto anota el modo,
los puntos A y B y los descartes vigentes, y al abrir reaplica el cálculo. Estas
pruebas verifican que la reconstrucción es idéntica bit a bit.
"""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from core.filters import trials as tr
from core.filters.artifacts import (
    columnas_activas, reaplicar_modificaciones, receta)
from core.kernel import Kernel
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService
from core.services.project_service import ProjectService
from plugins.preprocessing.prepare.artifact_remove.artifact_logic import (
    apply_modification_to_all_valid)

REPO = Path(__file__).resolve().parents[2]
ABF_PATH = REPO / "test" / "data" / "17308005.abf"

CORTE = dict(channel=0, stim_channel=1, threshold=0.7, t0=-0.05, t1=4.00,
             end_mode="until_next_onset", stim_expected=1, inter_stim_time=0.0,
             pad_value=0.0, debug=False)
PARAMS = dict(mode="interpolate", point_a=1.00, point_b=1.20)


@pytest.fixture(scope="module")
def senal_real():
    if not ABF_PATH.exists():
        pytest.skip("no se encontro el archivo ABF de prueba")
    sd = FileIOService().load_abf(str(ABF_PATH))
    sd.signals = sd.signals.astype(np.float64, copy=False)
    sd.time = sd.time.astype(np.float64, copy=False)
    return sd


def _cortar(senal_real, descartes=()):
    """Una copia nueva de la senal con sus trials recortados, como al abrir un proyecto."""
    sd = copy.deepcopy(senal_real)
    td = tr.cut_trials_single_channel(ds=sd, **CORTE)
    # El plugin de trials deja esto en los metadatos, y _trials_to_json salta las
    # entradas que no lo tienen: sin ello el manifiesto saldria vacio.
    td.metadata["generation_params"] = {k: v for k, v in CORTE.items()
                                        if k not in ("pad_value", "debug")}
    sd.add_trial_dataset(td)
    for i in descartes:
        sd.discard_trial(Path(td.source).name, td.channel_name, i)
    return sd, td


def _entorno(senal_real, descartes=()):
    sd, td = _cortar(senal_real, descartes)
    kernel = Kernel()
    store = DataStore()
    kernel.register_service("DataStore", store)
    store.set_active_signal(store.add_signal(sd))
    return kernel, sd, td


# ---------------------------------------------------------------- la receta

def test_aplicar_deja_la_receta_en_los_metadatos(senal_real):
    kernel, _, td = _entorno(senal_real)
    assert apply_modification_to_all_valid(kernel, **PARAMS) is True

    recetas = td.metadata.get("modificaciones")
    assert recetas, "aplicar una modificacion debe dejar su receta en los metadatos"
    assert len(recetas) == 1
    r = recetas[0]
    assert r["mode"] == PARAMS["mode"]
    assert r["point_a"] == pytest.approx(PARAMS["point_a"])
    assert r["point_b"] == pytest.approx(PARAMS["point_b"])
    assert r["discarded_indices"] == []


def test_la_receta_guarda_los_descartes_vigentes(senal_real):
    kernel, _, td = _entorno(senal_real, descartes=(3, 10, 25))
    assert apply_modification_to_all_valid(kernel, **PARAMS) is True

    r = td.metadata["modificaciones"][0]
    assert r["discarded_indices"] == [3, 10, 25], \
        "sin los descartes vigentes, reaplicar tocaria columnas distintas"


def test_la_receta_sobrevive_a_json(senal_real):
    kernel, _, td = _entorno(senal_real, descartes=(7,))
    apply_modification_to_all_valid(kernel, **PARAMS)
    r = td.metadata["modificaciones"][0]
    assert json.loads(json.dumps(r)) == r, "la receta debe ser serializable tal cual"


# -------------------------------------------------- la reconstruccion exacta

@pytest.mark.parametrize("descartes", [(), (3, 10, 25), (0,), (0, 1, 2, 58, 59)])
def test_reaplicar_reconstruye_bit_a_bit(senal_real, descartes):
    # 1) Sesion de trabajo: se modifica y se guarda la receta
    kernel, _, td = _entorno(senal_real, descartes=descartes)
    assert apply_modification_to_all_valid(kernel, **PARAMS) is True
    esperado = np.array(td.trials, copy=True)
    recetas = [json.loads(json.dumps(r)) for r in td.metadata["modificaciones"]]

    # 2) Reapertura: los trials se recortan de cero y se reaplica la receta
    _, td2 = _cortar(senal_real, descartes=descartes)
    sin_reaplicar = np.array(td2.trials, copy=True)
    assert not np.array_equal(sin_reaplicar, esperado), \
        "el escenario no prueba nada si al recortar ya salieran modificados"

    n = reaplicar_modificaciones(td2, recetas)
    assert n == 1, "debia reaplicarse exactamente una receta"
    assert np.array_equal(td2.trials, esperado), \
        "la reconstruccion no coincide bit a bit con la sesion original"


def test_dos_modificaciones_disjuntas_se_reaplican_las_dos(senal_real):
    """Ventanas que no se tocan: el resultado no depende del orden, pero las dos
    recetas tienen que quedar guardadas y volver a aplicarse."""
    kernel, _, td = _entorno(senal_real)
    assert apply_modification_to_all_valid(kernel, mode="interpolate", point_a=1.00, point_b=1.20) is True
    assert apply_modification_to_all_valid(kernel, mode="blank", point_a=2.00, point_b=2.10) is True
    esperado = np.array(td.trials, copy=True)
    recetas = [json.loads(json.dumps(r)) for r in td.metadata["modificaciones"]]
    assert len(recetas) == 2

    _, td2 = _cortar(senal_real)
    assert reaplicar_modificaciones(td2, recetas) == 2
    assert np.array_equal(td2.trials, esperado), \
        "dos modificaciones encadenadas deben reconstruirse igual"


def test_el_orden_se_respeta_con_ventanas_solapadas(senal_real):
    """Con ventanas que se solapan el resultado si depende del orden, asi que
    reaplicar al reves tiene que dar algo distinto."""
    kernel, _, td = _entorno(senal_real)
    assert apply_modification_to_all_valid(kernel, mode="interpolate", point_a=1.00, point_b=1.40) is True
    assert apply_modification_to_all_valid(kernel, mode="blank", point_a=1.20, point_b=1.60) is True
    esperado = np.array(td.trials, copy=True)
    recetas = [json.loads(json.dumps(r)) for r in td.metadata["modificaciones"]]

    _, td2 = _cortar(senal_real)
    assert reaplicar_modificaciones(td2, recetas) == 2
    assert np.array_equal(td2.trials, esperado), \
        "en el mismo orden la reconstruccion debe ser exacta"

    _, td3 = _cortar(senal_real)
    reaplicar_modificaciones(td3, list(reversed(recetas)))
    assert not np.array_equal(td3.trials, esperado), \
        "con ventanas solapadas el orden importa, y reaplicar al reves deberia notarse"


def test_reaplicar_marca_los_trials_modificados(senal_real):
    kernel, _, td = _entorno(senal_real, descartes=(5,))
    apply_modification_to_all_valid(kernel, **PARAMS)
    recetas = [json.loads(json.dumps(r)) for r in td.metadata["modificaciones"]]

    _, td2 = _cortar(senal_real, descartes=(5,))
    reaplicar_modificaciones(td2, recetas)
    assert td2.metadata.get("modificaciones") == recetas
    assert 5 not in td2.metadata.get("modified_trials", set()), \
        "el trial descartado no estaba activo, no debe aparecer como modificado"


# ------------------------------------------------------------- casos limite

def test_sin_recetas_no_toca_nada(senal_real):
    _, td = _cortar(senal_real)
    antes = np.array(td.trials, copy=True)
    assert reaplicar_modificaciones(td, []) == 0
    assert reaplicar_modificaciones(td, None) == 0
    assert np.array_equal(td.trials, antes)


def test_una_receta_invalida_no_interrumpe_las_demas(senal_real):
    _, td = _cortar(senal_real)
    buenas = [receta("interpolate", 1.00, 1.20, ())]
    mezcla = [{"mode": "modo_que_no_existe", "point_a": 1.0, "point_b": 1.2,
               "discarded_indices": []}] + buenas
    assert reaplicar_modificaciones(td, mezcla) == 1, \
        "la receta rota debe saltarse y la buena aplicarse"


def test_columnas_activas_respeta_los_descartes():
    assert columnas_activas(5, ()) == [0, 1, 2, 3, 4]
    assert columnas_activas(5, (1, 3)) == [0, 2, 4]
    assert columnas_activas(5, (0, 1, 2, 3, 4)) == []
    assert columnas_activas(3, (9,)) == [0, 1, 2], "un indice fuera de rango se ignora"


# ----------------------------------------------- el manifiesto del proyecto

def test_el_manifiesto_incluye_la_receta(senal_real):
    kernel, sd, td = _entorno(senal_real, descartes=(4,))
    apply_modification_to_all_valid(kernel, **PARAMS)

    entradas = ProjectService._trials_to_json(sd)
    assert entradas, "el manifiesto debe traer la entrada de trials"
    con_mods = [e for e in entradas if e.get("modifications")]
    assert con_mods, "el manifiesto debe incluir las modificaciones aplicadas"
    r = con_mods[0]["modifications"][0]
    assert r["mode"] == PARAMS["mode"]
    assert r["discarded_indices"] == [4]
    assert json.loads(json.dumps(entradas)) == entradas, \
        "el manifiesto completo debe ser serializable"


def test_el_manifiesto_no_inventa_la_clave_si_no_hubo_modificaciones(senal_real):
    _, sd, _ = _entorno(senal_real)
    entradas = ProjectService._trials_to_json(sd)
    assert entradas
    assert all("modifications" not in e for e in entradas), \
        "sin modificaciones no debe aparecer la clave en el manifiesto"

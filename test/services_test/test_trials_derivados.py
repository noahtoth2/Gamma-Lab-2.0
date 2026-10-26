"""R79: el preprocesamiento no modifica los trials originales; deja un conjunto derivado.

Antes la remoción de artefactos escribía sobre las columnas del TrialDataset
recortado: el original se perdía mientras el proyecto estaba abierto. Ahora el
resultado se registra como un derivado, `get_active_trials` lo sirve a los
análisis, y el original sigue disponible.
"""
from pathlib import Path

import numpy as np
import pytest

from core.filters.artifacts import crear_derivado
from core.filters.trials import cut_trials_single_channel
from core.kernel import Kernel
from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore
from core.services.project_service import ProjectService
from plugins.preprocessing.prepare.artifact_remove.artifact_logic import apply_modification_to_all_valid

FS = 2000.0
RECETA = dict(channel=0, stim_channel=1, threshold=0.5, t0=0.0, t1=1.0, end_mode="fixed",
              stim_expected=None, inter_stim_time=None)
ARCHIVO = "d.abf"


def _senal():
    n = int(FS * 12)
    t = np.arange(n) / FS
    stim = np.zeros(n)
    for k in range(6):
        stim[int((1 + 1.5 * k) * FS): int((1 + 1.5 * k) * FS) + 10] = 1.0
    rng = np.random.default_rng(0)
    ds = SignalDataset(name=ARCHIVO, format="abf", source_path=f"C:/x/{ARCHIVO}", sampling_rate=FS, time=t,
                       signals=np.vstack([np.sin(2 * np.pi * 8 * t) + 0.1 * rng.standard_normal(n), stim]),
                       channel_names=["a", "stim"], units=["mV", "V"])
    td = cut_trials_single_channel(ds=ds, **RECETA, debug=False)
    td.metadata["generation_params"] = dict(RECETA)
    ds.add_trial_dataset(td)
    return ds, td


def _entorno():
    ds, td = _senal()
    kernel, store = Kernel(), DataStore()
    kernel.register_service("DataStore", store)
    store.set_active_signal(store.add_signal(ds))
    return kernel, ds, td


APLICAR = dict(mode="blank", point_a=0.40, point_b=0.50)


def test_la_remocion_no_toca_los_trials_originales():
    kernel, ds, td = _entorno()
    antes = np.array(td.trials, copy=True)
    assert apply_modification_to_all_valid(kernel, **APLICAR) is True
    assert np.array_equal(td.trials, antes), "el original debe quedar bit a bit igual"
    assert "modificaciones" not in td.metadata and "modified_trials" not in td.metadata, \
        "ni siquiera sus metadatos se anotan"


def test_los_analisis_leen_el_derivado_y_el_original_sigue_disponible():
    kernel, ds, td = _entorno()
    apply_modification_to_all_valid(kernel, **APLICAR)

    activo = ds.get_active_trials(ds.name, "a")
    assert not np.array_equal(activo.trials, td.trials), "los análisis deben leer el resultado"
    assert ds.get_original_trials(ds.name, "a") is td
    assert np.array_equal(ds.get_original_trials(ds.name, "a").trials, td.trials)
    assert ds.get_derived_trials(ds.name, "a").metadata["derived_from"] == {"source": ARCHIVO, "channel": "a"}


def test_descartar_el_derivado_devuelve_el_original():
    kernel, ds, td = _entorno()
    apply_modification_to_all_valid(kernel, **APLICAR)
    assert ds.discard_derived_trials(ds.name, "a") is True
    assert ds.get_derived_trials(ds.name, "a") is None
    assert np.array_equal(ds.get_active_trials(ds.name, "a").trials, td.trials)
    assert ds.discard_derived_trials(ds.name, "a") is False, "una segunda vez no hay nada que descartar"


def test_dos_modificaciones_se_acumulan_en_el_mismo_derivado():
    kernel, ds, td = _entorno()
    apply_modification_to_all_valid(kernel, mode="blank", point_a=0.20, point_b=0.30)
    primero = ds.get_derived_trials(ds.name, "a")
    apply_modification_to_all_valid(kernel, mode="blank", point_a=0.60, point_b=0.70)
    derivado = ds.get_derived_trials(ds.name, "a")
    assert derivado is primero, "se sigue trabajando sobre el mismo conjunto derivado"
    assert len(derivado.metadata["modificaciones"]) == 2
    assert not np.array_equal(derivado.trials, td.trials)


def test_regenerar_los_trials_descarta_el_derivado():
    kernel, ds, td = _entorno()
    apply_modification_to_all_valid(kernel, **APLICAR)
    nuevo = cut_trials_single_channel(ds=ds, **RECETA, debug=False)
    nuevo.metadata["generation_params"] = dict(RECETA)
    ds.add_trial_dataset(nuevo)
    assert ds.get_derived_trials(ds.name, "a") is None, "un derivado de trials viejos ya no corresponde"
    assert ds.get_active_trials(ds.name, "a") is nuevo


def test_los_descartes_se_aplican_sobre_el_derivado():
    kernel, ds, td = _entorno()
    apply_modification_to_all_valid(kernel, **APLICAR)
    ds.discard_trial(ds.name, "a", 0)
    activo = ds.get_active_trials(ds.name, "a")
    derivado = ds.get_derived_trials(ds.name, "a")
    assert activo.trials.shape[1] == td.trials.shape[1] - 1
    assert np.array_equal(activo.trials, derivado.trials[:, 1:])


def test_el_proyecto_guarda_la_receta_y_al_abrir_recrea_el_derivado_sin_tocar_el_original():
    kernel, ds, td = _entorno()
    apply_modification_to_all_valid(kernel, **APLICAR)
    esperado = np.array(ds.get_derived_trials(ds.name, "a").trials, copy=True)

    entradas = ProjectService._trials_to_json(ds)
    assert entradas and entradas[0]["modifications"][0]["mode"] == "blank"

    ds2, _ = _senal()
    ds2.replace_trial_datasets([])
    ProjectService._restore_trials(ds2, entradas)
    original = ds2.get_original_trials(ds2.name, "a")
    derivado = ds2.get_derived_trials(ds2.name, "a")
    assert derivado is not None and np.array_equal(derivado.trials, esperado)
    assert np.array_equal(original.trials, td.trials), "al abrir, el original queda como se recortó"


def test_un_derivado_debe_venir_de_un_original_y_tener_su_forma():
    ds, td = _senal()
    ajeno = crear_derivado(td)
    ajeno.channel_name = "otro"
    with pytest.raises(ValueError):
        ds.register_derived_trials(ajeno)

    chico = crear_derivado(td)
    chico.trials = chico.trials[:, :-1]
    chico.onsets_s = chico.onsets_s[:-1]
    with pytest.raises(ValueError):
        ds.register_derived_trials(chico)


def test_un_derivado_no_puede_compartir_el_arreglo_del_original():
    ds, td = _senal()
    falso = crear_derivado(td)
    falso.trials = td.trials
    with pytest.raises(ValueError):
        ds.register_derived_trials(falso)


def test_crear_derivado_copia_los_datos_y_los_metadatos():
    _, td = _senal()
    d = crear_derivado(td)
    d.trials[0, 0] = 999.0
    d.metadata["generation_params"]["threshold"] = 123
    assert td.trials[0, 0] != 999.0
    assert td.metadata["generation_params"]["threshold"] == RECETA["threshold"]


# --------------------------------------------------------------- el filtro (R79)
from core.filters.bandpass import filtrar_banda, filtrar_columnas
from core.filters.artifacts import reaplicar_modificaciones
from plugins.preprocessing.prepare.artifact_remove.artifact_logic import (
    apply_filter_to_all_valid, descartar_derivado)

FILTRO = dict(low=4.0, high=40.0, order=4)


def test_filtrar_los_trials_deja_un_derivado_y_no_toca_el_original():
    kernel, ds, td = _entorno()
    antes = np.array(td.trials, copy=True)
    assert apply_filter_to_all_valid(kernel, **FILTRO) is True
    assert np.array_equal(td.trials, antes), "el original queda bit a bit igual"
    derivado = ds.get_derived_trials(ds.name, "a")
    assert derivado is not None and not np.array_equal(derivado.trials, antes)
    esperado = filtrar_banda(antes[:, 0], 4.0, 40.0, 4, FS)
    assert np.array_equal(derivado.trials[:, 0], esperado), "cada trial queda filtrado con fase cero"
    assert derivado.metadata["modificaciones"][0]["mode"] == "filter"


def test_descartar_el_derivado_deshace_el_filtro():
    kernel, ds, td = _entorno()
    apply_filter_to_all_valid(kernel, **FILTRO)
    assert descartar_derivado(kernel) == (ds.name, "a", True)
    assert np.array_equal(ds.get_active_trials(ds.name, "a").trials, td.trials)
    assert descartar_derivado(kernel)[2] is False


def test_filtro_y_artefacto_se_acumulan_en_orden_y_se_reaplican_igual():
    kernel, ds, td = _entorno()
    apply_filter_to_all_valid(kernel, **FILTRO)
    apply_modification_to_all_valid(kernel, mode="interpolate", point_a=0.40, point_b=0.50)
    derivado = ds.get_derived_trials(ds.name, "a")
    recetas = [dict(r) for r in derivado.metadata["modificaciones"]]
    assert [r["mode"] for r in recetas] == ["filter", "interpolate"]

    otro = crear_derivado(td)
    assert reaplicar_modificaciones(otro, recetas) == 2
    assert np.array_equal(otro.trials, derivado.trials, equal_nan=True), \
        "al abrir el proyecto la reconstrucción debe ser idéntica"

    inverso = crear_derivado(td)
    reaplicar_modificaciones(inverso, list(reversed(recetas)))
    assert not np.array_equal(inverso.trials, derivado.trials, equal_nan=True), "el orden importa"


def test_el_proyecto_recrea_el_filtrado_al_abrir():
    kernel, ds, td = _entorno()
    apply_filter_to_all_valid(kernel, **FILTRO)
    esperado = np.array(ds.get_derived_trials(ds.name, "a").trials, copy=True)
    entradas = ProjectService._trials_to_json(ds)
    assert entradas[0]["modifications"][0]["mode"] == "filter"

    ds2, _ = _senal()
    ds2.replace_trial_datasets([])
    ProjectService._restore_trials(ds2, entradas)
    assert np.array_equal(ds2.get_derived_trials(ds2.name, "a").trials, esperado)
    assert np.array_equal(ds2.get_original_trials(ds2.name, "a").trials, td.trials)


def test_un_filtro_con_frecuencias_invalidas_no_crea_derivado():
    kernel, ds, _ = _entorno()
    with pytest.raises(ValueError):
        apply_filter_to_all_valid(kernel, low=4.0, high=5000.0, order=4)
    assert ds.get_derived_trials(ds.name, "a") is None


def test_filtrar_columnas_se_cancela_entre_trials():
    class Ctx:
        cancelled = True

        def progress(self, *a):
            pass

    _, td = _senal()
    assert filtrar_columnas(td.trials, 4.0, 40.0, 4, FS, ctx=Ctx()) is None

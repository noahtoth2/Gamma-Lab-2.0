"""R54: el DataStore tiene un único escritor y lecturas seguras entre hilos."""
import threading
import time

import numpy as np
import pytest

from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore, EscrituraNoPermitida


def _senal(nombre="s.abf"):
    t = np.arange(10) / 10.0
    return SignalDataset(name=nombre, format="abf", source_path=f"C:/x/{nombre}", sampling_rate=10.0,
                         time=t, signals=np.vstack([t]), channel_names=["a"], units=["mV"])


def _en_otro_hilo(fn):
    """Ejecuta fn en otro hilo y devuelve (resultado, excepción)."""
    salida = {}

    def correr():
        try:
            salida["r"] = fn()
        except BaseException as e:
            salida["e"] = e

    h = threading.Thread(target=correr)
    h.start()
    h.join(10)
    return salida.get("r"), salida.get("e")


def test_el_hilo_que_lo_creo_puede_escribir():
    s = DataStore()
    s.set("k", 1)
    key = s.add_signal(_senal())
    s.set_active_signal(key)
    assert s.get("k") == 1 and s.get_active_signal() is not None
    s.clear_active_signal()
    s.remove("k")
    assert not s.has("k") and s.get_active_signal() is None


@pytest.mark.parametrize("escritura", [
    lambda s: s.set("k", 1),
    lambda s: s.add_signal(_senal()),
    lambda s: s.remove("existe"),
    lambda s: s.clear_active_signal(),
])
def test_otro_hilo_no_puede_escribir(escritura):
    s = DataStore()
    s.set("existe", 0)
    _, error = _en_otro_hilo(lambda: escritura(s))
    assert isinstance(error, EscrituraNoPermitida) and isinstance(error, PermissionError)
    assert s.get("existe") == 0 and not s.get_signals()


def test_otro_hilo_si_puede_leer():
    s = DataStore()
    key = s.add_signal(_senal())
    s.set_active_signal(key)
    s.set("k", 5)
    r, error = _en_otro_hilo(lambda: (s.get("k"), s.has("k"), s.get_active_signal() is not None,
                                      len(s.get_signals()), len(s.items()), s.get_active_signal_key()))
    assert error is None and r == (5, True, True, 1, s.items().__len__(), key)


def test_reasignar_propietario_cede_la_escritura_al_hilo_que_llama():
    s = DataStore()

    def adoptar():
        s.reasignar_propietario()
        s.set("k", 1)
        return s.get("k")

    r, error = _en_otro_hilo(adoptar)
    assert error is None and r == 1
    with pytest.raises(EscrituraNoPermitida):
        s.set("otra", 2)            # ahora el hilo de la prueba ya no es el propietario


def test_un_dato_con_dueno_no_lo_sobrescribe_otro_dueno():
    s = DataStore()
    s.set("resultado", 1, owner="PAC")
    s.set("resultado", 2, owner="PAC")
    with pytest.raises(EscrituraNoPermitida):
        s.set("resultado", 3, owner="PPC")
    assert s.get("resultado") == 2 and s.dueno_de("resultado") == "PAC"
    s.remove("resultado")
    s.set("resultado", 4, owner="PPC")      # al borrarlo se libera
    assert s.dueno_de("resultado") == "PPC"


def test_lecturas_concurrentes_con_escrituras_nunca_ven_el_diccionario_a_medias():
    s = DataStore()
    parar = threading.Event()
    errores = []

    def lector():
        while not parar.is_set():
            try:
                s.items()
                s.get_signals()
                s.get_active_signal()
            except Exception as e:      # "dictionary changed size during iteration"
                errores.append(e)
                return

    hilos = [threading.Thread(target=lector) for _ in range(4)]
    for h in hilos:
        h.start()
    for i in range(3000):
        s.set(f"k{i}", i)
        if i % 3 == 0:
            s.remove(f"k{i}")
        if i % 500 == 0:
            s.set_active_signal(s.add_signal(_senal(f"s{i}.abf")))
    parar.set()
    for h in hilos:
        h.join(10)
    assert not errores, errores[:1]


def test_una_tarea_que_escribe_en_el_datastore_falla_y_su_resultado_se_publica_en_la_interfaz():
    from PyQt5.QtWidgets import QApplication
    from core.services.task_service import TaskService
    app = QApplication.instance() or QApplication([])
    s = DataStore()
    ts = TaskService()
    resultados = {}

    def mala(ctx=None):
        s.set("directo", 1)

    def buena(ctx=None):
        return 42

    hm = ts.submit(mala, owner="t1")
    hm.failed.connect(lambda m: resultados.setdefault("falla", m))
    t0 = time.time()
    while "falla" not in resultados and time.time() - t0 < 10:
        app.processEvents()
        time.sleep(0.005)
    assert "DataStore" in resultados["falla"] and not s.has("directo")

    hb = ts.submit(buena, owner="t2")
    hb.finished.connect(lambda r: s.set("publicado", r))        # llega al hilo de la interfaz
    t0 = time.time()
    while not s.has("publicado") and time.time() - t0 < 10:
        app.processEvents()
        time.sleep(0.005)
    assert s.get("publicado") == 42

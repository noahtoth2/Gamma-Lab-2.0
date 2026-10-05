import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from PyQt5.QtCore import QCoreApplication

from core.services.task_service import TaskService


@pytest.fixture(scope="module")
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def wait_for(predicate, timeout_ms=5000):
    app = QCoreApplication.instance()
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return predicate()


class Recorder:

    def __init__(self, handle):
        self.finished = []
        self.failed = []
        self.cancelled = 0
        self.progress = []
        handle.finished.connect(self.finished.append)
        handle.failed.connect(self.failed.append)
        handle.cancelled.connect(self._on_cancelled)
        handle.progress.connect(lambda p, m: self.progress.append((p, m)))

    def _on_cancelled(self):
        self.cancelled += 1

    @property
    def settled(self):
        return bool(self.finished) or bool(self.failed) or self.cancelled > 0


def suma(a, b):
    return a + b


def revienta():
    raise ValueError("fallo a proposito")


def devuelve_hilo():
    return threading.get_ident()


def cooperativa(ctx, vueltas=200):
    for i in range(vueltas):
        if ctx.cancelled:
            return "cancelada a mitad"
        ctx.progress(int(100 * i / vueltas), f"vuelta {i}")
        time.sleep(0.005)
    return "completada"


def terca(duracion=1.5):
    time.sleep(duracion)
    return "termine igual"


def lenta(marca, retardo=0.15):
    time.sleep(retardo)
    return marca


def test_resultado_llega_por_finished(qt_app):
    svc = TaskService()
    rec = Recorder(svc.submit(suma, owner="p1", a=2, b=3))

    assert wait_for(lambda: rec.settled)
    assert rec.finished == [5]
    assert not rec.failed and rec.cancelled == 0


def test_corre_fuera_del_hilo_principal(qt_app):
    svc = TaskService()
    rec = Recorder(svc.submit(devuelve_hilo, owner="p1"))

    assert wait_for(lambda: rec.settled)
    assert rec.finished[0] != threading.get_ident()


def test_excepcion_emite_failed_y_no_tumba_nada(qt_app):
    svc = TaskService()
    rec = Recorder(svc.submit(revienta, owner="p1"))

    assert wait_for(lambda: rec.settled)
    assert not rec.finished
    assert len(rec.failed) == 1
    assert rec.failed[0] == "ValueError: fallo a proposito"

    rec2 = Recorder(svc.submit(suma, owner="p1", a=1, b=1))
    assert wait_for(lambda: rec2.settled)
    assert rec2.finished == [2]


def test_progreso_se_reporta(qt_app):
    svc = TaskService()
    rec = Recorder(svc.submit(cooperativa, owner="p1", vueltas=20))

    assert wait_for(lambda: rec.settled)
    assert rec.finished == ["completada"]
    assert len(rec.progress) == 20
    assert rec.progress[0][0] == 0
    assert all(0 <= p <= 100 for p, _ in rec.progress)


def test_cancelar_tarea_cooperativa(qt_app):
    svc = TaskService()
    h = svc.submit(cooperativa, owner="p1", vueltas=400)
    rec = Recorder(h)

    wait_for(lambda: len(rec.progress) > 2, timeout_ms=2000)
    h.cancel()

    assert wait_for(lambda: rec.settled)
    assert rec.cancelled == 1
    assert not rec.finished


def test_cancelar_encolada_no_la_ejecuta(qt_app):
    svc = TaskService()
    rec_a = Recorder(svc.submit(lenta, owner="p1", marca="A"))
    h_b = svc.submit(lenta, owner="p2", marca="B")
    rec_b = Recorder(h_b)

    h_b.cancel()

    assert wait_for(lambda: rec_a.settled and rec_b.settled)
    assert rec_a.finished == ["A"]
    assert rec_b.cancelled == 1
    assert not rec_b.finished


def test_una_sola_a_la_vez(qt_app):
    activas = []
    pico = []

    def registra(marca):
        activas.append(marca)
        pico.append(len(activas))
        time.sleep(0.1)
        activas.remove(marca)
        return marca

    svc = TaskService()
    recs = [Recorder(svc.submit(registra, owner=f"p{i}", marca=i)) for i in range(4)]

    assert wait_for(lambda: all(r.settled for r in recs), timeout_ms=8000)
    assert max(pico) == 1, f"hubo {max(pico)} tareas corriendo a la vez"
    assert [r.finished[0] for r in recs] == [0, 1, 2, 3], "la cola no respeto el orden"


def test_reemplazo_descarta_las_encoladas_del_mismo_owner(qt_app):
    svc = TaskService()
    rec_corriendo = Recorder(svc.submit(lenta, owner="otro", marca="corriendo"))
    rec_vieja = Recorder(svc.submit(lenta, owner="p1", marca="vieja"))
    rec_nueva = Recorder(svc.submit(lenta, owner="p1", marca="nueva"))

    assert wait_for(lambda: all(r.settled for r in
                                (rec_corriendo, rec_vieja, rec_nueva)))
    assert rec_vieja.cancelled == 1, "la encolada obsoleta debio descartarse"
    assert not rec_vieja.finished
    assert rec_nueva.finished == ["nueva"]
    assert rec_corriendo.finished == ["corriendo"], "no debe tocar la que ya corria"


def test_cancel_all_from_limpia_un_owner(qt_app):
    svc = TaskService()
    rec1 = Recorder(svc.submit(cooperativa, owner="plug", vueltas=400))
    rec2 = Recorder(svc.submit(lenta, owner="plug", marca="encolada"))
    rec3 = Recorder(svc.submit(lenta, owner="otro", marca="ajena"))

    wait_for(lambda: len(rec1.progress) > 2, timeout_ms=2000)
    afectadas = svc.cancel_all_from("plug")
    assert afectadas == 2

    assert wait_for(lambda: all(r.settled for r in (rec1, rec2, rec3)))
    assert rec1.cancelled == 1 and not rec1.finished
    assert rec2.cancelled == 1 and not rec2.finished
    assert rec3.finished == ["ajena"], "no debe tocar tareas de otro owner"


def test_tarea_terca_se_desliga_y_devuelve_la_interfaz(qt_app):
    svc = TaskService(cancel_timeout_ms=200)
    h = svc.submit(terca, owner="p1", duracion=1.5)
    rec = Recorder(h)

    wait_for(lambda: svc._running is not None, timeout_ms=2000)

    t0 = time.monotonic()
    h.cancel()
    assert wait_for(lambda: rec.settled, timeout_ms=2000)
    transcurrido = time.monotonic() - t0

    assert rec.cancelled == 1
    assert not rec.finished, "el resultado de una tarea desligada se descarta"
    assert transcurrido < 1.0, f"tardo {transcurrido:.2f}s en devolver la interfaz"

    rec2 = Recorder(svc.submit(suma, owner="p2", a=7, b=1))
    assert wait_for(lambda: rec2.settled, timeout_ms=3000)
    assert rec2.finished == [8]

    wait_for(lambda: not svc._detached, timeout_ms=4000)


def test_has_active_tasks(qt_app):
    svc = TaskService()
    assert not svc.has_active_tasks()

    rec = Recorder(svc.submit(lenta, owner="p1", marca="x", retardo=0.2))
    assert svc.has_active_tasks()

    assert wait_for(lambda: rec.settled)
    assert not svc.has_active_tasks()


def sale_del_programa():
    raise SystemExit(3)


def test_systemexit_en_la_tarea_no_bloquea_la_cola(qt_app):
    # SystemExit hereda de BaseException, no de Exception. Hasta el 30 de
    # septiembre de 2026 se escapaba: la tarea no emitia ninguna senal y la
    # siguiente nunca arrancaba.
    svc = TaskService()
    rec = Recorder(svc.submit(sale_del_programa, owner="p1"))
    rec2 = Recorder(svc.submit(suma, owner="p2", a=4, b=4))

    assert wait_for(lambda: rec.settled and rec2.settled)
    assert rec.failed == ["SystemExit: 3"] and not rec.finished and rec.cancelled == 0
    assert rec2.finished == [8]
    assert not svc.has_active_tasks()


def test_sin_ctx_no_se_inyecta_nada(qt_app):
    svc = TaskService()
    rec = Recorder(svc.submit(suma, owner="p1", a=10, b=5))
    assert wait_for(lambda: rec.settled)
    assert rec.finished == [15]


_MUCHAS_TAREAS = """
import sys, time
from PyQt5.QtCore import QCoreApplication
app = QCoreApplication([])
from core.services.task_service import TaskService
svc = TaskService()
n = int(sys.argv[1])
hechas = []
for i in range(n):
    svc.submit(lambda i=i: i, owner=f"p{i}").finished.connect(hechas.append)
limite = time.monotonic() + 60
while (svc.has_active_tasks() or svc._threads) and time.monotonic() < limite:
    app.processEvents()
print(len(hechas), len(svc._threads))
"""


def test_muchas_tareas_cortas_no_tumban_la_aplicacion():
    # Hasta el 30 de septiembre de 2026 el servicio soltaba cada QThread apenas
    # llegaba su resultado, a veces antes de que el hilo saliera, y Qt abortaba
    # el proceso ("QThread: Destroyed while thread is still running"). Con 3.000
    # tareas pasaba en 13 de 20 corridas. Corre en un proceso aparte para que,
    # si vuelve, falle esta prueba y no se caiga toda la sesion de pytest.
    n = 10_000
    env = dict(os.environ, QT_FORCE_STDERR_LOGGING="1")
    r = subprocess.run([sys.executable, "-c", _MUCHAS_TAREAS, str(n)],
                       cwd=Path(__file__).resolve().parents[2], env=env,
                       capture_output=True, text=True, timeout=120)

    assert "QThread: Destroyed" not in r.stderr, "Qt destruyo un hilo que seguia corriendo"
    assert r.returncode == 0, r.stderr[-800:]
    assert r.stdout.split() == [str(n), "0"], "no terminaron todas o quedaron hilos sin liberar"

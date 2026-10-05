import inspect
import itertools
import threading

from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal


DEFAULT_CANCEL_TIMEOUT_MS = 2000


class TaskContext:

    def __init__(self, cancel_event, report_progress):
        self._cancel_event = cancel_event
        self._report_progress = report_progress

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def progress(self, percent: int, message: str = "") -> None:
        if self._cancel_event.is_set():
            return
        self._report_progress(int(percent), str(message))


class TaskHandle(QObject):

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, task_id: str, owner: str, service):
        super().__init__()
        self.id = task_id
        self.owner = owner
        self._service = service

    def cancel(self) -> None:
        self._service._cancel(self.id)


class _Task:

    def __init__(self, task_id, fn, kwargs, owner, handle):
        self.id = task_id
        self.fn = fn
        self.kwargs = kwargs
        self.owner = owner
        self.handle = handle
        self.cancel_event = threading.Event()
        self.state = "queued"
        self.worker = None


class _Worker(QThread):

    done = pyqtSignal(str, object, object)

    def __init__(self, task: _Task, ctx):
        super().__init__()
        self._task = task
        self._ctx = ctx

    def run(self):
        task = self._task
        kwargs = dict(task.kwargs)
        if self._ctx is not None:
            kwargs["ctx"] = self._ctx
        try:
            result, error = task.fn(**kwargs), None
        except BaseException as e:
            # BaseException y no Exception: un SystemExit dentro de la tarea no
            # emitiria `done`, y la cola quedaria bloqueada para siempre.
            result, error = None, e
        self.done.emit(task.id, result, error)


class TaskService(QObject):

    # La emite submit() con el TaskHandle recien creado. Existe para que la
    # interfaz pueda mostrar progreso y ofrecer Cancelar sin que cada plugin
    # tenga que acordarse de engancharse (requisito R04, problema nº 9).
    task_started = pyqtSignal(object)

    def __init__(self, cancel_timeout_ms: int = DEFAULT_CANCEL_TIMEOUT_MS):
        super().__init__()
        self._cancel_timeout_ms = cancel_timeout_ms
        self._ids = itertools.count(1)
        self._queue = []
        self._running = None
        self._detached = {}
        # Cada hilo se conserva hasta que Qt emite su propio QThread.finished.
        # Soltarlo antes (al llegar `done`, que se emite todavia dentro de run())
        # puede destruir un QThread que aun no salio, y Qt aborta toda la
        # aplicacion con "QThread: Destroyed while thread is still running".
        self._threads = set()

    def submit(self, fn, *, owner: str, **kwargs) -> TaskHandle:
        self._discard_queued_from(owner)

        task_id = f"t{next(self._ids)}"
        handle = TaskHandle(task_id, owner, self)
        task = _Task(task_id, fn, kwargs, owner, handle)

        self._queue.append(task)
        # Antes de arrancar, para que quien escuche ya tenga el handle conectado
        # cuando empiecen a llegar las señales de progreso.
        self.task_started.emit(handle)
        self._start_next_if_idle()
        return handle

    def cancel_all_from(self, owner: str) -> int:
        affected = self._discard_queued_from(owner)
        if self._running is not None and self._running.owner == owner:
            self._cancel(self._running.id)
            affected += 1
        return affected

    def has_active_tasks(self) -> bool:
        return self._running is not None or bool(self._queue)

    def pending_count(self) -> int:
        return len(self._queue)

    def _discard_queued_from(self, owner: str) -> int:
        keep, dropped = [], []
        for task in self._queue:
            (dropped if task.owner == owner else keep).append(task)
        self._queue = keep
        for task in dropped:
            task.state = "cancelled"
            task.handle.cancelled.emit()
        return len(dropped)

    def _start_next_if_idle(self) -> None:
        if self._running is not None or not self._queue:
            return

        task = self._queue.pop(0)
        task.state = "running"
        self._running = task

        ctx = None
        if _accepts_ctx(task.fn):
            ctx = TaskContext(
                task.cancel_event,
                lambda pct, msg, h=task.handle: h.progress.emit(pct, msg),
            )

        worker = _Worker(task, ctx)
        task.worker = worker
        self._threads.add(worker)
        worker.done.connect(self._on_worker_done)
        # Se conecta antes de start(): una tarea muy corta puede terminar
        # antes de que se alcance a conectar despues.
        worker.finished.connect(self._release_thread)
        worker.start()

    def _release_thread(self) -> None:
        worker = self.sender()
        self._threads.discard(worker)
        worker.deleteLater()

    def _cancel(self, task_id: str) -> None:
        for task in self._queue:
            if task.id == task_id:
                self._queue.remove(task)
                task.state = "cancelled"
                task.handle.cancelled.emit()
                return

        task = self._running
        if task is None or task.id != task_id or task.state != "running":
            return

        task.cancel_event.set()
        QTimer.singleShot(self._cancel_timeout_ms,
                          lambda tid=task_id: self._detach_if_still_running(tid))

    def _detach_if_still_running(self, task_id: str) -> None:
        # Salida de emergencia del R46, no un descuido: la tarea ignoro la
        # cancelacion durante cancel_timeout_ms. Se deja de esperarla para
        # devolver la interfaz y seguir con la cola; el hilo puede seguir vivo
        # y lo que devuelva se descarta en _on_worker_done. Python no ofrece
        # forma segura de matar un hilo desde afuera.
        task = self._running
        if task is None or task.id != task_id or task.state != "running":
            return

        task.state = "cancelled"
        self._running = None
        if task.worker is not None:
            self._detached[task_id] = task.worker
        task.handle.cancelled.emit()
        self._start_next_if_idle()

    def _on_worker_done(self, task_id, result, error) -> None:
        # El hilo no se libera aqui sino en _release_thread, cuando ya salio de run().
        if self._detached.pop(task_id, None) is not None:
            return

        task = self._running
        if task is None or task.id != task_id:
            return

        self._running = None
        task.worker = None

        if task.cancel_event.is_set():
            task.state = "cancelled"
            task.handle.cancelled.emit()
        elif error is not None:
            task.state = "done"
            detalle = str(error)
            task.handle.failed.emit(
                f"{type(error).__name__}: {detalle}" if detalle else type(error).__name__)
        else:
            task.state = "done"
            task.handle.finished.emit(result)

        self._start_next_if_idle()


def _accepts_ctx(fn) -> bool:
    try:
        return "ctx" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False

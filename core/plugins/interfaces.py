from abc import ABC, abstractmethod
import sys

from core import kernel
from core.kernel import Kernel
from core.plugins.meta import PluginMeta
from core.utils.plugin_alerts import PluginAlerts
from core.services.data_store import DataStore
from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset
from PyQt5.QtWidgets import QWidget




class IPlugin(ABC):
    
    def __init__(self, meta: PluginMeta) -> None:
        self.meta: PluginMeta = meta
        self.started: bool = False
        self.mainwin = None
        self.widget: QWidget = None  # Where the PyQt UI is rendered
        self.kernel: Kernel = None
        self.active_signal: SignalDataset = None
        self.active_chanel = None
        self.alerts = PluginAlerts()
        # Trials que uso la ultima operacion (core.utils.trial_labels.trials_used);
        # se guarda con los parametros del analisis en el proyecto.
        self._trials_used: dict | None = None

        
        
    # ===== Getters read from YAML =====
    def name(self) -> str:
        """Display name for UI (from properties.yml)."""
        return self.meta.name

    def category(self) -> str:
        """Plugin category (from properties.yml)."""
        return self.meta.category

    def subcategory(self) -> str:
        """Plugin subcategory (from properties.yml)."""
        return self.meta.subcategory

    def description(self) -> str:
        """Short help text shown as tooltip (from properties.yml)."""
        return self.meta.description or ""

    def icon(self) -> str:
        """
        Absolute path to the icon (inside the plugin folder).
        MainWindow expects a path to build QIcon(icon_path).
        """
        return str(self.meta.icon_path())
    
    def _log(self, *args):
        print(f"[{self.meta.name}]", *args)
        sys.stdout.flush()

    def _notify(self, msg: str, level: str = "info"):
        """Mensaje breve en la barra de estado, coloreado por severidad.

        `info` se queda solo en la barra; `warning` y `error` ademas pasan por
        `self.alerts`, para que no se pierdan entre los mensajes de progreso.
        """
        if level in ("warning", "error"):
            self.alerts.show(level, msg)
        try:
            if self.mainwin:
                if hasattr(self.mainwin, "show_status"):
                    self.mainwin.show_status(msg, level, 3000 if level == "info" else 6000)
                else:
                    self.mainwin.statusBar().showMessage(msg, 3000)
                return
        except Exception:
            pass
        self._log(msg)


    def get_datastore(self) -> DataStore | None:
        """Obtain the DataStore service from the kernel."""
        try:
            if not self.mainwin:
                self.alerts.error("MainWindow not found to access the DataStore.")
                return None
            store: DataStore | None = self.mainwin.kernel.get_service("DataStore")
            if store is None:
                self.alerts.error("DataStore service not found.")
            return store
        except Exception as e:
            self.alerts.error(f"Error accessing DataStore: {e}")
            return None

    def run_task(self, fn, on_done, *, on_failed=None, on_cancelled=None, on_finished=None, **kwargs):
        """Runs `fn(**kwargs)` in the TaskService and calls `on_done(result)` on the UI thread.

        This is the one place that knows the task pattern (R70/R71): queue, progress bar
        and Cancel come with the service, and the four signals are connected here with
        the "is this still my current task?" guard, so a plugin only writes its compute
        function (pure: arrays in, arrays out, optional `ctx` kwarg) and its drawing.

        - A new call cancels the one still running for this plugin.
        - `on_finished()` runs after done, failed or cancelled (re-enable buttons...).
        - Without a TaskService (headless tests) `fn` runs inline, with the same callbacks.
        """
        def fallo(msg):
            if on_failed is not None:
                on_failed(msg)
            else:
                self.alerts.error(f"No se pudo calcular: {msg}")

        tasks = self.kernel.get_service("TaskService") if self.kernel else None
        if tasks is None:
            try:
                result = fn(**kwargs)
            except Exception as e:
                fallo(str(e))
            else:
                if result is not None:
                    on_done(result)
            finally:
                if on_finished is not None:
                    on_finished()
            return None

        tasks.cancel_all_from(self.meta.id)
        handle = tasks.submit(fn, owner=self.meta.id, **kwargs)
        self._task_handle = handle

        def vigente():
            return handle is getattr(self, "_task_handle", None)

        def terminar():
            self._task_handle = None
            if on_finished is not None:
                on_finished()

        def al_progreso(pct, msg):
            if vigente():
                self._notify(f"{msg} ({pct}%)" if msg else f"{pct}%")

        def al_terminar(result):
            if not vigente():
                return
            terminar()
            if result is not None:
                on_done(result)

        def al_fallar(msg):
            if not vigente():
                return
            terminar()
            fallo(msg)

        def al_cancelar():
            if not vigente():
                return
            terminar()
            if on_cancelled is not None:
                on_cancelled()

        handle.progress.connect(al_progreso)
        handle.finished.connect(al_terminar)
        handle.failed.connect(al_fallar)
        handle.cancelled.connect(al_cancelar)
        return handle

    def mark_project_dirty(self):

        try:
            store = self.kernel.get_service("DataStore") if self.kernel else None
            project = store.get("_project_service") if store else None
            if project is not None:
                project.mark_dirty()
            if self.mainwin and hasattr(self.mainwin, "_update_title_bar_project_name"):
                self.mainwin._update_title_bar_project_name()
        except Exception:
            pass

    def get_active_signal(self, silent: bool = False) -> SignalDataset | None:

        try:
            store = self.get_datastore()
            if not store:
                return None
            ds = store.get_active_signal()
            if not ds:
                if not silent:
                    self.alerts.warning("No signal has been loaded.")
                return None
            self.active_signal = ds
            return ds
        except Exception as e:
            self.alerts.error(f"Error obtaining the signal: {e}")
            return None

    def get_active_trials(self, signal: SignalDataset | None = None) -> TrialDataset | None:
        """Return the active trials for the current signal."""
        try:
            sig = signal or self.active_signal or self.get_active_signal()
            if sig is None:
                return None

            td : TrialDataset = self.active_signal.get_active_trials(sig.name, None)
            if td is None or td.trials.size == 0:
                self.alerts.warning(f"There are no active trials for {sig.name}.")
                return None
        

            return td

        except Exception as e:
            self.alerts.error(f"Error obtaining trials: {e}")
            return None

    def get_trials_de_canal(self, channel_name: str,
                            signal: SignalDataset | None = None) -> TrialDataset | None:
        """Los trials de **un canal concreto**, no los del último generado.

        `get_active_trials` devuelve siempre el canal activo, que es lo que
        quieren los análisis de un canal. PPC necesita dos a la vez, así que
        tiene que poder nombrarlos.

        El usuario genera los trials del canal 1, después los del canal 2 —el
        plugin *Trials* corta uno por vez— y los dos quedan guardados. Para que
        PPC sirva de algo, **los dos cortes tienen que ser el mismo**: mismos
        `onsets`, mismo `t0`/`t1` y mismo umbral, cambiando solo el canal. Si no,
        los trials no están alineados muestra a muestra y la diferencia de fase
        no significa nada. Quien llame a esto lo comprueba antes de calcular.

        Devuelve `None` y avisa si ese canal no tiene trials, que es el caso
        normal de «todavía no los has generado».
        """
        try:
            sig = signal or self.active_signal or self.get_active_signal()
            if sig is None:
                return None

            td: TrialDataset = sig.get_active_trials(sig.name, channel_name)
            if td is None or td.trials.size == 0:
                self.alerts.warning(
                    f"El canal '{channel_name}' no tiene trials generados. "
                    f"Genéralos en Trials antes de usarlo aquí.")
                return None
            return td

        except Exception as e:
            self.alerts.error(f"Error al obtener los trials del canal '{channel_name}': {e}")
            return None

    # ===== Trial actual (indicador global de la barra de titulo) =====
    def _active_trials_quiet(self):
        """(senal, trials activos) sin avisar al usuario si faltan."""
        try:
            store = self.kernel.get_service("DataStore") if self.kernel else None
            sig = store.get_active_signal() if store else None
            if sig is None:
                return None, None
            return sig, sig.get_active_trials(sig.name, None)
        except Exception:
            return None, None

    def build_trial_state(self, mode: str, *, position: int = None, positions=None,
                          total: int = None, channel: str = None, discarded: bool = False,
                          original_index: int = None, note: str = None) -> dict:
        """Estado del trial actual con la numeracion de la aplicacion:
        posicion base 1 entre los trials validos.

        `mode`: "single" (un trial), "average" (promedio), "all" (todos los
        validos), "selection" (subconjunto) o "none" (no hay trials).
        """
        if total is None or channel is None:
            _, td = self._active_trials_quiet()
            if td is not None:
                if total is None:
                    total = int(td.trials.shape[1])
                if channel is None:
                    channel = td.channel_name
        return {
            "plugin": self.name(),
            "mode": mode,
            "position": position,
            "positions": None if positions is None else sorted({int(p) for p in positions}),
            "total": int(total or 0),
            "channel": channel,
            "discarded": bool(discarded),
            "original_index": original_index,
            "note": note,
        }

    def publish_current_trial(self, mode: str = None, **kwargs):
        """Publica en que trial se esta trabajando: lo guarda en el DataStore
        (`current_trial`) y emite `current_trial_changed`. La ventana principal
        solo lo muestra si viene del plugin visible.

        Sin argumentos publica `self.current_trial_state()`, que es lo normal:
        el plugin describe su estado en un solo sitio y avisa cuando cambia.
        """
        state = self.current_trial_state() if mode is None else self.build_trial_state(mode, **kwargs)
        if state is None:
            return None
        try:
            store = self.kernel.get_service("DataStore") if self.kernel else None
            if store is not None:
                store.set("current_trial", state)
            if self.kernel is not None:
                self.kernel.emit_event("current_trial_changed", state)
        except Exception as e:
            self._log("publish_current_trial error:", e)
        return state

    def trial_state_from_used(self, used: dict, channel: str = None) -> dict:
        """Estado del indicador a partir de un registro `trials_used`."""
        mode = used.get("mode") or "selection"
        positions = used.get("positions") or []
        total = used.get("total_valid")
        channel = channel or used.get("channel")
        if mode == "single" and positions:
            return self.build_trial_state("single", position=positions[0], total=total, channel=channel)
        if mode in ("average", "all"):
            return self.build_trial_state(mode, total=total, channel=channel)
        return self.build_trial_state("selection", positions=positions, total=total, channel=channel)

    def current_trial_state(self) -> dict | None:
        """Lo que el indicador debe mostrar cuando este plugin esta visible.

        Por defecto: los trials que uso la ultima operacion de este plugin
        (`self._trials_used`), si siguen correspondiendo a los trials actuales;
        si no, todos los validos del canal activo, que es lo que usa la mayoria
        de los analisis. Los plugins con selector de trial lo sobrescriben.
        """
        _, td = self._active_trials_quiet()
        if td is None:
            return None
        total = int(td.trials.shape[1])
        used = self._trials_used
        if (used and used.get("total_valid") == total
                and used.get("channel") in (None, td.channel_name)):
            return self.trial_state_from_used(used, td.channel_name)
        return self.build_trial_state("all", total=total, channel=td.channel_name)

    def on_kernel_event(self, topic: str, payload: object):

    
        if topic == "signal_active_changed" or topic =="signal_added":
            print(f"Signal changed/added: {payload}")
            self.active_signal = self.get_active_signal() 

    def initialize(self, kernel):

        self.kernel = kernel
        self._log("Initializing")

    def start(self, kernel: kernel):
        """
        Initialize the plugin with the kernel and register for active-signal change events.

        :param kernel: The kernel the plugin depends on.
        :return: None
        """
        
        self.mainwin = kernel.get_service("MainWindow")
        self.kernel.event.connect(self.on_kernel_event)

        if self.mainwin:
            self.started = True
            self._log("Plugin started.")
            
    @abstractmethod
    def stop(self):
        """Invoked when the kernel stops plugins."""
        pass

    @abstractmethod
    def get_widget(self, parent=None):
        """Return the widget associated with the plugin."""
        pass

    @abstractmethod
    def process(self, data: any):
        """Process data sent by the kernel or other plugins."""
        pass

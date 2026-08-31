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


'''
Interfaces for plugins and services — the contract and communication system
between plugins and the kernel.
'''

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

    def icon(self) -> str:
        """
        Absolute path to the icon (inside the plugin folder).
        MainWindow expects a path to build QIcon(icon_path).
        """
        return str(self.meta.icon_path())
    
    def _log(self, *args):
        print(f"[{self.meta.name}]", *args)
        sys.stdout.flush()

    def _notify(self, msg: str):
        try:
            if self.mainwin:
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
                self.alerts.warning("DataStore service not found.")
            return store
        except Exception as e:
            self.alerts.error(f"Error accessing DataStore: {e}")
            return None

    def get_active_signal(self) -> SignalDataset | None:
        """Return the active signal or None if not available."""
        try:
            store = self.get_datastore()
            if not store:
                return None
            ds = store.get_active_signal()
            if not ds:
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
        
    def on_kernel_event(self, topic: str, payload: object):

        """
        Listen to events emitted by the Kernel.

        Invoked when a kernel event occurs; receives the topic and payload.

        Used for events relevant to the plugin, e.g., active signal changes or new data added.

        :param topic: Event topic
        :param payload: Event payload
        :return: None
        """
        if topic == "signal_active_changed" or topic =="signal_added":
            print(f"Signal changed/added: {payload}")
            self.active_signal = self.get_active_signal() 

    def initialize(self, kernel):
        """
        Initialize the plugin with the kernel.

        :param kernel: The kernel the plugin depends on.
        :return: None
        """
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

# core/kernel.py
from PyQt5.QtCore import QObject, pyqtSignal
import sys
import importlib
import os

class Kernel(QObject):
  
    event = pyqtSignal(str, object)  # General events
    plugin_registered = pyqtSignal(str)  # Emitted when a plugin is registered


    def __init__(self):
        super().__init__()
        self._plugins = {}
        self._services = {}

    def register_plugin(self, name, plugin):
        if name in self._plugins:
            print(f"Plugin '{name}' is already registered; it will be overwritten.")
        print(f"Registering plugin: {name}")
        # Add the plugin to the plugins dict
        self._plugins[name] = plugin

        # Verify plugin has initialize() and call it
        if hasattr(plugin, "initialize"):
            try:
                plugin.initialize(self)
            except Exception as e:
                print(f"Error initializing plugin '{name}':", e)

        # Emit the plugin-registered event
        self.plugin_registered.emit(name)

    # Get all registered plugin names
    def get_plugins(self):
        return list(self._plugins.keys())
    
    # Get a plugin by name
    def get_plugin(self, name):
        return self._plugins.get(name)

    # Get all plugins by category
    def get_plugins_by_category(self, category: str):
        return [name for name, p in self._plugins.items() if hasattr(p, "category") and p.category() == category]

    

    # Dynamically load and register a plugin
    def load_and_register(self, name: str, module_path: str, class_name: str):
        """
        Dynamically load a plugin from a Python module and register it.
        - name: name to register the plugin with
        - module_path: module path (e.g., 'plugins.my_plugin')
        - class_name: class name inside the module
        """
        try:
            if module_path in sys.modules:
                del sys.modules[module_path]

            module = importlib.import_module(module_path)
            PluginClass = getattr(module, class_name)
            plugin_instance = PluginClass()
            self.register_plugin(name, plugin_instance)
            return True
        except Exception as e:
            print(f"ERROR: could not load plugin '{name}' from {module_path}: {e}")
            return False
        
    '''
    def execute(self, name, data=None):
        """
        Execute a 'process(data)' method on the specified plugin.
        """
        if name in self._plugins:
            plugin = self._plugins[name]
            if hasattr(plugin, "process"):
                plugin.process(data)
                return {"success": True, "message": f"Plugin '{name}' executed."}
            else:
                return {"success": False, "message": f"Plugin '{name}' has no process() method."}
        else:
            msg = f"ERROR: plugin '{name}' is not registered."
            print(msg)
            return {"success": False, "message": msg}
    '''

    def stop_plugins(self):
        for plugin in self._plugins.values():
            plugin.stop()

    def register_service(self, key, service):
        self._services[key] = service

    def get_service(self, key):
        return self._services.get(key)

    def emit_event(self, topic, payload=None):
        self.event.emit(topic, payload)

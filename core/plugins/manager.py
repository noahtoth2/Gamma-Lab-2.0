from pathlib import Path
from typing import Dict, Tuple
from core.plugins.loader import discover
from core.plugins.meta import PluginMeta
from core.plugins.interfaces import IPlugin

class PluginManager:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.registry: Dict[str, Tuple[PluginMeta, IPlugin]] = {}

    def load_all(self, on_progress=None) -> None:
        # on_progress(index, total, name) is optional, used by the splash screen
        found = discover(self.plugins_dir)
        for i, (meta, PluginCls) in enumerate(found, start=1):
            plugin = PluginCls(meta)
            self.registry[meta.id] = (meta, plugin)
            if on_progress:
                on_progress(i, len(found), meta.name)

    def all(self):
        return list(self.registry.values())

    def get(self, plugin_id: str) -> Tuple[PluginMeta, IPlugin]:
        return self.registry[plugin_id]
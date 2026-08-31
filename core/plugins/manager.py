from pathlib import Path
from typing import Dict, Tuple
from core.plugins.loader import discover
from core.plugins.meta import PluginMeta
from core.plugins.interfaces import IPlugin

class PluginManager:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.registry: Dict[str, Tuple[PluginMeta, IPlugin]] = {}

    def load_all(self) -> None:
        for meta, PluginCls in discover(self.plugins_dir):
            plugin = PluginCls(meta)
            self.registry[meta.id] = (meta, plugin)

    def all(self):
        return list(self.registry.values())

    def get(self, plugin_id: str) -> Tuple[PluginMeta, IPlugin]:
        return self.registry[plugin_id]
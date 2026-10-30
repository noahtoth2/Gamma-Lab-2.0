from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class PluginMeta:
    id: str
    name: str
    category: str
    subcategory: str
    version: str
    icon: str 
    logic_class: str
    ui_class: Optional[str] = None
    description: str = ""
    root: Optional[Path] = None
    saves_analysis: bool = False
    order: Optional[int] = None
    subcategory_order: Optional[int] = None
    free_graphics: bool = True

    def icon_path(self) -> Path:
        assert self.root is not None, "PluginMeta.root not set"
        return (self.root / self.icon).resolve()
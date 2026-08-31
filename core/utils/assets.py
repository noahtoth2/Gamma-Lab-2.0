import os
from PyQt5.QtGui import QIcon

from core.plugins.meta import PluginMeta

def icon_from_plugin(meta: PluginMeta) -> QIcon:
    p = meta.icon_path()
    return QIcon(str(p)) if p.exists() else QIcon()
# main.py
from pathlib import Path
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFontDatabase, QFont, QIcon
from PyQt5.QtCore import Qt, QTimer, QCoreApplication

import resources_rc

from core.kernel import Kernel
from app.view.main_window import MainWindow
from core.plugins.manager import PluginManager
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService




def main():
    # On Windows, set AppUserModelID so the taskbar uses our icon
    if sys.platform == 'win32':
        try:
            import ctypes  # type: ignore
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('GammaLab.DesktopApp')
        except Exception:
            pass

        # ⚡ Esto debe ir antes de crear QApplication
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    # Set application icon (taskbar, Alt-Tab). Prefer embedded resource, fallback to file path.
    icon = QIcon(":/assets/logos/app-logo.png")
    if icon.isNull():
        icon = QIcon("assets/logos/app-logo.png")
    app.setWindowIcon(icon)
   
    fid = QFontDatabase.addApplicationFont(":/assets/fonts/Inter.ttf")
    families = QFontDatabase.applicationFontFamilies(fid)
    default_family = families[0] if families else "Inter"
    
    app.setFont(QFont(default_family, 10))
    app.setStyleSheet(loadStyleSheet())
    
    kernel = Kernel()

    # 1) Core services
    kernel.register_service("DataStore", DataStore())
    kernel.register_service("FileIO", FileIOService())

    # 2) Discover and instantiate plugins
    plugins_dir = Path(__file__).resolve().parent / "plugins"
    pm = PluginManager(plugins_dir)
    pm.load_all()

    # 3) Register plugins in the kernel BY NAME (from properties.yml)
    for meta, plugin in pm.all():
        try:
            kernel.register_plugin(meta.name, plugin)
        except Exception as e:
            print(f"Could not register '{meta.name}':", e)

    # 4) Main window (after registering plugins)
    main_win = MainWindow(kernel)
    kernel.register_service("MainWindow", main_win)

    def show_startup_window():
        # Restore from minimized state and maximize while keeping window chrome visible
        main_win.setWindowState((main_win.windowState() & ~Qt.WindowMinimized) | Qt.WindowMaximized)
        main_win.show()
        main_win.raise_()
        main_win.activateWindow()

    # Run once the event loop starts so Windows does not re-minimize the window
    QTimer.singleShot(0, show_startup_window)
    sys.exit(app.exec_())


def loadStyleSheet():
    with open("assets/styles/styles.qss", "r") as f:
        return f.read()

if __name__ == "__main__":
    main()

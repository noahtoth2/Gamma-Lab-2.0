import os
from pathlib import Path
import sys

from core.utils.rutas import asegurar_salida_estandar
asegurar_salida_estandar()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFontDatabase, QFont, QIcon
from PyQt5.QtCore import Qt, QTimer, QCoreApplication

import resources_rc

from core.kernel import Kernel
from app.view.main_window import MainWindow
from app.view.splash_screen import SplashScreen
from core.plugins.manager import PluginManager
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService
from core.services.task_service import TaskService
from core.services.compartidos import registrar_servicios_compartidos
from core.utils.vtk_context_menu import VTKContextMenu
from core.utils import vtk_temporizador
from core.utils.rutas import carpeta_del_programa, ruta_de_proyecto




def main():
    proyecto = ruta_de_proyecto(sys.argv[1:])
    os.chdir(carpeta_del_programa())
    vtk_temporizador.instalar()
    if sys.platform == 'win32':
        try:
            import ctypes  # type: ignore
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('GammaLab.DesktopApp')
        except Exception:
            pass

       
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    icon = QIcon(":/assets/logos/app-logo.png")
    if icon.isNull():
        icon = QIcon("assets/logos/app-logo.png")
    app.setWindowIcon(icon)
   
    fid = QFontDatabase.addApplicationFont(":/assets/fonts/Inter.ttf")
    families = QFontDatabase.applicationFontFamilies(fid)
    default_family = families[0] if families else "Inter"
    
    app.setFont(QFont(default_family, 10))
    app.setStyleSheet(loadStyleSheet())

    splash = SplashScreen()
    splash.show()
    splash.set_progress(5, "Initializing core...")

    kernel = Kernel()

    splash.set_progress(10, "Registering services...")
    kernel.register_service("DataStore", DataStore())
    kernel.register_service("FileIO", FileIOService())
    kernel.register_service("TaskService", TaskService())
    registrar_servicios_compartidos(kernel)
    VTKContextMenu.kernel = kernel

    plugins_dir = carpeta_del_programa() / "plugins"
    splash.set_progress(20, "Discovering plugins...")
    pm = PluginManager(plugins_dir)
    pm.load_all(on_progress=lambda i, n, name: splash.set_progress(
        30 + int(40 * i / n), f"Loading plugin: {name}"))

    splash.set_progress(75, "Registering plugins...")
    for meta, plugin in pm.all():
        try:
            kernel.register_plugin(meta.name, plugin)
        except Exception as e:
            print(f"Could not register '{meta.name}':", e)

    splash.set_progress(85, "Building interface...")
    main_win = MainWindow(kernel)
    kernel.register_service("MainWindow", main_win)
    splash.set_progress(100, "Ready")

    def show_startup_window():
        main_win.setWindowState((main_win.windowState() & ~Qt.WindowMinimized) | Qt.WindowMaximized)
        main_win.show()
        splash.finish(main_win)
        main_win.raise_()
        main_win.activateWindow()

    QTimer.singleShot(0, show_startup_window)
    
    if proyecto:
        QTimer.singleShot(0, lambda: main_win.abrir_proyecto_desde_ruta(proyecto))
    salida_autoprueba = os.environ.get("GAMMALAB_AUTOPRUEBA")
    if not salida_autoprueba:
        QTimer.singleShot(600, main_win.mostrar_bienvenida_inicial)
    if salida_autoprueba:
        from core.utils import autoprueba
        autoprueba.programar(main_win, kernel, salida_autoprueba, espera_proyecto=bool(proyecto))
    sys.exit(app.exec_())


def loadStyleSheet():
    with open("assets/styles/styles.qss", "r") as f:
        return f.read()

if __name__ == "__main__":
    main()

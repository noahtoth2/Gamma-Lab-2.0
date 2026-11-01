# main.py
import os
from pathlib import Path
import sys

from core.utils.rutas import asegurar_salida_estandar
asegurar_salida_estandar()   # antes que nada: sin consola, print() y flush() se caen

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
    # Windows lanza el programa desde la carpeta del archivo que se abrió con doble clic, y la
    # interfaz carga sus imágenes con rutas relativas ("assets/..."): se resuelven desde aquí.
    proyecto = ruta_de_proyecto(sys.argv[1:])   # (absoluta, antes de cambiar de carpeta)
    os.chdir(carpeta_del_programa())
    # Antes de crear ningun widget de VTK: le pone al temporizador de
    # QVTKRenderWindowInteractor la guarda que le falta, que es lo que
    # cerraba la aplicacion al cambiar de pestana (nº 24).
    vtk_temporizador.instalar()
    # On Windows, set AppUserModelID so the taskbar uses our icon
    if sys.platform == 'win32':
        try:
            import ctypes  # type: ignore
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('GammaLab.DesktopApp')
        except Exception:
            pass

       
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

    splash = SplashScreen()
    splash.show()
    splash.set_progress(5, "Initializing core...")

    kernel = Kernel()

    # 1) Core services
    # Van antes del descubrimiento de plugins: register_plugin() llama a
    # initialize(kernel), y desde ahi un plugin ya puede pedir cualquier
    # servicio. Si estas lineas se mueven despues, recibiria None.
    splash.set_progress(10, "Registering services...")
    kernel.register_service("DataStore", DataStore())
    kernel.register_service("FileIO", FileIOService())
    kernel.register_service("TaskService", TaskService())
    registrar_servicios_compartidos(kernel)   # R69: una sola instancia de ajustes, exportación y medición
    VTKContextMenu.kernel = kernel

    # 2) Discover and instantiate plugins
    plugins_dir = carpeta_del_programa() / "plugins"
    splash.set_progress(20, "Discovering plugins...")
    pm = PluginManager(plugins_dir)
    pm.load_all(on_progress=lambda i, n, name: splash.set_progress(
        30 + int(40 * i / n), f"Loading plugin: {name}"))

    # 3) Register plugins in the kernel BY NAME (from properties.yml)
    splash.set_progress(75, "Registering plugins...")
    for meta, plugin in pm.all():
        try:
            kernel.register_plugin(meta.name, plugin)
        except Exception as e:
            print(f"Could not register '{meta.name}':", e)

    # 4) Main window (after registering plugins)
    splash.set_progress(85, "Building interface...")
    main_win = MainWindow(kernel)
    kernel.register_service("MainWindow", main_win)
    splash.set_progress(100, "Ready")

    def show_startup_window():
        # Restore from minimized state and maximize while keeping window chrome visible
        main_win.setWindowState((main_win.windowState() & ~Qt.WindowMinimized) | Qt.WindowMaximized)
        main_win.show()
        splash.finish(main_win)
        main_win.raise_()
        main_win.activateWindow()

    # Run once the event loop starts so Windows does not re-minimize the window
    QTimer.singleShot(0, show_startup_window)
    
    if proyecto:
        QTimer.singleShot(0, lambda: main_win.abrir_proyecto_desde_ruta(proyecto))
    salida_autoprueba = os.environ.get("GAMMALAB_AUTOPRUEBA")
    if salida_autoprueba:
        from core.utils import autoprueba
        autoprueba.programar(main_win, kernel, salida_autoprueba, espera_proyecto=bool(proyecto))
    sys.exit(app.exec_())


def loadStyleSheet():
    with open("assets/styles/styles.qss", "r") as f:
        return f.read()

if __name__ == "__main__":
    main()

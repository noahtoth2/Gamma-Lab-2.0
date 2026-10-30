"""Autoprueba del programa instalado (R39).

Con la variable de entorno GAMMALAB_AUTOPRUEBA=<archivo.json>, el programa espera a que
termine de abrir el proyecto que recibió, calcula un FFT, crea la ventana de ayuda y
escribe en ese archivo qué funcionó. Una aplicación sin consola no puede decirlo de otra forma.
"""
import json
import time
import traceback

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

ESPERA_MAXIMA_S = 60


def programar(main_win, kernel, ruta_salida, espera_proyecto):
    """Empieza a comprobar cuando arranca el bucle de eventos."""
    estado = {"inicio": time.time(), "resultado": {"plugins": sorted(kernel.get_plugins())}}

    def terminar():
        try:
            with open(ruta_salida, "w", encoding="utf-8") as f:
                json.dump(estado["resultado"], f, indent=2, ensure_ascii=False)
        finally:
            QApplication.quit()

    def esperar_proyecto():
        r = estado["resultado"]
        ds = kernel.get_service("DataStore").get_active_signal()
        if espera_proyecto and ds is None and time.time() - estado["inicio"] < ESPERA_MAXIMA_S:
            QTimer.singleShot(300, esperar_proyecto)
            return
        r["proyecto"] = main_win.project_service.project_name
        r["senal"] = getattr(ds, "name", None)
        comprobar_fft(r)
        comprobar_ayuda(r)
        terminar()

    def comprobar_fft(r):
        try:
            fft = kernel.get_plugin("FFT")
            fft.start(kernel)
            fft.get_widget(parent=main_win.plugin_area)
            fft._on_calculate_clicked()
            tareas = kernel.get_service("TaskService")
            t0 = time.time()
            while (tareas.has_active_tasks() or tareas.pending_count()) and time.time() - t0 < 60:
                QApplication.processEvents()
                time.sleep(0.01)
            QApplication.processEvents()
            r["fft"] = getattr(fft, "chart", None) is not None
        except Exception:
            r["fft"] = False
            r["fft_error"] = traceback.format_exc()[-600:]

    def comprobar_ayuda(r):
        try:
            ayuda = kernel.get_plugin("Help")
            ayuda.start(kernel)
            r["ayuda"] = ayuda.get_widget(parent=main_win.plugin_area) is not None
        except Exception:
            r["ayuda"] = False
            r["ayuda_error"] = traceback.format_exc()[-600:]

    QTimer.singleShot(1500, esperar_proyecto)

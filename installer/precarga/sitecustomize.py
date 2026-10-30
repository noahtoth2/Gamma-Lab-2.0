"""Se importa solo al arrancar Python si esta carpeta está en PYTHONPATH (lo hace construir.bat).

PyQt5 trae msvcp140.dll 14.26 en PyQt5/Qt5/bin. Si un proceso la carga antes que la del sistema,
NumPy, SciPy o VTK se caen con una violación de acceso en ese DLL. PyInstaller importa todos los
paquetes en un mismo proceso para descubrir sus DLL, así que se carga primero la del sistema.
"""
import ctypes
import os

if os.name == "nt":
    for nombre in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll"):
        try:
            ctypes.WinDLL(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", nombre))
        except OSError:
            pass

"""Rutas que dependen de cómo se ejecuta la aplicación (R39).

Instalada, el código queda en una carpeta de solo lectura (Program Files); lo que
la aplicación escribe va a la carpeta de datos del usuario. Al hacer doble clic en
un `.glab`, Windows ejecuta `GammaLab.exe "ruta.glab"`: `ruta_de_proyecto` lo encuentra.
"""
import os
import sys
from pathlib import Path

NOMBRE_CARPETA = "GammaLab"


def carpeta_del_programa():
    """Donde están `assets/` y `plugins/`: la carpeta del paquete instalado o la raíz del repositorio."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def carpeta_inicial():
    """Carpeta por defecto de los diálogos de archivo: la del usuario, no la desde la que se lanzó el programa."""
    return str(Path.home())


def carpeta_de_datos():
    """La carpeta GammaLab dentro de %APPDATA%, creada si hace falta. Si no se puede crear, la carpeta del código."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    ruta = os.path.join(base, NOMBRE_CARPETA)
    try:
        os.makedirs(ruta, exist_ok=True)
        return ruta
    except OSError:
        return str(Path(__file__).resolve().parents[2])


def asegurar_salida_estandar():
    """Una aplicación sin consola (la instalada) arranca con sys.stdout y sys.stderr en None y
    cualquier `print(...); flush()` se cae. Se redirigen a un registro en la carpeta de datos del usuario.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return None
    ruta = os.path.join(carpeta_de_datos(), "gamma_lab.log")
    try:
        registro = open(ruta, "w", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        registro = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = registro
    if sys.stderr is None:
        sys.stderr = registro
    return ruta


def ruta_de_proyecto(argumentos):
    """El primer argumento que es un archivo `.glab` existente, o None."""
    for argumento in argumentos:
        if argumento.lower().endswith(".glab") and os.path.isfile(argumento):
            return os.path.abspath(argumento)
    return None

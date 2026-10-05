"""Lectura de archivos de señal, para el orquestador.

Es la parte de `open_file_dialog` que de verdad tarda. Corre en el TaskService y
no toca el Kernel, el DataStore ni ningún widget: recibe una ruta y devuelve un
SignalDataset. El diálogo de archivos, los avisos y el registro en el DataStore
se quedan en el hilo de la interfaz.

El Escenario de Calidad 2 del SAD pide explícitamente que «la lectura corre en el
servicio de tareas, fuera del hilo de la UI», sin condicionarlo al tamaño del
archivo. Con el archivo de prueba la carga mide 82,5 ms, por debajo del umbral de
100 ms de la Fase 4, pero el requisito no depende de eso.
"""
from pathlib import Path

from core.services.fileio_service import FileIOService

EXTENSIONES = (".abf", ".edf", ".mat")


def cargar_senal(ctx, ruta, fileio=None):
    """Lee el archivo de `ruta` y devuelve su SignalDataset, o None si se canceló.

    `fileio` permite reusar el servicio que ya tiene el Kernel; si no llega, se
    crea uno. `FileIOService` no guarda estado, así que usarlo desde el hilo
    trabajador es seguro.
    """
    if ctx.cancelled:
        return None

    nombre = Path(ruta).name
    extension = Path(ruta).suffix.lower()
    servicio = fileio if fileio is not None else FileIOService()

    ctx.progress(0, f"Leyendo {nombre}")

    if extension == ".abf":
        ds = servicio.load_abf(str(ruta))
    elif extension == ".edf":
        ds = servicio.load_edf(str(ruta))
    elif extension == ".mat":
        ds = servicio.load_mat(str(ruta))
    else:
        raise ValueError(
            f"Formato no soportado: {extension or '(sin extensión)'}. "
            f"Se admiten {', '.join(EXTENSIONES)}.")

    # La lectura entra en código C de pyabf/pyedflib y no vuelve hasta terminar,
    # así que la cancelación solo puede atenderse en los extremos.
    if ctx.cancelled:
        return None

    ctx.progress(100, f"{nombre} leído")
    return ds

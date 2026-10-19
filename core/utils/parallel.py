import ctypes
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_HILOS = 4
PRESUPUESTO_BYTES = 3_000_000_000
_CANCELADO = object()


def memoria_disponible():
    """Bytes de RAM libres en Windows, o None si no se puede saber."""
    if os.name != "nt":
        return None

    class _Estado(ctypes.Structure):
        _fields_ = [("largo", ctypes.c_ulong), ("carga", ctypes.c_ulong),
                    ("total_fisica", ctypes.c_ulonglong), ("libre_fisica", ctypes.c_ulonglong),
                    ("total_paginacion", ctypes.c_ulonglong), ("libre_paginacion", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("libre_virtual", ctypes.c_ulonglong),
                    ("libre_virtual_ext", ctypes.c_ulonglong)]

    estado = _Estado()
    estado.largo = ctypes.sizeof(_Estado)
    try:
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
            return None
    except Exception:
        return None
    return int(estado.libre_fisica)


def n_hilos(n_items, max_hilos=MAX_HILOS, bytes_por_item=0, presupuesto=PRESUPUESTO_BYTES):
    """Hilos a usar: nunca más que items, `max_hilos`, la mitad de los núcleos,
    ni los que caben en la memoria si cada item en vuelo ocupa `bytes_por_item`.
    La memoria es el menor entre `presupuesto` y un cuarto de la RAM libre."""
    nucleos = os.cpu_count() or 1
    libre = memoria_disponible()
    if libre:
        presupuesto = min(presupuesto, libre // 4)
    por_memoria = int(presupuesto // bytes_por_item) if bytes_por_item else n_items
    return max(1, min(n_items, max_hilos, nucleos // 2, por_memoria))


def map_ordenado(fn, items, ctx=None, max_hilos=MAX_HILOS, etiqueta="Trial", bytes_por_item=0):
    """Aplica `fn` a cada item repartiéndolos entre hilos.

    Devuelve los resultados en el mismo orden que `items`, o None si `ctx` canceló.
    Si algún item falla se relanza el error del primero (por orden), no del primero
    en terminar. Con un solo hilo corre en el hilo que llama, sin pool.
    """
    items = list(items)
    total = len(items)
    n = n_hilos(total, max_hilos, bytes_por_item)

    def cancelado():
        return ctx is not None and ctx.cancelled

    def avance(hechos):
        if ctx is not None:
            ctx.progress(int(100 * hechos / total), f"{etiqueta} {hechos}/{total}")

    if n <= 1:
        salida = []
        for k, item in enumerate(items, 1):
            if cancelado():
                return None
            salida.append(fn(item))
            avance(k)
        return salida

    def trabajo(item):
        return _CANCELADO if cancelado() else fn(item)

    with ThreadPoolExecutor(max_workers=n, thread_name_prefix="gamma-par") as pool:
        futuros = [pool.submit(trabajo, item) for item in items]
        hechos = 0
        for f in as_completed(futuros):
            if f.cancelled():
                continue
            hechos += 1
            if f.exception() is not None or cancelado():
                pool.shutdown(wait=False, cancel_futures=True)
            else:
                avance(hechos)

    for f in futuros:
        if not f.cancelled() and f.exception() is not None:
            raise f.exception()
    if cancelado():
        return None
    salida = [f.result() for f in futuros]
    return None if any(r is _CANCELADO for r in salida) else salida

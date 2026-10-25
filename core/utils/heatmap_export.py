"""Las tablas de un mapa de calor (escalograma, comodulograma) para exportar.

Un escalograma de 790 frecuencias por 6 000 instantes son casi cinco millones de
celdas. CSV y JSON los escriben en segundos, pero Excel tarda del orden de un
minuto en guardarlos y no admite más de 16 384 columnas. Para Excel se toma
entonces una de cada `k` columnas de tiempo y se **deja escrito en la hoja
Resumen** cuánto se recortó; CSV y JSON llevan siempre la matriz completa.
"""
import numpy as np

# Celdas que Excel escribe en unos diez segundos
MAX_CELDAS_XLSX = 1_000_000
MAX_COLUMNAS_XLSX = 16_000


def _num(x):
    x = float(x)
    return x if np.isfinite(x) else None


def secciones_de_mapa(parametros, resumen, frecuencias, tiempos, matriz, fmt,
                      nombre="Mapa", etiqueta_x="t", unidad_x="s"):
    """Arma las secciones para `ExportService.export_sections`.

    `matriz` es (frecuencia, tiempo); `frecuencias` en Hz, una por fila.
    """
    matriz = np.asarray(matriz)
    frecuencias = np.asarray(frecuencias, dtype=float).ravel()
    tiempos = np.asarray(tiempos, dtype=float).ravel()
    resumen = [list(r) for r in resumen]

    paso = 1
    if fmt == "xlsx":
        paso = max(int(np.ceil(matriz.size / MAX_CELDAS_XLSX)),
                   int(np.ceil(matriz.shape[1] / MAX_COLUMNAS_XLSX)), 1)
    columnas = np.arange(0, matriz.shape[1], paso)
    if paso > 1:
        resumen.append(["excel_columnas_recortadas",
                        f"1 de cada {paso} columnas ({columnas.size} de {matriz.shape[1]}); "
                        f"CSV y JSON llevan la matriz completa"])

    encabezado = ["frecuencia_hz"] + [f"{etiqueta_x}_{tiempos[c]:.4f}{unidad_x}" for c in columnas]
    filas = [[_num(f)] + [_num(v) for v in fila[columnas]] for f, fila in zip(frecuencias, matriz)]
    return {
        "Parametros": (["parametro", "valor"], [[k, v] for k, v in parametros.items()]),
        "Resumen": (["medida", "valor"], resumen),
        nombre: (encabezado, filas),
    }

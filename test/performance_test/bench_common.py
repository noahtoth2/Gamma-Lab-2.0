# test/performance_test/bench_common.py
"""
Utilidades compartidas por toda la suite de benchmarks de rendimiento.

Cómo se usa (ver README.md para el detalle completo):

    1. Correr la suite contra el código actual y ponerle una etiqueta:

           # PowerShell
           $env:GAMMA_PERF_LABEL = "gammalab_v1_2026-08-16"
           pytest test/performance_test -s

    2. Más adelante, correr la MISMA suite contra Gamma Lab 2.0 con otra etiqueta:

           $env:GAMMA_PERF_LABEL = "gammalab_v2_2026-09-XX"
           pytest test/performance_test -s

    3. Comparar ambas corridas:

           python test/performance_test/compare_report.py gammalab_v1_2026-08-16 gammalab_v2_2026-09-XX

Cada corrida se agrega a results/perf_results.json bajo su propia etiqueta -- las
etiquetas viejas nunca se pisan, salvo que se reutilice la misma etiqueta a propósito.
Este diseño es intencional: es lo que permite comparar "antes" (Gamma Lab 1.0) contra
"después" (Gamma Lab 2.0) sin perder ninguna corrida histórica.
"""

import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_FILE = RESULTS_DIR / "perf_results.json"

DEFAULT_LABEL = "baseline"

# Prefijo usado para las entradas que NO son un benchmark de tiempo (p. ej. el
# snapshot de entorno). compare_report.py las ignora al armar la tabla comparativa.
META_PREFIX = "_"


def current_label() -> str:
    """Etiqueta de la corrida actual, usada para agrupar resultados. Se controla con GAMMA_PERF_LABEL."""
    return os.environ.get("GAMMA_PERF_LABEL", DEFAULT_LABEL)


def time_block(fn, *args, reps: int = 5, warmup: int = 1, **kwargs) -> dict:
    """
    Ejecuta fn(*args, **kwargs) `warmup` veces (se descartan) y luego `reps` veces,
    cronometradas con un reloj monotónico de alta resolución (time.perf_counter).

    Devuelve estadísticas en segundos: min, mediana, media y max, más el valor de
    retorno de la última llamada (por si el test quiere validar el resultado).
    """
    for _ in range(max(0, warmup)):
        fn(*args, **kwargs)

    samples = []
    result = None
    for _ in range(max(1, reps)):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        samples.append(time.perf_counter() - t0)

    samples.sort()
    n = len(samples)
    mid = n // 2
    median = samples[mid] if n % 2 else (samples[mid - 1] + samples[mid]) / 2.0

    return {
        "reps": n,
        "min_s": samples[0],
        "median_s": median,
        "mean_s": sum(samples) / n,
        "max_s": samples[-1],
        "result": result,
    }


def _load_json() -> dict:
    if not RESULTS_FILE.exists():
        return {}
    try:
        return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(data: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def record(bench_name: str, stats: dict, *, label: str | None = None, extra: dict | None = None) -> None:
    """Guarda las estadísticas de un benchmark en results/perf_results.json, bajo `label`."""
    label = label or current_label()

    data = _load_json()

    entry = {k: v for k, v in stats.items() if k != "result"}
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    if extra:
        entry.update(extra)

    data.setdefault(label, {})[bench_name] = entry
    _write_json(data)

    print(
        f"[perf][{label}] {bench_name}: "
        f"min={entry['min_s']*1000:.1f}ms median={entry['median_s']*1000:.1f}ms "
        f"mean={entry['mean_s']*1000:.1f}ms (n={entry['reps']})"
    )


def load_results() -> dict:
    return _load_json()


def _package_version(module_name: str, attr: str = "__version__"):
    try:
        mod = __import__(module_name)
        return getattr(mod, attr)
    except Exception as e:  # pragma: no cover - solo informativo
        return f"no disponible ({e})"


def system_info() -> dict:
    """
    Snapshot del entorno de ejecución: SO, CPU lógicas, Python y versión de las
    librerías clave (numpy, scipy, VTK, Qt, PyWavelets, pyabf).

    Esto importa porque los tiempos de un benchmark NO son comparables entre dos
    máquinas distintas (o incluso la misma máquina con otra versión de VTK/numpy).
    Guardar el entorno junto a cada corrida deja registrado bajo qué condiciones se
    midió, para poder juzgar si una diferencia entre Gamma Lab 1.0 y 2.0 es un
    cambio real de rendimiento o solo un cambio de máquina/librerías.
    """
    info = {
        "python": platform.python_version(),
        "sistema_operativo": platform.platform(),
        "arquitectura": platform.machine(),
        "procesador": platform.processor() or platform.machine(),
        "cpus_logicas": os.cpu_count(),
    }

    try:
        import vtk
        info["vtk"] = vtk.VTK_VERSION
    except Exception as e:  # pragma: no cover
        info["vtk"] = f"no disponible ({e})"

    try:
        from PyQt5 import QtCore
        info["pyqt5_qt"] = QtCore.QT_VERSION_STR
    except Exception as e:  # pragma: no cover
        info["pyqt5_qt"] = f"no disponible ({e})"

    info["numpy"] = _package_version("numpy")
    info["scipy"] = _package_version("scipy")
    info["pywt"] = _package_version("pywt")
    info["pyabf"] = _package_version("pyabf")

    return info


def record_environment(*, label: str | None = None) -> dict:
    """
    Guarda system_info() dentro de results/perf_results.json, bajo la clave especial
    "_entorno" de la etiqueta actual (con el prefijo META_PREFIX para que
    compare_report.py la reconozca y la excluya de la tabla de benchmarks).
    """
    label = label or current_label()
    info = system_info()

    data = _load_json()
    data.setdefault(label, {})[f"{META_PREFIX}entorno"] = info
    _write_json(data)

    print(f"[perf][{label}] entorno registrado: {info}")
    return info

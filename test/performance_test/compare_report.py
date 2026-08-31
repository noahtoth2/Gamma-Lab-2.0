# test/performance_test/compare_report.py
"""
Imprime una tabla comparativa "antes/después" entre dos corridas de benchmarks
(identificadas por etiqueta) guardadas por test/performance_test/*.

Uso:
    python test/performance_test/compare_report.py gammalab_v1_2026-08-16 gammalab_v2_2026-09-XX

Este mismo script es el que se debe usar para comparar Gamma Lab 1.0 contra
Gamma Lab 2.0: mientras la etiqueta de la corrida de 2.0 se registre con el mismo
GAMMA_PERF_LABEL, no hace falta tocar este archivo -- solo correr la suite contra
el código nuevo y pasar las dos etiquetas aquí.

Si no se dan argumentos, compara las dos etiquetas registradas más recientemente
(la más antigua contra la más nueva, según el timestamp de su primera entrada).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_common import load_results, META_PREFIX  # noqa: E402


def _es_meta(nombre_benchmark: str) -> bool:
    """True para entradas que no son un benchmark de tiempo (p. ej. "_entorno")."""
    return nombre_benchmark.startswith(META_PREFIX)


def _pick_default_labels(data: dict):
    def first_ts(label):
        entries = [v for k, v in data[label].items() if not _es_meta(k)]
        return min((e.get("timestamp", "") for e in entries), default="")

    labels = sorted(data.keys(), key=first_ts)
    if len(labels) < 2:
        return None, None
    return labels[0], labels[-1]


def _print_environment(label: str, entry: dict) -> None:
    if not entry:
        return
    print(f"Entorno de {label!r}:")
    for k in ("sistema_operativo", "procesador", "cpus_logicas", "python", "vtk", "numpy", "scipy"):
        if k in entry:
            print(f"  {k}: {entry[k]}")
    print()


def main():
    data = load_results()
    if not data:
        print("No hay resultados. Corré los benchmarks primero, por ejemplo:")
        print('  $env:GAMMA_PERF_LABEL = "gammalab_v1_baseline"; pytest test/performance_test -s')
        return 1

    if len(sys.argv) >= 3:
        before_label, after_label = sys.argv[1], sys.argv[2]
    else:
        before_label, after_label = _pick_default_labels(data)

    if not before_label or not after_label:
        print("Se necesitan al menos dos corridas con etiqueta para comparar. Etiquetas registradas:", list(data.keys()))
        return 1
    if before_label not in data or after_label not in data:
        print(f"Etiqueta(s) desconocida(s). Etiquetas registradas: {list(data.keys())}")
        return 1

    before, after = data[before_label], data[after_label]

    _print_environment(before_label, before.get(f"{META_PREFIX}entorno"))
    _print_environment(after_label, after.get(f"{META_PREFIX}entorno"))

    names = sorted(n for n in (set(before) | set(after)) if not _es_meta(n))

    col_bench = max(28, max((len(n) for n in names), default=0) + 1)
    header = f"{'benchmark':<{col_bench}} {'antes (ms)':>12} {'despues (ms)':>13} {'factor':>10}"
    print(f"{before_label!r} -> {after_label!r}\n")
    print(header)
    print("-" * len(header))

    for name in names:
        b = before.get(name)
        a = after.get(name)
        b_ms = f"{b['median_s']*1000:.1f}" if b else "-"
        a_ms = f"{a['median_s']*1000:.1f}" if a else "-"
        if b and a and a["median_s"] > 0:
            factor = f"{b['median_s'] / a['median_s']:.2f}x"
        else:
            factor = "-"
        print(f"{name:<{col_bench}} {b_ms:>12} {a_ms:>13} {factor:>10}")

    print()
    print("factor > 1x  => mas rapido en 'despues' (mejora)")
    print("factor < 1x  => mas lento en 'despues' (regresion)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

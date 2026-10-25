"""Textos para indicar con que trials se trabaja.

Convencion de toda la aplicacion: un trial se nombra por su **posicion entre
los trials validos** (no descartados), empezando en 1. Es la numeracion que ya
usan ERP, PAC, MI y PSD, porque operan sobre `get_active_trials`, que quita los
descartados.
"""

from typing import Iterable, List, Optional


def compress_ranges(positions: Iterable[int]) -> str:
    """[1, 2, 3, 5, 8, 9] -> "1–3, 5, 8–9" (posiciones base 1)."""
    nums = sorted({int(p) for p in positions})
    if not nums:
        return ""
    partes: List[str] = []
    ini = fin = nums[0]
    for n in nums[1:]:
        if n == fin + 1:
            fin = n
            continue
        partes.append(str(ini) if ini == fin else f"{ini}–{fin}")
        ini = fin = n
    partes.append(str(ini) if ini == fin else f"{ini}–{fin}")
    return ", ".join(partes)


def describe_trials(positions: Optional[Iterable[int]], total: int) -> str:
    """Describe un conjunto de trials, en posiciones base 1 entre los validos.

    - `None`, o todos los trials -> "todos (18)"
    - uno solo                   -> "trial 3 de 18"
    - un subconjunto             -> "trials 1–5, 8 (6 de 18)"
    - vacio                      -> "ninguno (0 de 18)"
    """
    total = int(total or 0)
    if positions is None:
        return f"todos ({total})"
    nums = sorted({int(p) for p in positions})
    if total and nums == list(range(1, total + 1)):
        return f"todos ({total})"
    if not nums:
        return f"ninguno (0 de {total})"
    if len(nums) == 1:
        return f"trial {nums[0]} de {total}"
    return f"trials {compress_ranges(nums)} ({len(nums)} de {total})"


def describe_average(total: int) -> str:
    """Un promedio de todos los trials validos."""
    return f"promedio de todos ({int(total or 0)})"


def trials_used(positions: Optional[Iterable[int]], total: int, mode: str = None,
                channel: str = None) -> dict:
    """Registro serializable de los trials de una operacion, para
    `get_analysis_params()` y el manifiesto del proyecto."""
    lista = None if positions is None else sorted({int(p) for p in positions})
    total = int(total or 0)
    if lista is None:
        lista = list(range(1, total + 1))
    return {
        "numbering": "valid_position_1based",
        "positions": lista,
        "count": len(lista),
        "total_valid": total,
        "mode": mode or ("all" if len(lista) == total else "selection"),
        "label": describe_trials(lista, total) if mode != "average" else describe_average(total),
        "channel": channel,
    }

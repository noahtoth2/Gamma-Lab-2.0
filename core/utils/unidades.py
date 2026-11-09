"""Rótulos de ejes que dependen de la unidad de la señal."""


def etiqueta_psd(unidad: str) -> str:
    """El rótulo del eje de una densidad espectral de potencia: unidad² / Hz.

    Welch con `scaling='density'` devuelve la potencia en la unidad de la señal al
    cuadrado por hercio. Los tres plugins de PSD rotulaban el eje «V^2/Hz» fijo,
    aunque los registros de este laboratorio vienen en mV: el eje decía V²/Hz y los
    números eran mV²/Hz, un millón de veces más grandes de lo que el rótulo daba a
    entender.
    """
    unidad = (unidad or "").strip()
    if not unidad:
        return "PSD (unidad²/Hz)"
    if unidad.isalnum() or unidad in ("µV", "μV"):
        return f"PSD ({unidad}²/Hz)"
    return f"PSD (({unidad})²/Hz)"           # p. ej. «a.u.»: (a.u.)²/Hz

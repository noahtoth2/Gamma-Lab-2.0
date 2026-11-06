"""Descripciones emergentes de los controles de cada módulo (R42).

`completar_ayudas(raiz)` recorre los controles de un módulo y, a los que no traen descripción
propia, les pone una: la del diccionario `AYUDAS` si el control es de los habituales, y si no la
del rótulo que lo acompaña. Nunca reemplaza una descripción que el módulo ya declaró.
"""
import re

from PyQt5 import QtWidgets

TIPOS = (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox, QtWidgets.QCheckBox, QtWidgets.QRadioButton,
         QtWidgets.QPushButton, QtWidgets.QToolButton, QtWidgets.QSlider, QtWidgets.QListWidget)

AYUDAS = {
    "headerGenerateButton": "Calcula con los parámetros de este panel y dibuja el resultado.",
    "clearButton": "Restablece todos los parámetros de este panel a sus valores por defecto.",
    "sampleDensitySpinBox": "Frecuencia de muestreo a la que se calcula, en Hz. Se reduce la señal por un factor entero; 0 usa la del archivo.",
    "sampleFqSpinBox": "Frecuencia de muestreo a la que se calcula, en Hz.",
    "lowFrequencySpinBox": "Frecuencia mínima del rango de análisis, en Hz.",
    "highFrequencySpinBox": "Frecuencia máxima del rango de análisis, en Hz.",
    "windowComboBox": "Ventana que se aplica a cada segmento antes de calcular el espectro.",
    "npersegSpinBox": "Número de muestras de cada segmento del método de Welch. Más muestras dan más resolución en frecuencia.",
    "noverlapSpinBox": "Número de muestras que se solapan entre segmentos consecutivos.",
    "nfftSpinBox": "Número de puntos de la transformada de Fourier de cada segmento.",
    "detrendComboBox": "Cómo se quita la tendencia de cada segmento antes de calcular: ninguna, constante (media) o lineal.",
    "gainFactorComboBox": "Cómo se combinan los trials: promedio de sus espectros o suma de todos.",
    "cyclesSpinBox": "Número de ciclos de la wavelet. Más ciclos dan más resolución en frecuencia y menos en tiempo.",
    "normalizeCheckBox": "Normaliza el escalograma con el método elegido a la derecha.",
    "normalizeComboBox": "Método con el que se normaliza el escalograma.",
    "scaleCheckBox": "Cambia el tipo de escala con que se representa el escalograma.",
    "scaleComboBox": "Tipo de escala del escalograma.",
    "colorMinSpinBox": "Valor mínimo de la escala de color del escalograma.",
    "colorMaxSpinBox": "Valor máximo de la escala de color del escalograma.",
    "pacTypeComboBox": "Tipo de acoplamiento fase-amplitud: dentro de un canal o entre dos canales.",
    "ampLowFrequencySpinBox": "Frecuencia mínima de la banda de amplitud, en Hz.",
    "ampHighFrequencySpinBox": "Frecuencia máxima de la banda de amplitud, en Hz.",
    "fqP1SpinBox": "Frecuencia inicial de las bandas de fase, en Hz.",
    "fqP2SpinBox": "Frecuencia final de las bandas de fase, en Hz.",
    "pStepSpinBox": "Paso entre bandas de fase, en Hz.",
    "fqA1SpinBox": "Frecuencia inicial de las bandas de amplitud, en Hz.",
    "fqA2SpinBox": "Frecuencia final de las bandas de amplitud, en Hz.",
    "aStepSpinBox": "Paso entre bandas de amplitud, en Hz.",
    "prevTrialButton": "Pasa al trial anterior.",
    "nextTrialButton": "Pasa al trial siguiente.",
    "trialSpinBox": "Número del trial sobre el que se calcula.",
    "chkSelectAll": "Usa todos los trials válidos.",
    "chkSingleTrial": "Usa un solo trial, el que indica el número de al lado.",
    "spnSingleTrial": "Número del trial que se usa.",
    "chkUseRange": "Usa un rango de trials consecutivos, entre «From» y «To».",
    "spnFrom": "Primer trial del rango.",
    "spnTo": "Último trial del rango.",
    "lstTrials": "Marca los trials que participan. Los descartados no aparecen.",
    "mode_combo": "Método con el que se reemplaza el segmento de artefacto.",
    "trialNavButton": "Cambia el trial que se muestra.",
    "typeSelectComboBox": "Tipo de filtro. Se aplica pasa-banda de fase cero.",
    "orderSpinBox": "Orden del filtro. Un orden mayor corta con más pendiente.",
}

_SUFIJO = re.compile(r"(SpinBox|ComboBox|CheckBox|Button|Combo|Spin|Chk|Btn)$")


def _controles(raiz):
    return [c for c in raiz.findChildren(QtWidgets.QWidget)
            if isinstance(c, TIPOS) and c.objectName() != "qt_spinbox_lineedit"
            and not (c.parent() is not None and c.parent().inherits("QAbstractSpinBox"))]


def _rotulo_previo(control):
    """Texto del rótulo que precede al control en su fila, si lo hay."""
    padre = control.parentWidget()
    capa = padre.layout() if padre is not None else None
    pendientes = [capa] if capa is not None else []
    while pendientes:
        actual = pendientes.pop()
        for i in range(actual.count()):
            item = actual.itemAt(i)
            if item.widget() is control:
                for j in range(i - 1, -1, -1):
                    previo = actual.itemAt(j).widget()
                    if isinstance(previo, QtWidgets.QLabel) and previo.text().strip():
                        return previo.text().strip()
                return None
            if item.layout() is not None:
                pendientes.append(item.layout())
    return None


def descripcion_de(control):
    nombre = control.objectName()
    if nombre in AYUDAS:
        return AYUDAS[nombre]
    rotulo = _rotulo_previo(control)
    if rotulo:
        return f"{rotulo.rstrip(':')}."
    texto = getattr(control, "text", lambda: "")()
    if texto and texto.strip():
        return f"{texto.strip()}."
    if nombre:
        return _SUFIJO.sub("", nombre).replace("_", " ").strip().capitalize() + "."
    return None


def completar_ayudas(raiz):
    """Pone descripción emergente a los controles de `raiz` que no la tienen. Devuelve cuántos completó."""
    n = 0
    for control in _controles(raiz):
        if control.toolTip():
            continue
        texto = descripcion_de(control)
        if texto:
            control.setToolTip(texto)
            n += 1
    return n


def sin_ayuda(raiz):
    """Controles de `raiz` sin descripción emergente."""
    return [c for c in _controles(raiz) if not c.toolTip()]

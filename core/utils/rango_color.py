"""Rango de valores del color del escalograma (R33).

Por defecto el rango sale de los datos. Con "Color range" activado el usuario fija
mínimo y máximo, y los valores fuera del rango toman el color de los extremos.
Lo comparten Wavelet y Wavelet Average.
"""
import numpy as np
from PyQt5 import QtCore, QtWidgets


def limites_color(Z, manual=False, vmin=0.0, vmax=1.0):
    """(mínimo, máximo) del color. Un rango manual inválido (máx <= mín) cae al automático."""
    if manual and float(vmax) > float(vmin):
        return float(vmin), float(vmax)
    lo, hi = np.round([np.min(Z), np.max(Z)], 2)
    return float(lo), float(hi)


def _fila(parent, layout, etiqueta, nombre, widget):
    fila = QtWidgets.QHBoxLayout()
    label = QtWidgets.QLabel(etiqueta, parent)
    label.setObjectName(nombre + "Label")
    label.setProperty("variant", "input")
    fila.addWidget(label)
    widget.setObjectName(nombre)
    fila.addWidget(widget)
    if isinstance(widget, QtWidgets.QCheckBox):
        fila.setAlignment(widget, QtCore.Qt.AlignRight)
    layout.addLayout(fila)
    return label


def agregar_rango_color(ui, parent, layout):
    """Añade al panel "Color range" con casilla y límites Min / Max."""
    ui.colorRangeCheckBox = QtWidgets.QCheckBox(parent)
    ui.colorRangeCheckBox.setText("")
    ui.colorRangeCheckBox.setToolTip("Fix the minimum and maximum of the color scale. "
                                     "Values outside the range take the end colors.")
    ui.colorRangeLabel = _fila(parent, layout, "Color range", "colorRangeCheckBox", ui.colorRangeCheckBox)
    for nombre, texto in (("colorMinSpinBox", "Min"), ("colorMaxSpinBox", "Max")):
        spin = QtWidgets.QDoubleSpinBox(parent)
        spin.setRange(-1e12, 1e12)
        spin.setDecimals(4)
        spin.setStepType(QtWidgets.QAbstractSpinBox.AdaptiveDecimalStepType)
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setEnabled(False)
        setattr(ui, nombre, spin)
        _fila(parent, layout, texto, nombre, spin)
    ui.colorMaxSpinBox.setValue(1.0)
    ui.colorRangeCheckBox.toggled.connect(ui.colorMinSpinBox.setEnabled)
    ui.colorRangeCheckBox.toggled.connect(ui.colorMaxSpinBox.setEnabled)


def mostrar_rango_automatico(ui, vmin, vmax):
    """Pone en los cuadros el rango que salió de los datos, para partir de él al fijarlo."""
    if ui is None or ui.colorRangeCheckBox.isChecked():
        return
    for spin, v in ((ui.colorMinSpinBox, vmin), (ui.colorMaxSpinBox, vmax)):
        spin.blockSignals(True)
        spin.setValue(float(v))
        spin.blockSignals(False)


def leer_rango(ui):
    if ui is None:
        return False, 0.0, 1.0
    return ui.colorRangeCheckBox.isChecked(), ui.colorMinSpinBox.value(), ui.colorMaxSpinBox.value()


def guardar_rango(ui):
    manual, lo, hi = leer_rango(ui)
    return {"color_manual": manual, "color_min": lo, "color_max": hi}


def restaurar_rango(ui, params):
    ui.colorMinSpinBox.setValue(params.get("color_min", ui.colorMinSpinBox.value()))
    ui.colorMaxSpinBox.setValue(params.get("color_max", ui.colorMaxSpinBox.value()))
    ui.colorRangeCheckBox.setChecked(bool(params.get("color_manual", False)))

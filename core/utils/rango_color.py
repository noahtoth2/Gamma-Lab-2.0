"""Rango de valores del color de los mapas (R33).

Por defecto el rango sale de los datos. Con "Color range" activado el usuario fija
mínimo y máximo, y los valores fuera del rango toman el color de los extremos.
Lo comparten Wavelet, Wavelet Average, PAC y PPC.

El rango automático es el mínimo y el máximo **exactos** de los datos. Antes se
redondeaba a dos decimales, y con un registro en voltios (un escalograma de
1e-10 a 1,5e-4) quedaba en (0,0, 0,0): el mapa salía de un solo color.
"""
import warnings

import numpy as np
from PyQt5 import QtCore, QtWidgets

AVISO_RANGO_INVALIDO = ("El máximo del rango de color debe ser mayor que el mínimo; "
                        "se usa el rango automático.")


def limites_color(Z, manual=False, vmin=0.0, vmax=1.0, por_defecto=None):
    """(mínimo, máximo) del color.

    Un rango manual válido manda. Si no, `por_defecto` cuando el plugin tiene uno
    fijo (PPC usa 0-0,5, como MATLAB), y si tampoco, el mínimo y el máximo de los
    datos que no son NaN. Un rango manual inválido (máx <= mín) cae al automático.
    """
    if manual and float(vmax) > float(vmin):
        return float(vmin), float(vmax)
    if por_defecto is not None:
        return float(por_defecto[0]), float(por_defecto[1])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # todo NaN
        lo, hi = float(np.nanmin(Z)), float(np.nanmax(Z))
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return 0.0, 1.0
    if hi <= lo:
        # Un mapa plano: se abre un poco para que la escala tenga largo
        d = abs(lo) * 0.01 or 1.0
        return lo - d, hi + d
    return lo, hi


def rango_manual_invalido(ui):
    """True si el usuario activó el rango manual con un máximo que no supera al mínimo."""
    manual, lo, hi = leer_rango(ui)
    return manual and not float(hi) > float(lo)


def _decimales(vmin, vmax):
    """Decimales para que los cuadros muestren el rango: al menos 4, y 3 cifras de su ancho."""
    ancho = abs(float(vmax) - float(vmin)) or abs(float(vmax)) or 1.0
    return int(min(15, max(4, -np.floor(np.log10(ancho)) + 3)))


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
    """Añade al panel "Color range" con casilla y límites Min / Max.

    Los deja en `ui` y además los devuelve (casilla, mínimo, máximo), para que
    la interfaz pueda nombrarlos donde los crea.
    """
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
    return ui.colorRangeCheckBox, ui.colorMinSpinBox, ui.colorMaxSpinBox


def _tiene_rango(ui):
    return ui is not None and getattr(ui, "colorRangeCheckBox", None) is not None


def mostrar_rango_automatico(ui, vmin, vmax):
    """Pone en los cuadros el rango que salió de los datos, para partir de él al fijarlo.

    Los decimales se ajustan a la magnitud: con 4 fijos, un rango de 1e-5 se veía
    como 0,0000 y no se podía escribir.
    """
    if not _tiene_rango(ui) or ui.colorRangeCheckBox.isChecked():
        return
    decimales = _decimales(vmin, vmax)
    for spin, v in ((ui.colorMinSpinBox, vmin), (ui.colorMaxSpinBox, vmax)):
        spin.blockSignals(True)
        spin.setDecimals(decimales)
        spin.setValue(float(v))
        spin.blockSignals(False)


def leer_rango(ui):
    if not _tiene_rango(ui):
        return False, 0.0, 1.0
    return ui.colorRangeCheckBox.isChecked(), ui.colorMinSpinBox.value(), ui.colorMaxSpinBox.value()


def guardar_rango(ui):
    manual, lo, hi = leer_rango(ui)
    return {"color_manual": manual, "color_min": lo, "color_max": hi}


def recolorear(chart, lut):
    """Cambia la tabla de color de un mapa ya dibujado, sin rehacerlo.

    Así se conserva el zoom. Antes, cambiar el rango rehacía el gráfico entero
    y volvía a la vista completa. También actualiza la tabla que lee el EMF.
    """
    chart.SetTransferFunction(lut)
    chart.emf_color = lut


def mapa_en_pantalla(context_view):
    """El primer `vtkChartHistogram2D` de la escena, o None si todavía no hay mapa."""
    import vtk
    escena = context_view.GetScene() if context_view is not None else None
    if escena is None:
        return None
    for i in range(escena.GetNumberOfItems()):
        item = escena.GetItem(i)
        if isinstance(item, vtk.vtkChartHistogram2D):
            return item
    return None


def restaurar_rango(ui, params):
    if not _tiene_rango(ui):
        return
    for spin, clave in ((ui.colorMinSpinBox, "color_min"), (ui.colorMaxSpinBox, "color_max")):
        valor = params.get(clave)
        if valor is not None:
            spin.setDecimals(max(spin.decimals(), _decimales(0.0, valor)))
            spin.setValue(float(valor))
    ui.colorRangeCheckBox.setChecked(bool(params.get("color_manual", False)))

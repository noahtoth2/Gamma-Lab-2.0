"""Interfaz de PPC: el panel de parámetros y el área del gráfico.

`ppc_plugin.py` lee los widgets por nombre, así que esos nombres son el contrato
y no deben cambiar:

| Nombre | Tipo | Qué es |
|---|---|---|
| `plotArea` | `QFrame` | donde se mete el `QVTKRenderWindowInteractor` |
| `clearButton` | `QToolButton` | la escoba: devuelve los parámetros a su valor inicial |
| `createPpcButton` | `QPushButton` | *Generate*. Durante el cálculo pasa a *Computing...* |
| `channel1ComboBox` | `QComboBox` | canal 1; lo llena el plugin con los canales que tengan trials |
| `channel2ComboBox` | `QComboBox` | canal 2, igual |
| `sampleDensitySpinBox` | `QSpinBox` | remuestreo en Hz (`Resample` del MATLAB) |
| `lowFrequencySpinBox` | `QDoubleSpinBox` | `F min` |
| `highFrequencySpinBox` | `QDoubleSpinBox` | `F max` |
| `windowSpinBox` | `QDoubleSpinBox` | `wd`, la ventana **mínima** en segundos |
| `cyclesSpinBox` | `QDoubleSpinBox` | ciclos de la gaussiana (`ps_StDevCycles`) |

Los nombres repiten los de PAC donde el campo es el mismo
(`sampleDensitySpinBox`, `lowFrequencySpinBox`, `highFrequencySpinBox`,
`clearButton`, `plotArea`), para que no haya dos convenciones en el proyecto.

Las etiquetas van en inglés, como las de PAC, y cada control lleva su descripción
emergente (R42).

**Ojo con la etiqueta de `wd`.** En MATLAB `wd` es *la* ventana; aquí es la
ventana **mínima**, porque cada frecuencia usa la suya (decisión 10 del plan).
La etiqueta tiene que decirlo o se lee al revés.
"""
import os

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Ppc(object):

    def setupUi(self, PPC):
        PPC.setObjectName("PPC")
        PPC.resize(825, 609)

        self.mainWindow = QtWidgets.QHBoxLayout(PPC)
        self.mainWindow.setObjectName("mainWindow")
        self.mainWindow.setSpacing(0)

        self.splitter = QtWidgets.QSplitter(PPC)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.mainWindow.addWidget(self.splitter)

        # --- Izquierda: el gráfico
        self.plotArea = QtWidgets.QFrame(self.splitter)
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setObjectName("plotArea")

        # --- Derecha: cabecera fija y cuerpo con parámetros
        self.rightContainer = QtWidgets.QWidget(self.splitter)
        self.rightLayoutOuter = QtWidgets.QVBoxLayout(self.rightContainer)
        self.rightLayoutOuter.setContentsMargins(8, 0, 8, 0)

        self.headerLayout = QtWidgets.QHBoxLayout()
        self.parametersLabel = QtWidgets.QLabel(self.rightContainer)
        self.parametersLabel.setProperty("variant", "title")
        self.headerLayout.addWidget(self.parametersLabel)
        self.headerLayout.addStretch(1)

        self.clearButton = QtWidgets.QToolButton(self.rightContainer)
        icono = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                             "assets", "iconos", "clear.png")
        self.clearButton.setIcon(QtGui.QIcon(icono))
        self.clearButton.setIconSize(QtCore.QSize(28, 28))
        self.clearButton.setAutoRaise(True)
        self.headerLayout.addWidget(self.clearButton)
        self.headerLayout.addSpacing(10)

        self.createPpcButton = QtWidgets.QPushButton(self.rightContainer)
        self.createPpcButton.setObjectName("headerGenerateButton")
        self.headerLayout.addWidget(self.createPpcButton)
        self.rightLayoutOuter.addLayout(self.headerLayout)

        self.paramsLine = QtWidgets.QFrame(self.rightContainer)
        self.paramsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.paramsLine.setProperty("role", "section-divider")
        self.rightLayoutOuter.addWidget(self.paramsLine)

        self.scrollArea = QtWidgets.QScrollArea(self.rightContainer)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.layoutWidget = QtWidgets.QWidget()
        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setContentsMargins(0, 10, 0, 0)
        self.paramsLayout.setSpacing(12)
        self.scrollArea.setWidget(self.layoutWidget)
        self.rightLayoutOuter.addWidget(self.scrollArea)
        self.splitter.widget(1).setMaximumWidth(300)

        # --- Los campos
        self.channel1ComboBox = self._combo(
            "Channel 1", "First channel of the pair. Only channels that already have trials are listed.")
        self.channel2ComboBox = self._combo(
            "Channel 2", "Second channel of the pair. It must be different from channel 1 and its "
                         "trials must be cut with the same parameters.")
        self.sampleDensitySpinBox = self._entero(
            "Sample frequency (Hz)", "Rate the signal is downsampled to before the analysis.")
        self.lowFrequencySpinBox = self._decimal(
            "F min (Hz)", "Lowest frequency of the map.")
        self.highFrequencySpinBox = self._decimal(
            "F max (Hz)", "Highest frequency of the map. It cannot exceed half the sample frequency.")
        self.windowSpinBox = self._decimal(
            "Minimum window (s)", "Shortest analysis window. Each frequency uses its own window, "
                                  "never shorter than this one.")
        self.cyclesSpinBox = self._decimal(
            "Gaussian cycles", "Cycles of the Gabor wavelet. More cycles give a sharper frequency "
                               "and a blurrier time resolution.")

        self.paramsLayout.addStretch(1)
        self.retranslateUi(PPC)

    # --- Tres ayudas para no repetir el mismo bloque
    def _etiqueta(self, texto):
        lab = QtWidgets.QLabel(self.layoutWidget)
        lab.setText(texto)
        lab.setProperty("variant", "subtitle")
        self.paramsLayout.addWidget(lab)
        return lab

    def _combo(self, texto, ayuda=""):
        self._etiqueta(texto)
        w = QtWidgets.QComboBox(self.layoutWidget)
        w.setToolTip(ayuda)
        self.paramsLayout.addWidget(w)
        return w

    def _entero(self, texto, ayuda=""):
        self._etiqueta(texto)
        w = QtWidgets.QSpinBox(self.layoutWidget)
        w.setToolTip(ayuda)
        w.setRange(1, 1_000_000)
        self.paramsLayout.addWidget(w)
        return w

    def _decimal(self, texto, ayuda=""):
        self._etiqueta(texto)
        w = QtWidgets.QDoubleSpinBox(self.layoutWidget)
        w.setToolTip(ayuda)
        w.setDecimals(3)
        w.setRange(0.0, 100_000.0)
        self.paramsLayout.addWidget(w)
        return w

    def retranslateUi(self, PPC):
        _t = QtCore.QCoreApplication.translate
        PPC.setWindowTitle(_t("PPC", "PPC"))
        self.parametersLabel.setText(_t("PPC", "Parameters"))
        self.clearButton.setToolTip(_t("PPC", "Clear parameters"))
        self.createPpcButton.setText(_t("PPC", "Generate"))
        self.createPpcButton.setToolTip(_t("PPC", "Compute the phase consistency map between the two channels"))

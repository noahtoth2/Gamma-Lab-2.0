from PyQt5 import QtCore, QtGui, QtWidgets
import os

class Ui_Pac(object):

    def setupUi(self, PAC):
        PAC.setObjectName("PAC")
        PAC.resize(825, 609)

        self.mainWindow = QtWidgets.QHBoxLayout(PAC)
        self.mainWindow.setObjectName("mainWindow")
        self.mainWindow.setSpacing(0)

        self.splitter = QtWidgets.QSplitter(PAC)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.mainWindow.addWidget(self.splitter)

        # --- Left Area: Plot ---
        self.plotArea = QtWidgets.QFrame(self.splitter)
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setFrameShadow(QtWidgets.QFrame.Raised)
        self.plotArea.setObjectName("plotArea")

        # --- Right Area: Panel (fixed header + scrollable body) ---
        self.rightContainer = QtWidgets.QWidget(self.splitter)
        self.rightContainer.setObjectName("rightContainer")

        self.rightLayoutOuter = QtWidgets.QVBoxLayout(self.rightContainer)
        self.rightLayoutOuter.setContentsMargins(8, 0, 8, 0)
        self.rightLayoutOuter.setSpacing(0)

        # ===== Header: Parameters + clear + Create PAC (always visible) =====
        self.headerLayout = QtWidgets.QHBoxLayout()
        self.headerLayout.setContentsMargins(0, 0, 0, 5)

        self.parametersLabel = QtWidgets.QLabel(self.rightContainer)
        self.parametersLabel.setObjectName("parametersLabel")
        self.parametersLabel.setProperty("variant", "title")
        self.headerLayout.addWidget(self.parametersLabel)

        self.headerLayout.addStretch(1)

        # --- Clear/ broom button ---
        self.clearButton = QtWidgets.QToolButton(self.rightContainer)
        self.clearButton.setObjectName("clearButton")
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "assets", "iconos", "clear.png")
        self.clearButton.setIcon(QtGui.QIcon(icon_path))
        self.clearButton.setIconSize(QtCore.QSize(28, 28))
        self.clearButton.setAutoRaise(True)
        self.clearButton.setToolTip("Clear parameters")
        self.headerLayout.addWidget(self.clearButton)
        self.headerLayout.addSpacing(10)

        self.createPacButton = QtWidgets.QPushButton(self.rightContainer)
        self.createPacButton.setObjectName("headerGenerateButton")
        self.headerLayout.addWidget(self.createPacButton)

        self.rightLayoutOuter.addLayout(self.headerLayout)

        self.paramsLine = QtWidgets.QFrame(self.rightContainer)
        self.paramsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.paramsLine.setObjectName("paramsLine")
        self.paramsLine.setProperty("role", "section-divider")
        self.rightLayoutOuter.addWidget(self.paramsLine)

        # ===== Scrollable body =====
        self.scrollArea = QtWidgets.QScrollArea(self.rightContainer)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scrollArea.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.layoutWidget = QtWidgets.QWidget()
        self.layoutWidget.setObjectName("layoutWidget")

        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setObjectName("paramsLayout")
        self.paramsLayout.setContentsMargins(0, 10, 0, 0)
        self.paramsLayout.setSpacing(12)

        self.scrollArea.setWidget(self.layoutWidget)
        self.rightLayoutOuter.addWidget(self.scrollArea)

        self.splitter.widget(1).setMaximumWidth(300)

        # --- PAC type ---
        self.pacTypeLayout = QtWidgets.QVBoxLayout()
        self.pacTypeLayout.setObjectName("pacTypeLayout")

        self.pacTypeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.pacTypeLabel.setObjectName("pacTypeLabel")
        self.pacTypeLabel.setProperty("variant", "subtitle")
        self.pacTypeLayout.addWidget(self.pacTypeLabel)

        self.pacTypeLine = QtWidgets.QFrame(self.layoutWidget)
        self.pacTypeLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.pacTypeLine.setObjectName("pacTypeLine")
        self.pacTypeLine.setProperty("role", "divider")
        self.pacTypeLayout.addWidget(self.pacTypeLine)

        self.pacTypeComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.pacTypeComboBox.setObjectName("pacTypeComboBox")
        self.pacTypeComboBox.setProperty("variant", "input")
        self.pacTypeLayout.addWidget(self.pacTypeComboBox)
        self.paramsLayout.addLayout(self.pacTypeLayout)

        # --- Sample frequency ---
        self.sampleDensity = QtWidgets.QVBoxLayout()
        self.sampleDensity.setObjectName("sampleDensity")

        self.sampleDensityLabel = QtWidgets.QLabel(self.layoutWidget)
        self.sampleDensityLabel.setObjectName("sampleDensityLabel")
        self.sampleDensityLabel.setProperty("variant", "subtitle")
        self.sampleDensity.addWidget(self.sampleDensityLabel)

        self.sampleDensityLine = QtWidgets.QFrame(self.layoutWidget)
        self.sampleDensityLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.sampleDensityLine.setObjectName("sampleDensityLine")
        self.sampleDensityLine.setProperty("role", "divider")
        self.sampleDensity.addWidget(self.sampleDensityLine)

        self.sampleDensityInput = QtWidgets.QHBoxLayout()
        self.sampleDensityInput.setObjectName("sampleDensityInput")

        self.sampleDensitySpinBox = QtWidgets.QSpinBox(self.layoutWidget)
        self.sampleDensitySpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.sampleDensitySpinBox.setObjectName("sampleDensitySpinBox")
        self.sampleDensityInput.addWidget(self.sampleDensitySpinBox)

        self.hzLabel = QtWidgets.QLabel(self.layoutWidget)
        self.hzLabel.setObjectName("hzLabel")
        self.hzLabel.setProperty("variant", "input")

        self.sampleDensityInput.addWidget(self.hzLabel)
        self.sampleDensity.addLayout(self.sampleDensityInput)
        self.paramsLayout.addLayout(self.sampleDensity)

        # --- Phase band---
        self.PhaseBandLayout = QtWidgets.QVBoxLayout()
        self.PhaseBandLayout.setObjectName("PhaseBandLayout")

        self.PhaseBandLabel = QtWidgets.QLabel(self.layoutWidget)
        self.PhaseBandLabel.setObjectName("PhaseBandLabel")
        self.PhaseBandLabel.setProperty("variant", "subtitle")
        self.PhaseBandLayout.addWidget(self.PhaseBandLabel)

        self.PhaseBandLine = QtWidgets.QFrame(self.layoutWidget)
        self.PhaseBandLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.PhaseBandLine.setObjectName("PhaseBandLine")
        self.PhaseBandLine.setProperty("role", "divider")
        self.PhaseBandLayout.addWidget(self.PhaseBandLine)

        self.frequencyLayout = QtWidgets.QVBoxLayout()
        self.frequencyLayout.setObjectName("frequencyLayout")

        self.frequencyLabel = QtWidgets.QLabel(self.layoutWidget)
        self.frequencyLabel.setObjectName("frequencyLabel")
        self.frequencyLabel.setProperty("variant", "input")
        self.frequencyLayout.addWidget(self.frequencyLabel)

        # --- Fq p1 ---
        self.lowFqLayout = QtWidgets.QHBoxLayout()
        self.lowFqLayout.setObjectName("lowFqLayout")

        self.lowLabel = QtWidgets.QLabel(self.layoutWidget)
        self.lowLabel.setObjectName("lowLabel")
        self.lowLabel.setProperty("variant", "input")
        self.lowFqLayout.addWidget(self.lowLabel)

        self.lowFrequencySpinBox = QtWidgets.QDoubleSpinBox(self.layoutWidget)
        self.lowFrequencySpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.lowFrequencySpinBox.setObjectName("lowFrequencySpinBox")
        self.lowFqLayout.addWidget(self.lowFrequencySpinBox)

        self.hzLowFreqLabel = QtWidgets.QLabel(self.layoutWidget)
        self.hzLowFreqLabel.setObjectName("hzLowFreqLabel")
        self.hzLowFreqLabel.setProperty("variant", "input")
        self.lowFqLayout.addWidget(self.hzLowFreqLabel)

        self.frequencyLayout.addLayout(self.lowFqLayout)
    
        # --- Fq p2 ---
        self.highFqLayout = QtWidgets.QHBoxLayout()
        self.highFqLayout.setObjectName("highFqLayout")

        self.highLabel = QtWidgets.QLabel(self.layoutWidget)
        self.highLabel.setObjectName("highLabel")
        self.highLabel.setProperty("variant", "input")
        self.highFqLayout.addWidget(self.highLabel)

        self.highFrequencySpinBox = QtWidgets.QDoubleSpinBox(self.layoutWidget)
        self.highFrequencySpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.highFrequencySpinBox.setObjectName("highFrequencySpinBox")
        self.highFqLayout.addWidget(self.highFrequencySpinBox)

        self.hzHighFreqLabel = QtWidgets.QLabel(self.layoutWidget)
        self.hzHighFreqLabel.setObjectName("hzHighFreqLabel")
        self.hzHighFreqLabel.setProperty("variant", "input")
        self.highFqLayout.addWidget(self.hzHighFreqLabel)

        self.frequencyLayout.addLayout(self.highFqLayout)
        
        self.PhaseBandLayout.addLayout(self.frequencyLayout)
        self.paramsLayout.addLayout(self.PhaseBandLayout)

        # --- Amplitude band ---
        self.AmplitudeBandLayout = QtWidgets.QVBoxLayout()
        self.AmplitudeBandLayout.setObjectName("AmplitudeBandLayout")

        self.AmplitudeBandLabel = QtWidgets.QLabel(self.layoutWidget)
        self.AmplitudeBandLabel.setObjectName("AmplitudeBandLabel")
        self.AmplitudeBandLabel.setProperty("variant", "subtitle")
        self.AmplitudeBandLayout.addWidget(self.AmplitudeBandLabel)

        self.AmplitudeBandLine = QtWidgets.QFrame(self.layoutWidget)
        self.AmplitudeBandLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.AmplitudeBandLine.setObjectName("AmplitudeBandLine")
        self.AmplitudeBandLine.setProperty("role", "divider")
        self.AmplitudeBandLayout.addWidget(self.AmplitudeBandLine)

        self.ampFrequencyLayout = QtWidgets.QVBoxLayout()
        self.ampFrequencyLayout.setObjectName("ampFrequencyLayout")

        self.ampFrequencyLabel = QtWidgets.QLabel(self.layoutWidget)
        self.ampFrequencyLabel.setObjectName("ampFrequencyLabel")
        self.ampFrequencyLabel.setProperty("variant", "input")
        self.ampFrequencyLayout.addWidget(self.ampFrequencyLabel)

        # --- Fq a1 ---
        self.ampLowFqLayout = QtWidgets.QHBoxLayout()
        self.ampLowFqLayout.setObjectName("ampLowFqLayout")

        self.ampLowLabel = QtWidgets.QLabel(self.layoutWidget)
        self.ampLowLabel.setObjectName("ampLowLabel")
        self.ampLowLabel.setProperty("variant", "input")
        self.ampLowFqLayout.addWidget(self.ampLowLabel)

        self.ampLowFrequencySpinBox = QtWidgets.QDoubleSpinBox(self.layoutWidget)
        self.ampLowFrequencySpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.ampLowFrequencySpinBox.setObjectName("ampLowFrequencySpinBox")
        self.ampLowFqLayout.addWidget(self.ampLowFrequencySpinBox)

        self.hzAmpLowFreqLabel = QtWidgets.QLabel(self.layoutWidget)
        self.hzAmpLowFreqLabel.setObjectName("hzAmpLowFreqLabel")
        self.hzAmpLowFreqLabel.setProperty("variant", "input")
        self.ampLowFqLayout.addWidget(self.hzAmpLowFreqLabel)

        self.ampFrequencyLayout.addLayout(self.ampLowFqLayout)

        # --- Fq a2 ---
        self.ampHighFqLayout = QtWidgets.QHBoxLayout()
        self.ampHighFqLayout.setObjectName("ampHighFqLayout")

        self.ampHighLabel = QtWidgets.QLabel(self.layoutWidget)
        self.ampHighLabel.setObjectName("ampHighLabel")
        self.ampHighLabel.setProperty("variant", "input")
        self.ampHighFqLayout.addWidget(self.ampHighLabel)

        self.ampHighFrequencySpinBox = QtWidgets.QDoubleSpinBox(self.layoutWidget)
        self.ampHighFrequencySpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.ampHighFrequencySpinBox.setObjectName("ampHighFrequencySpinBox")
        self.ampHighFqLayout.addWidget(self.ampHighFrequencySpinBox)

        self.hzAmpHighFreqLabel = QtWidgets.QLabel(self.layoutWidget)
        self.hzAmpHighFreqLabel.setObjectName("hzAmpHighFreqLabel")
        self.hzAmpHighFreqLabel.setProperty("variant", "input")
        self.ampHighFqLayout.addWidget(self.hzAmpHighFreqLabel)

        self.ampFrequencyLayout.addLayout(self.ampHighFqLayout)

        self.AmplitudeBandLayout.addLayout(self.ampFrequencyLayout)
        self.paramsLayout.addLayout(self.AmplitudeBandLayout)



        # --- Spacer ---
        self.paramsLayout.addStretch(1)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(PAC)
        QtCore.QMetaObject.connectSlotsByName(PAC)

    def retranslateUi(self, PAC):
        _translate = QtCore.QCoreApplication.translate
        PAC.setWindowTitle(_translate("PAC", "PAC"))

        self.parametersLabel.setText(_translate("PAC", "Parameters"))
        self.sampleDensityLabel.setText(_translate("PAC", "Sample frequency"))
        self.hzLabel.setText(_translate("PAC", "Hz"))
        self.PhaseBandLabel.setText(_translate("PAC", "Phase Band"))
        self.frequencyLabel.setText(_translate("PAC", "Frequency (Hz)"))
        self.highLabel.setText(_translate("PAC", "P2"))
        self.hzHighFreqLabel.setText(_translate("PAC", "Hz"))
        self.lowLabel.setText(_translate("PAC", "P1"))
        self.hzLowFreqLabel.setText(_translate("PAC", "Hz"))
        self.pacTypeLabel.setText(_translate("PAC", "PAC Type"))
        self.AmplitudeBandLabel.setText(_translate("PAC", "Amplitude Band"))
        self.ampFrequencyLabel.setText(_translate("PAC", "Frequency (Hz)"))
        self.ampLowLabel.setText(_translate("PAC", "A1"))
        self.hzAmpLowFreqLabel.setText(_translate("PAC", "Hz"))
        self.ampHighLabel.setText(_translate("PAC", "A2"))
        self.hzAmpHighFreqLabel.setText(_translate("PAC", "Hz"))
        self.createPacButton.setText(_translate("PAC", "Generate"))
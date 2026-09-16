from PyQt5 import QtCore, QtGui, QtWidgets


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

        # Right Area: Panel
        self.scrollArea = QtWidgets.QScrollArea(self.splitter)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.layoutWidget = QtWidgets.QWidget(self.splitter)
        self.layoutWidget.setObjectName("layoutWidget")

        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setObjectName("paramsLayout")
        self.paramsLayout.setContentsMargins(8, 0, 8, 0)
        self.paramsLayout.setSpacing(12)

        self.scrollArea.setWidget(self.layoutWidget)
        self.splitter.widget(1).setMaximumWidth(300)

        # === Parameters Header ===
        self.parametersHeader = QtWidgets.QHBoxLayout()
        self.parametersHeader.setObjectName("parametersHeader")

        self.parametersLabel = QtWidgets.QLabel(self.layoutWidget)
        self.parametersLabel.setObjectName("parametersLabel")
        self.parametersLabel.setProperty("variant", "title")
        self.parametersHeader.addWidget(self.parametersLabel)

        self.parametersHeader.addStretch()

        # --- Clear/ broom button ---
        self.clearButton = QtWidgets.QToolButton(self.layoutWidget)
        self.clearButton.setObjectName("clearButton")
        self.clearButton.setText("🧹")
        self.parametersHeader.addWidget(self.clearButton)

        self.paramsLayout.addLayout(self.parametersHeader)

        # --- Driver below parameters ---
        self.paramsLine = QtWidgets.QFrame(self.layoutWidget)
        self.paramsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.paramsLine.setObjectName("paramsLine")
        self.paramsLine.setProperty("role", "section-divider")
        self.paramsLayout.addWidget(self.paramsLine)

        # --- Sample density ---
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

        # --- Trial Mode ---
        self.trialModeLayout = QtWidgets.QVBoxLayout()
        self.trialModeLayout.setObjectName("trialModeLayout")

        self.trialModeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.trialModeLabel.setObjectName("trialModeLabel")
        self.trialModeLabel.setProperty("variant", "subtitle")
        self.trialModeLayout.addWidget(self.trialModeLabel)

        self.trialModeLine = QtWidgets.QFrame(self.layoutWidget)
        self.trialModeLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.trialModeLine.setObjectName("trialModeLine")
        self.trialModeLine.setProperty("role", "divider")
        self.trialModeLayout.addWidget(self.trialModeLine)

        self.trialModeInput = QtWidgets.QHBoxLayout()
        self.trialModeInput.setObjectName("trialModeInput")

        self.trialModeComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.trialModeComboBox.setObjectName("trialModeComboBox")
        self.trialModeComboBox.setProperty("variant", "input")
        self.trialModeInput.addWidget(self.trialModeComboBox)

        self.trialModeLayout.addLayout(self.trialModeInput)
        self.paramsLayout.addLayout(self.trialModeLayout)



        # --- Button Create PAC ---
        self.paramsLayout.addStretch(1)

        self.createPacButton = QtWidgets.QPushButton(self.layoutWidget)
        self.createPacButton.setObjectName("mainActionButton")
        self.paramsLayout.addWidget(self.createPacButton)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(PAC)
        QtCore.QMetaObject.connectSlotsByName(PAC)

    def retranslateUi(self, PAC):
        _translate = QtCore.QCoreApplication.translate
        PAC.setWindowTitle(_translate("PAC", "PAC"))

        self.parametersLabel.setText(_translate("PAC", "Parameters"))
        self.sampleDensityLabel.setText(_translate("PAC", "Sample density"))
        self.hzLabel.setText(_translate("PAC", "Hz"))
        self.PhaseBandLabel.setText(_translate("PAC", "Phase Band"))
        self.frequencyLabel.setText(_translate("PAC", "Frequency (Hz)"))
        self.highLabel.setText(_translate("PAC", "F2"))
        self.hzHighFreqLabel.setText(_translate("PAC", "Hz"))
        self.lowLabel.setText(_translate("PAC", "F1"))
        self.hzLowFreqLabel.setText(_translate("PAC", "Hz"))
        self.trialModeLabel.setText(_translate("PAC", "Trial Mode"))
        self.createPacButton.setText(_translate("PAC", "Create PAC"))
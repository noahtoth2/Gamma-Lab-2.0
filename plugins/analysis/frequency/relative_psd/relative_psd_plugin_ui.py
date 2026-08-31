from PyQt5 import QtCore, QtWidgets

class Ui_Relative_psd(object):

    def setupUi(self, Form):
        Form.setObjectName("Form")

        # Layout principal del Form
        self.vbox = QtWidgets.QVBoxLayout(Form)
        self.vbox.setSpacing(0)

        self.scrollArea = QtWidgets.QScrollArea(Form)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.vbox.addWidget(self.scrollArea)

        self.layoutWidget = QtWidgets.QWidget()
        self.scrollArea.setWidget(self.layoutWidget)

        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setSpacing(12)

        # === Parameters Header ===
        self.parametersLabel = QtWidgets.QLabel(self.layoutWidget)
        self.parametersLabel.setObjectName("parametersLabel")
        self.parametersLabel.setProperty("variant", "title")
        self.paramsLayout.addWidget(self.parametersLabel)

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

        # --- Welch Parameters ---
        self.welchParameters = QtWidgets.QVBoxLayout()
        self.welchParameters.setObjectName("welchParameters")

        self.welchLabel = QtWidgets.QLabel(self.layoutWidget)
        self.welchLabel.setObjectName("welchLabel")
        self.welchLabel.setProperty("variant", "subtitle")
        self.welchParameters.addWidget(self.welchLabel)

        self.welchLine = QtWidgets.QFrame(self.layoutWidget)
        self.welchLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.welchLine.setObjectName("welchLine")
        self.welchLine.setProperty("role", "divider")
        self.welchParameters.addWidget(self.welchLine)

        # Window
        self.windowLayout = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.windowLayout.setObjectName("windowLayout")

        self.windowLabel = QtWidgets.QLabel(self.layoutWidget)
        self.windowLabel.setObjectName("windowLabel")
        self.windowLabel.setProperty("variant", "input")
        self.windowLayout.addWidget(self.windowLabel)

        self.windowComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.windowComboBox.setObjectName("windowComboBox")
        self.windowComboBox.addItems(["hann", "hamming", "blackman", "bartlett"])
        self.windowLayout.addWidget(self.windowComboBox)

        # N-per-seg
        self.npersegLayout = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.npersegLayout.setObjectName("npersegLayout")

        self.npersegLabel = QtWidgets.QLabel(self.layoutWidget)
        self.npersegLabel.setObjectName("npersegLabel")
        self.npersegLabel.setProperty("variant", "input")
        self.npersegLayout.addWidget(self.npersegLabel)

        self.npersegSpinBox = QtWidgets.QSpinBox(self.layoutWidget)
        self.npersegSpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.npersegSpinBox.setObjectName("npersegSpinBox")
        self.npersegLayout.addWidget(self.npersegSpinBox)
        
        # N-overlap
        self.noverlapLayout = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.noverlapLayout.setObjectName("noverlapLayout")

        self.noverlapLabel = QtWidgets.QLabel(self.layoutWidget)
        self.noverlapLabel.setObjectName("noverlapLabel")
        self.noverlapLabel.setProperty("variant", "input")
        self.noverlapLayout.addWidget(self.noverlapLabel)

        self.noverlapSpinBox = QtWidgets.QSpinBox(self.layoutWidget)
        self.noverlapSpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.noverlapSpinBox.setObjectName("noverlapSpinBox")
        self.noverlapLayout.addWidget(self.noverlapSpinBox)

        # N-FFT
        self.nfftLayout = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.nfftLayout.setObjectName("nfftLayout")

        self.nfftLabel = QtWidgets.QLabel(self.layoutWidget)
        self.nfftLabel.setObjectName("nfftLabel")
        self.nfftLabel.setProperty("variant", "input")
        self.nfftLayout.addWidget(self.nfftLabel)

        self.nfftSpinBox = QtWidgets.QSpinBox(self.layoutWidget)
        self.nfftSpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.nfftSpinBox.setObjectName("nfftSpinBox")
        self.nfftLayout.addWidget(self.nfftSpinBox)

        self.welchParameters.addLayout(self.windowLayout)
        self.welchParameters.addLayout(self.npersegLayout)
        self.welchParameters.addLayout(self.noverlapLayout)
        self.welchParameters.addLayout(self.nfftLayout)

        self.paramsLayout.addLayout(self.welchParameters, stretch=1)
        
        # --- Range ---
        self.rangeLayout = QtWidgets.QVBoxLayout()
        self.rangeLayout.setObjectName("rangeLayout")
        
        self.rangeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.rangeLabel.setObjectName("rangeLabel")
        self.rangeLabel.setProperty("variant", "subtitle")
        self.rangeLayout.addWidget(self.rangeLabel)

        self.rangeLine = QtWidgets.QFrame(self.layoutWidget)
        self.rangeLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.rangeLine.setObjectName("rangeLine")
        self.rangeLine.setProperty("role", "divider")
        self.rangeLayout.addWidget(self.rangeLine)

        self.frequencyLayout = QtWidgets.QVBoxLayout()
        self.frequencyLayout.setObjectName("frequencyLayout")

        self.frequencyLabel = QtWidgets.QLabel(self.layoutWidget)
        self.frequencyLabel.setObjectName("frequencyLabel")
        self.frequencyLabel.setProperty("variant", "input")
        self.frequencyLayout.addWidget(self.frequencyLabel)

        # Low Frequency
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

        self.frequencyLayout.addLayout(self.lowFqLayout, stretch=1)
    
        # High Frequency
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
        
        self.rangeLayout.addLayout(self.frequencyLayout)
        self.paramsLayout.addLayout(self.rangeLayout)

        # --- Results Section ---
        self.resultsSection = QtWidgets.QVBoxLayout()
        self.resultsSection.setObjectName("resultsSection")

        self.resultsLabel = QtWidgets.QLabel(self.layoutWidget)
        self.resultsLabel.setObjectName("resultsLabel")
        self.resultsLabel.setProperty("variant", "subtitle")
        self.resultsSection.addWidget(self.resultsLabel)

        self.resultsLine = QtWidgets.QFrame(self.layoutWidget)
        self.resultsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.resultsLine.setObjectName("resultsLine")
        self.resultsLine.setProperty("role", "divider")
        self.resultsSection.addWidget(self.resultsLine)

        # --- Row: Absolute Power ---
        self.absPowerRow = QtWidgets.QHBoxLayout()
        self.absPowerRow.setObjectName("absPowerRow")

        self.absPowerLabel = QtWidgets.QLabel(self.layoutWidget)
        self.absPowerLabel.setObjectName("absPowerLabel")
        self.absPowerLabel.setProperty("variant", "input")
        self.absPowerRow.addWidget(self.absPowerLabel)

        self.absPowerValue = QtWidgets.QLineEdit(self.layoutWidget)
        self.absPowerValue.setObjectName("absPowerValue")
        self.absPowerValue.setText("0.0")
        self.absPowerValue.setReadOnly(True)
        self.absPowerRow.addWidget(self.absPowerValue)

        self.resultsSection.addLayout(self.absPowerRow)

        # --- Row: Relative Power ---
        self.relPowerRow = QtWidgets.QHBoxLayout()
        self.relPowerRow.setObjectName("relPowerRow")

        self.relPowerLabel = QtWidgets.QLabel(self.layoutWidget)
        self.relPowerLabel.setObjectName("relPowerLabel")
        self.relPowerLabel.setProperty("variant", "input")
        self.relPowerRow.addWidget(self.relPowerLabel)

        self.relPowerValue = QtWidgets.QLineEdit(self.layoutWidget)
        self.relPowerValue.setObjectName("relPowerValue")
        self.relPowerValue.setText("0.0")
        self.relPowerValue.setReadOnly(True)
        self.relPowerValue.setToolTip("Porcentaje de la potencia total")
        self.relPowerRow.addWidget(self.relPowerValue)

        self.resultsSection.addLayout(self.relPowerRow)

        # Add entire section to main layout
        self.vbox.addLayout(self.resultsSection)


        # --- Button Calculate Relative PSD ---
        self.paramsLayout.addStretch(1)

        self.calculateRelativePsd = QtWidgets.QPushButton(self.layoutWidget)
        self.calculateRelativePsd.setObjectName("mainActionButton")
        self.paramsLayout.addWidget(self.calculateRelativePsd)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Relative_PSD", "Relative_PSD"))
        self.parametersLabel.setText(_translate("Relativa_PSD", "Parameters"))
        self.sampleDensityLabel.setText(_translate("Relativa_PSD", "Sample density"))
        self.hzLabel.setText(_translate("Relativa_PSD", "Hz"))
        self.welchLabel.setText(_translate("Relativa_PSD", "Welch"))
        self.windowLabel.setText(_translate("Relativa_PSD", "Window"))
        self.npersegLabel.setText(_translate("Relativa_PSD", "N-Per-Seg"))
        self.noverlapLabel.setText(_translate("Relativa_PSD", "N-Overlap"))
        self.nfftLabel.setText(_translate("Relativa_PSD", "N-FFT"))
        self.rangeLabel.setText(_translate("Relativa_PSD", "Range"))
        self.frequencyLabel.setText(_translate("Relativa_PSD", "Frequency (Hz)"))
        self.highLabel.setText(_translate("Relativa_PSD", "High"))
        self.hzHighFreqLabel.setText(_translate("Relativa_PSD", "Hz"))
        self.lowLabel.setText(_translate("Relativa_PSD", "Low"))
        self.hzLowFreqLabel.setText(_translate("Relativa_PSD", "Hz"))
        self.resultsLabel.setText(_translate("Relative_PSD", "Results"))
        self.absPowerLabel.setText(_translate("Relative_PSD", "Absolute Power (Pow)"))
        self.relPowerLabel.setText(_translate("Relative_PSD", "Relative Power (Powr)"))
        self.calculateRelativePsd.setText(_translate("Relative_PSD", "Calculate Relative PSD"))
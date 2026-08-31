from PyQt5 import QtCore, QtWidgets

class Ui_Psd(object):

    def setupUi(self, Psd):
        Psd.setObjectName("Psd")

        # Root layout
        self._root = QtWidgets.QVBoxLayout(Psd)
        self._root.setObjectName("root")
        self._root.setSpacing(0)

        # ====== Splitter ======
        self.splitter = QtWidgets.QSplitter(Psd)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self._root.addWidget(self.splitter)

        # --- Left Area: Plot ---
        self.plotArea = QtWidgets.QFrame(self.splitter)
        self.plotArea.setObjectName("plotArea")
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setFrameShadow(QtWidgets.QFrame.Raised)

        # --- Right Area: Panel ---
        self.scrollArea = QtWidgets.QScrollArea(self.splitter)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.layoutWidget = QtWidgets.QWidget(self.splitter)
        self.layoutWidget.setObjectName("panel")

        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setSpacing(12)

        self.scrollArea.setWidget(self.layoutWidget)
        self.splitter.widget(1).setMaximumWidth(300)

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
        
        # --- Calculation Mode
        self.calculationMode = QtWidgets.QVBoxLayout()
        self.calculationMode.setObjectName("calculationMode")

        self.calculationModeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.calculationModeLabel.setObjectName("calculationModeLabel")
        self.calculationModeLabel.setProperty("variant", "subtitle")
        self.calculationMode.addWidget(self.calculationModeLabel)

        self.calculationModeLine = QtWidgets.QFrame(self.layoutWidget)
        self.calculationModeLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.calculationModeLine.setObjectName("calculationModeLine")
        self.calculationModeLine.setProperty("role", "divider")
        self.calculationMode.addWidget(self.calculationModeLine)

        # --- Row: Mode ComboBox ---
        self.modeRow = QtWidgets.QHBoxLayout()
        self.modeRow.setObjectName("modeRow")

        self.modeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.modeLabel.setObjectName("modeLabel")
        self.modeLabel.setProperty("variant", "input")
        self.modeRow.addWidget(self.modeLabel)

        self.modeComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.modeComboBox.addItems(["All Trials", "Average", "Individual"])
        self.modeRow.addWidget(self.modeComboBox)

        self.calculationMode.addLayout(self.modeRow)

        # --- Row: Individual Trial Selector ---
        self.trialRow = QtWidgets.QHBoxLayout()
        self.trialRow.setObjectName("trialRow")

        self.trialIndexLabel = QtWidgets.QLabel(self.layoutWidget)
        self.trialIndexLabel.setProperty("variant", "input")
        self.trialRow.addWidget(self.trialIndexLabel)

        self.trialIndexSpinBox = QtWidgets.QSpinBox(self.layoutWidget)
        self.trialIndexSpinBox.setEnabled(False)
        self.trialRow.addWidget(self.trialIndexSpinBox)

        # Hidden by default
        self.trialIndexLabel.setVisible(False)
        self.trialIndexSpinBox.setVisible(False)

        self.calculationMode.addLayout(self.trialRow)
        self.paramsLayout.addLayout(self.calculationMode)

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

        self.paramsLayout.addLayout(self.welchParameters)
        
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

        self.frequencyLayout.addLayout(self.lowFqLayout)
    
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

        # --- Detrend ---
        self.detrendSection = QtWidgets.QVBoxLayout()
        self.detrendSection.setObjectName("detrendSection")

        self.detrendLabel = QtWidgets.QLabel(self.layoutWidget)
        self.detrendLabel.setObjectName("detrendLabel")
        self.detrendLabel.setProperty("variant", "subtitle")
        self.detrendSection.addWidget(self.detrendLabel)

        self.detrendLine = QtWidgets.QFrame(self.layoutWidget)
        self.detrendLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.detrendLine.setObjectName("detrendLine")
        self.detrendLine.setProperty("role", "divider")
        self.detrendSection.addWidget(self.detrendLine)

        self.detrendRow = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.detrendRow.setObjectName("detrendRow")

        self.detrendRowLabel = QtWidgets.QLabel(self.layoutWidget)
        self.detrendRowLabel.setObjectName("detrendRowLabel")
        self.detrendRowLabel.setProperty("variant", "input")
        self.detrendRowLabel.setText("Detrend")
        self.detrendRow.addWidget(self.detrendRowLabel)

        self.detrendComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.detrendComboBox.setObjectName("detrendComboBox")
        self.detrendComboBox.addItems(["none", "constant", "linear"])
        self.detrendRow.addWidget(self.detrendComboBox)

        self.detrendSection.addLayout(self.detrendRow)
        self.paramsLayout.addLayout(self.detrendSection)

        # --- Button Calculate PSD ---
        self.paramsLayout.addStretch(1)

        self.calculatePsdButton = QtWidgets.QPushButton(self.layoutWidget)
        self.calculatePsdButton.setObjectName("mainActionButton")
        self.paramsLayout.addWidget(self.calculatePsdButton)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(Psd)
        QtCore.QMetaObject.connectSlotsByName(Psd)

    def retranslateUi(self, Psd):
        _translate = QtCore.QCoreApplication.translate
        Psd.setWindowTitle(_translate("PSD", "PSD"))
        self.parametersLabel.setText(_translate("PSD", "Parameters"))
        self.calculationModeLabel.setText(_translate("PSD", "Calculation Mode"))
        self.modeLabel.setText(_translate("PSD", "Mode"))
        self.trialIndexLabel.setText(_translate("PSD", "Trial Index"))
        self.sampleDensityLabel.setText(_translate("PSD", "Sample density"))
        self.hzLabel.setText(_translate("PSD", "Hz"))
        self.welchLabel.setText(_translate("PSD", "Welch"))
        self.windowLabel.setText(_translate("PSD", "Window"))
        self.npersegLabel.setText(_translate("PSD", "N-Per-Seg"))
        self.noverlapLabel.setText(_translate("PSD", "N-Overlap"))
        self.nfftLabel.setText(_translate("PSD", "N-FFT"))
        self.rangeLabel.setText(_translate("PSD", "Range"))
        self.frequencyLabel.setText(_translate("PSD", "Frequency (Hz)"))
        self.highLabel.setText(_translate("PSD", "High"))
        self.hzHighFreqLabel.setText(_translate("PSD", "Hz"))
        self.lowLabel.setText(_translate("PSD", "Low"))
        self.hzLowFreqLabel.setText(_translate("PSD", "Hz"))
        self.detrendLabel.setText(_translate("PSD", "Detrend"))
        self.calculatePsdButton.setText(_translate("PSD", "Calculate PSD"))

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Wavelet(object):

    def setupUi(self, Wavelet):
        Wavelet.setObjectName("Wavelet")
        Wavelet.resize(825, 609)

        self.mainWindow = QtWidgets.QHBoxLayout(Wavelet)
        self.mainWindow.setObjectName("mainWindow")
        self.mainWindow.setSpacing(0)

        self.splitter = QtWidgets.QSplitter(Wavelet)
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

        # --- Wavelet ---
        self.waveletLayout = QtWidgets.QVBoxLayout()
        self.waveletLayout.setObjectName("waveletLayout")

        self.waveletLabel = QtWidgets.QLabel(self.layoutWidget)
        self.waveletLabel.setObjectName("waveletLabel")
        self.waveletLabel.setProperty("variant", "subtitle")
        self.waveletLayout.addWidget(self.waveletLabel)

        self.waveletLine = QtWidgets.QFrame(self.layoutWidget)
        self.waveletLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.waveletLine.setObjectName("waveletLine")
        self.waveletLine.setProperty("role", "divider")
        self.waveletLayout.addWidget(self.waveletLine)

        self.cyclesLayout = QtWidgets.QHBoxLayout()
        self.cyclesLayout.setObjectName("cyclesLayout")

        self.cyclesLabel = QtWidgets.QLabel(self.layoutWidget)
        self.cyclesLabel.setObjectName("cyclesLabel")
        self.cyclesLabel.setProperty("variant", "input")
        self.cyclesLayout.addWidget(self.cyclesLabel)

        self.cyclesSpinBox = QtWidgets.QSpinBox(self.layoutWidget)
        self.cyclesSpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.cyclesSpinBox.setObjectName("cyclesSpinBox")

        self.cyclesLayout.addWidget(self.cyclesSpinBox)
        self.waveletLayout.addLayout(self.cyclesLayout)
        self.paramsLayout.addLayout(self.waveletLayout)

        # --- Scalogram ---
        self.scalogramLayout = QtWidgets.QVBoxLayout()
        self.scalogramLayout.setObjectName("scalogramLayout")

        self.scalogramLabel = QtWidgets.QLabel(self.layoutWidget)
        self.scalogramLabel.setObjectName("scalogramLabel")
        self.scalogramLabel.setProperty("variant", "subtitle")
        self.scalogramLayout.addWidget(self.scalogramLabel)

        self.scalogramLine = QtWidgets.QFrame(self.layoutWidget)
        self.scalogramLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.scalogramLine.setObjectName("scalogramLine")
        self.scalogramLine.setProperty("role", "divider")
        self.scalogramLayout.addWidget(self.scalogramLine)

        self.normScaleLayout = QtWidgets.QVBoxLayout()
        self.normScaleLayout.setObjectName("normScaleLayout")

        # Normalize
        self.normalizeLayout = QtWidgets.QHBoxLayout()
        self.normalizeLayout.setObjectName("normalizeLayout")

        self.normalizeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.normalizeLabel.setObjectName("normalizeLabel")
        self.normalizeLabel.setProperty("variant", "input")
        self.normalizeLayout.addWidget(self.normalizeLabel)

        self.normalizeCheckBox = QtWidgets.QCheckBox(self.layoutWidget)
        self.normalizeCheckBox.setText("")
        self.normalizeCheckBox.setObjectName("normalizeCheckBox")

        self.normalizeLayout.addWidget(self.normalizeCheckBox)
        self.normalizeLayout.setAlignment(self.normalizeCheckBox, QtCore.Qt.AlignRight)
        
        self.normScaleLayout.addLayout(self.normalizeLayout)

        self.normTypeLayout = QtWidgets.QHBoxLayout()
        self.normTypeLayout.setObjectName("normTypeLayout")

        self.typeNormalizeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.typeNormalizeLabel.setObjectName("typeNormalizeLabel")
        self.typeNormalizeLabel.setProperty("variant", "input")
        self.normTypeLayout.addWidget(self.typeNormalizeLabel)

        self.normalizeComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.normalizeComboBox.setObjectName("normalizeComboBox")
        self.normTypeLayout.addWidget(self.normalizeComboBox)
        self.normScaleLayout.addLayout(self.normTypeLayout)

        # Scale
        self.scaleLayout = QtWidgets.QHBoxLayout()
        self.scaleLayout.setObjectName("scaleLayout")

        self.scaleLabel = QtWidgets.QLabel(self.layoutWidget)
        self.scaleLabel.setObjectName("scaleLabel")
        self.scaleLabel.setProperty("variant", "input")
        self.scaleLayout.addWidget(self.scaleLabel)

        self.scaleCheckBox = QtWidgets.QCheckBox(self.layoutWidget)
        self.scaleCheckBox.setText("")
        self.scaleCheckBox.setObjectName("scaleCheckBox")

        self.scaleLayout.addWidget(self.scaleCheckBox)
        self.scaleLayout.setAlignment(self.scaleCheckBox, QtCore.Qt.AlignRight)

        self.normScaleLayout.addLayout(self.scaleLayout)

        self.scaleTypeLayout = QtWidgets.QHBoxLayout()
        self.scaleTypeLayout.setObjectName("scaleTypeLayout")

        self.typeScaleLabel = QtWidgets.QLabel(self.layoutWidget)
        self.typeScaleLabel.setObjectName("typeScaleLabel")
        self.typeScaleLabel.setProperty("variant", "input")
        self.scaleTypeLayout.addWidget(self.typeScaleLabel)

        self.scaleComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.scaleComboBox.setObjectName("scaleComboBox")
        self.scaleTypeLayout.addWidget(self.scaleComboBox)
        self.normScaleLayout.addLayout(self.scaleTypeLayout)

        self.scalogramLayout.addLayout(self.normScaleLayout)
        self.paramsLayout.addLayout(self.scalogramLayout)

        # --- Button Create Wavelet ---
        self.paramsLayout.addStretch(1)

        self.createWaveletButton = QtWidgets.QPushButton(self.layoutWidget)
        self.createWaveletButton.setObjectName("mainActionButton")
        self.paramsLayout.addWidget(self.createWaveletButton)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(Wavelet)
        QtCore.QMetaObject.connectSlotsByName(Wavelet)

    def retranslateUi(self, Wavelet):
        _translate = QtCore.QCoreApplication.translate
        Wavelet.setWindowTitle(_translate("Wavelet", "Wavelet"))
        self.parametersLabel.setText(_translate("Wavelet", "Parameters"))
        self.sampleDensityLabel.setText(_translate("Wavelet", "Sample density"))
        self.hzLabel.setText(_translate("Wavelet", "Hz"))
        self.rangeLabel.setText(_translate("Wavelet", "Range"))
        self.frequencyLabel.setText(_translate("Wavelet", "Frequency (Hz)"))
        self.highLabel.setText(_translate("Wavelet", "High"))
        self.hzHighFreqLabel.setText(_translate("Wavelet", "Hz"))
        self.lowLabel.setText(_translate("Wavelet", "Low"))
        self.hzLowFreqLabel.setText(_translate("Wavelet", "Hz"))
        self.waveletLabel.setText(_translate("Wavelet", "Wavelet"))
        self.cyclesLabel.setText(_translate("Wavelet", "Cycles"))
        self.scalogramLabel.setText(_translate("Wavelet", "Scalogram"))
        self.normalizeLabel.setText(_translate("Wavelet", "Normalize"))
        self.typeNormalizeLabel.setText(_translate("Wavelet", "Type"))
        self.scaleLabel.setText(_translate("Wavelet", "Scale"))
        self.typeScaleLabel.setText(_translate("Wavelet", "Type"))
        self.createWaveletButton.setText(_translate("Wavelet", "Create Wavelet"))
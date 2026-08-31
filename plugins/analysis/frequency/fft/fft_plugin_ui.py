from PyQt5 import QtCore, QtWidgets

class Ui_Fft(object):
    def setupUi(self, Fft):
        Fft.setObjectName("Fft")

        self.mainWindow = QtWidgets.QHBoxLayout(Fft)
        self.mainWindow.setObjectName("mainWindow")
        self.mainWindow.setSpacing(0)

        self.splitter = QtWidgets.QSplitter(Fft)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.mainWindow.addWidget(self.splitter)

        # --- Left Area: Plot ---
        self.plotArea = QtWidgets.QFrame(self.splitter)
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setFrameShadow(QtWidgets.QFrame.Raised)
        self.plotArea.setObjectName("plotArea")

        # --- Right Area: Panel ---
        self.scrollArea = QtWidgets.QScrollArea(self.splitter)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.layoutWidget = QtWidgets.QWidget(self.splitter)
        self.layoutWidget.setObjectName("layoutWidget")

        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setObjectName("paramsLayout")
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

        # --- Button Calculate FFT ---
        self.paramsLayout.addStretch(1)

        self.calculateFftButton = QtWidgets.QPushButton(self.layoutWidget)
        self.calculateFftButton.setObjectName("mainActionButton")
        self.paramsLayout.addWidget(self.calculateFftButton)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(Fft)
        QtCore.QMetaObject.connectSlotsByName(Fft)

    def retranslateUi(self, Fft):
        _translate = QtCore.QCoreApplication.translate
        Fft.setWindowTitle(_translate("Fft", "Fft"))
        self.parametersLabel.setText(_translate("Fft", "Parameters"))
        self.sampleDensityLabel.setText(_translate("Fft", "Sample density"))
        self.hzLabel.setText(_translate("Fft", "Hz"))
        self.rangeLabel.setText(_translate("Fft", "Range"))
        self.frequencyLabel.setText(_translate("Fft", "Frequency (Hz)"))
        self.highLabel.setText(_translate("Fft", "High"))
        self.hzHighFreqLabel.setText(_translate("Fft", "Hz"))
        self.lowLabel.setText(_translate("Fft", "Low"))
        self.hzLowFreqLabel.setText(_translate("Fft", "Hz"))
        self.calculateFftButton.setText(_translate("Fft", "Calculate FFT"))

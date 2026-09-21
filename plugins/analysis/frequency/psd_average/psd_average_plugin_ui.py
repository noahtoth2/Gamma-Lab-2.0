from PyQt5 import QtCore, QtGui, QtWidgets
import os

class Ui_Psd_average(object):

    def setupUi(self, PsdAvg):
        PsdAvg.setObjectName("PsdAvg")

        # Root layout
        self._root = QtWidgets.QVBoxLayout(PsdAvg)
        self._root.setObjectName("root")
        self._root.setSpacing(0)

        # ====== Splitter ======
        self.splitter = QtWidgets.QSplitter(PsdAvg)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self._root.addWidget(self.splitter)

        # --- Left Area: Plot ---
        self.plotArea = QtWidgets.QFrame(self.splitter)
        self.plotArea.setObjectName("plotArea")
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setFrameShadow(QtWidgets.QFrame.Raised)

        # --- Right Area: Panel (fixed header + scrollable body) ---
        self.rightContainer = QtWidgets.QWidget(self.splitter)
        self.rightContainer.setObjectName("rightContainer")

        self.rightLayoutOuter = QtWidgets.QVBoxLayout(self.rightContainer)
        self.rightLayoutOuter.setContentsMargins(8, 0, 8, 0)
        self.rightLayoutOuter.setSpacing(0)

        # ===== Header: Parameters + clear + Calculate PSD Average (always visible) =====
        self.headerLayout = QtWidgets.QHBoxLayout()
        self.headerLayout.setContentsMargins(0, 0, 0, 5)

        self.parametersLabel = QtWidgets.QLabel(self.rightContainer)
        self.parametersLabel.setObjectName("parametersLabel")
        self.parametersLabel.setProperty("variant", "title")
        self.headerLayout.addWidget(self.parametersLabel)

        self.headerLayout.addStretch(1)

        self.clearButton = QtWidgets.QToolButton(self.rightContainer)
        self.clearButton.setObjectName("clearButton")
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "assets", "iconos", "clear.png")
        self.clearButton.setIcon(QtGui.QIcon(icon_path))
        self.clearButton.setIconSize(QtCore.QSize(20, 20))
        self.clearButton.setAutoRaise(True)
        self.clearButton.setToolTip("Clear parameters")
        self.headerLayout.addWidget(self.clearButton)
        self.headerLayout.addSpacing(10)

        self.calculatePsdAvgButton = QtWidgets.QPushButton(self.rightContainer)
        self.calculatePsdAvgButton.setObjectName("headerGenerateButton")
        self.headerLayout.addWidget(self.calculatePsdAvgButton)

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
        self.paramsLayout.setContentsMargins(0, 10, 0, 0)
        self.paramsLayout.setSpacing(12)

        self.scrollArea.setWidget(self.layoutWidget)
        self.rightLayoutOuter.addWidget(self.scrollArea)

        self.splitter.widget(1).setMaximumWidth(300)

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

        # Low Frequency (shown first)
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

        # High Frequency (shown second)
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

        # --- Spacer ---
        self.paramsLayout.addStretch(1)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(PsdAvg)
        QtCore.QMetaObject.connectSlotsByName(PsdAvg)

    def retranslateUi(self, PsdAvg):
        _translate = QtCore.QCoreApplication.translate
        PsdAvg.setWindowTitle(_translate("PSD_Average", "PSD_Average"))
        self.parametersLabel.setText(_translate("PSD_Average", "Parameters"))
        self.sampleDensityLabel.setText(_translate("PSD_Average", "Sample density"))
        self.hzLabel.setText(_translate("PSD_Average", "Hz"))
        self.welchLabel.setText(_translate("PSD_Average", "Welch"))
        self.windowLabel.setText(_translate("PSD_Average", "Window"))
        self.npersegLabel.setText(_translate("PSD_Average", "N-Per-Seg"))
        self.noverlapLabel.setText(_translate("PSD_Average", "N-Overlap"))
        self.nfftLabel.setText(_translate("PSD_Average", "N-FFT"))
        self.rangeLabel.setText(_translate("PSD_Average", "Range"))
        self.frequencyLabel.setText(_translate("PSD_Average", "Frequency (Hz)"))
        self.highLabel.setText(_translate("PSD_Average", "High"))
        self.hzHighFreqLabel.setText(_translate("PSD_Average", "Hz"))
        self.lowLabel.setText(_translate("PSD_Average", "Low"))
        self.hzLowFreqLabel.setText(_translate("PSD_Average", "Hz"))
        self.calculatePsdAvgButton.setText(_translate("PSD_Average", "Generate"))

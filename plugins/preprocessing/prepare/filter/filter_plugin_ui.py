from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Filter(object):

    def setupUi(self, Filter):
        Filter.setObjectName("Filter")

        self.mainWindow = QtWidgets.QHBoxLayout(Filter)
        self.mainWindow.setObjectName("mainWindow")

        self.main_splitter = QtWidgets.QSplitter(Filter)
        self.main_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.main_splitter.setObjectName("main_splitter")
        self.mainWindow.addWidget(self.main_splitter)

        # === Center: Splitter with 2 graphic zones ===
        self.splitter = QtWidgets.QSplitter(Filter)
        self.splitter.setOrientation(QtCore.Qt.Vertical)
        self.splitter.setObjectName("splitter")
        self.main_splitter.addWidget(self.splitter)

        # Up: Filtered signal
        self.filteredSignal = QtWidgets.QFrame(self.splitter)
        self.filteredSignal.setObjectName("filteredSignal")
        self.filteredSignal.setFrameShape(QtWidgets.QFrame.StyledPanel)

        # Down: Filtered trial
        self.filteredTrial = QtWidgets.QFrame(self.splitter)
        self.filteredTrial.setObjectName("filteredTrial")
        self.filteredTrial.setFrameShape(QtWidgets.QFrame.StyledPanel)

        # --- Right Area: Panel
        self.scrollArea = QtWidgets.QScrollArea(self.main_splitter)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.layoutWidget = QtWidgets.QWidget(self.main_splitter)
        self.layoutWidget.setObjectName("layoutWidget")

        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setObjectName("paramsLayout")
        self.paramsLayout.setContentsMargins(8, 0, 8, 0)
        self.paramsLayout.setSpacing(12)

        self.scrollArea.setWidget(self.layoutWidget)
        self.main_splitter.widget(1).setMaximumWidth(300)

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

        # --- Filters ---
        self.filterLayout = QtWidgets.QVBoxLayout()
        self.filterLayout.setObjectName("filterLayout")

        self.filtersLabel = QtWidgets.QLabel(self.layoutWidget)
        self.filtersLabel.setObjectName("filtersLabel")
        self.filtersLabel.setProperty("variant", "subtitle")
        self.filterLayout.addWidget(self.filtersLabel)

        self.filtersLine = QtWidgets.QFrame(self.layoutWidget)
        self.filtersLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.filtersLine.setObjectName("filtersLine")
        self.filtersLine.setProperty("role", "divider")
        self.filterLayout.addWidget(self.filtersLine)

        self.filterType = QtWidgets.QHBoxLayout()
        self.filterType.setObjectName("filterType")

        self.typeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.typeLabel.setObjectName("typeLabel")
        self.typeLabel.setProperty("variant", "input")
        self.filterType.addWidget(self.typeLabel)

        self.typeSelectComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.typeSelectComboBox.setObjectName("typeSelectComboBox")
        self.filterType.addWidget(self.typeSelectComboBox)
        self.filterLayout.addLayout(self.filterType)
        self.paramsLayout.addLayout(self.filterLayout)

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

        # --- Order ---
        self.orderLayout = QtWidgets.QVBoxLayout()
        self.orderLayout.setObjectName("orderLayout")

        self.orderLabel = QtWidgets.QLabel(self.layoutWidget)
        self.orderLabel.setObjectName("orderLabel")
        self.orderLabel.setProperty("variant", "subtitle")
        self.orderLayout.addWidget(self.orderLabel)

        self.orderLine = QtWidgets.QFrame(self.layoutWidget)
        self.orderLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.orderLine.setObjectName("orderLine")
        self.rangeLine.setProperty("role", "divider")
        self.orderLayout.addWidget(self.orderLine)

        self.orderSpinBox = QtWidgets.QSpinBox(self.layoutWidget)
        self.orderSpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.orderSpinBox.setObjectName("orderSpinBox")
        self.orderLayout.addWidget(self.orderSpinBox)

        self.paramsLayout.addLayout(self.orderLayout)

        # --- Button Create Wavelet ---
        self.paramsLayout.addStretch(1)

        self.applyFilterButton = QtWidgets.QPushButton(self.layoutWidget)
        self.applyFilterButton.setObjectName("mainActionButton")
        self.paramsLayout.addWidget(self.applyFilterButton)

        # Size splitter
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        self.retranslateUi(Filter)
        QtCore.QMetaObject.connectSlotsByName(Filter)

    def retranslateUi(self, Filter):
        _translate = QtCore.QCoreApplication.translate
        Filter.setWindowTitle(_translate("Filter", "Form"))
        self.parametersLabel.setText(_translate("Filter", "Parameters"))
        self.filtersLabel.setText(_translate("Filter", "Filters"))
        self.typeLabel.setText(_translate("Filter", "Type"))
        self.rangeLabel.setText(_translate("Filter", "Range"))
        self.frequencyLabel.setText(_translate("Filter", "Frequency (Hz)"))
        self.highLabel.setText(_translate("Filter", "High"))
        self.lowLabel.setText(_translate("Filter", "Low"))
        self.orderLabel.setText(_translate("Filter", "Order"))
        self.applyFilterButton.setText(_translate("Filter", "Filter"))

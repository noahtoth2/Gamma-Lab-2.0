from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Filter(object):

    def setupUi(self, Filter):
        Filter.setObjectName("Filter")

        self.mainWindow = QtWidgets.QHBoxLayout(Filter)
        self.mainWindow.setObjectName("mainWindow")
        self.mainWindow.setSpacing(0)

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

        # === Right: Parameters panel (fixed header + scrollable body) ===
        self.rightContainer = QtWidgets.QWidget(self.main_splitter)
        self.rightLayoutOuter = QtWidgets.QVBoxLayout(self.rightContainer)
        self.rightLayoutOuter.setContentsMargins(8, 0, 8, 0)
        self.rightLayoutOuter.setSpacing(0)

        # --- Header: Parameters + clear + Filter (always visible, not scrollable) ---
        self.headerLayout = QtWidgets.QHBoxLayout()

        self.parametersLabel = QtWidgets.QLabel(self.rightContainer)
        self.parametersLabel.setObjectName("parametersLabel")
        self.parametersLabel.setProperty("variant", "title")
        self.headerLayout.addWidget(self.parametersLabel)

        self.headerLayout.addStretch(1)

        self.Btn_clear_params = QtWidgets.QToolButton(self.rightContainer)
        self.Btn_clear_params.setObjectName("clearParamsButton")
        self.Btn_clear_params.setIcon(QtGui.QIcon("assets/iconos/clear.png"))
        self.Btn_clear_params.setIconSize(QtCore.QSize(28, 28))
        self.Btn_clear_params.setAutoRaise(True)
        self.Btn_clear_params.setToolTip("Clear parameters")
        self.headerLayout.addWidget(self.Btn_clear_params)
        self.headerLayout.addSpacing(10)

        self.applyFilterButton = QtWidgets.QPushButton(self.rightContainer)
        self.applyFilterButton.setObjectName("headerGenerateButton")
        self.headerLayout.addWidget(self.applyFilterButton)

        self.rightLayoutOuter.addLayout(self.headerLayout)

        self.paramsLine = QtWidgets.QFrame(self.rightContainer)
        self.paramsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.paramsLine.setObjectName("paramsLine")
        self.paramsLine.setProperty("role", "section-divider")
        self.rightLayoutOuter.addWidget(self.paramsLine)

        # --- Scrollable body (only scrolls if the panel is squeezed, e.g. by Results) ---
        self.scrollArea = QtWidgets.QScrollArea(self.rightContainer)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scrollArea.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scrollArea.setObjectName("scrollArea")

        self.layoutWidget = QtWidgets.QWidget()
        self.layoutWidget.setObjectName("layoutWidget")
        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setObjectName("paramsLayout")
        self.paramsLayout.setContentsMargins(0, 10, 0, 0)
        self.paramsLayout.setSpacing(6)

        self.scrollArea.setWidget(self.layoutWidget)
        self.rightLayoutOuter.addWidget(self.scrollArea)

        # === Filters ===
        self.filtersLabel = QtWidgets.QLabel(self.layoutWidget)
        self.filtersLabel.setObjectName("filtersLabel")
        self.filtersLabel.setProperty("variant", "subtitle")
        self.paramsLayout.addWidget(self.filtersLabel)

        self.filtersLine = QtWidgets.QFrame(self.layoutWidget)
        self.filtersLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.filtersLine.setObjectName("filtersLine")
        self.filtersLine.setProperty("role", "divider")
        self.paramsLayout.addWidget(self.filtersLine)

        self.typeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.typeLabel.setObjectName("typeLabel")
        self.typeLabel.setProperty("variant", "input")
        self.paramsLayout.addWidget(self.typeLabel)

        self.typeSelectComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.typeSelectComboBox.setObjectName("typeSelectComboBox")
        self.paramsLayout.addWidget(self.typeSelectComboBox)

        # === Frecuency (Hz) (two columns, side by side) ===
        self.frequencyLabel = QtWidgets.QLabel(self.layoutWidget)
        self.frequencyLabel.setObjectName("frequencyLabel")
        self.frequencyLabel.setProperty("variant", "subtitle")
        self.paramsLayout.addWidget(self.frequencyLabel)

        self.frequencyLine = QtWidgets.QFrame(self.layoutWidget)
        self.frequencyLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.frequencyLine.setObjectName("frequencyLine")
        self.frequencyLine.setProperty("role", "divider")
        self.paramsLayout.addWidget(self.frequencyLine)

        self.frequencyBodyRow = QtWidgets.QHBoxLayout()

        self.lowCol = QtWidgets.QVBoxLayout()
        self.lowLabel = QtWidgets.QLabel(self.layoutWidget)
        self.lowLabel.setObjectName("lowLabel")
        self.lowLabel.setProperty("variant", "input")
        self.lowCol.addWidget(self.lowLabel)
        self.lowFrequencySpinBox = QtWidgets.QDoubleSpinBox(self.layoutWidget)
        self.lowFrequencySpinBox.setObjectName("lowFrequencySpinBox")
        self.lowFrequencySpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.lowCol.addWidget(self.lowFrequencySpinBox)
        self.frequencyBodyRow.addLayout(self.lowCol, 1)

        self.highCol = QtWidgets.QVBoxLayout()
        self.highLabel = QtWidgets.QLabel(self.layoutWidget)
        self.highLabel.setObjectName("highLabel")
        self.highLabel.setProperty("variant", "input")
        self.highCol.addWidget(self.highLabel)
        self.highFrequencySpinBox = QtWidgets.QDoubleSpinBox(self.layoutWidget)
        self.highFrequencySpinBox.setObjectName("highFrequencySpinBox")
        self.highFrequencySpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.highCol.addWidget(self.highFrequencySpinBox)
        self.frequencyBodyRow.addLayout(self.highCol, 1)

        self.paramsLayout.addLayout(self.frequencyBodyRow)

        # === Order ===
        self.orderLabel = QtWidgets.QLabel(self.layoutWidget)
        self.orderLabel.setObjectName("orderLabel")
        self.orderLabel.setProperty("variant", "subtitle")
        self.paramsLayout.addWidget(self.orderLabel)

        self.orderLine = QtWidgets.QFrame(self.layoutWidget)
        self.orderLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.orderLine.setObjectName("orderLine")
        self.orderLine.setProperty("role", "divider")
        self.paramsLayout.addWidget(self.orderLine)

        self.orderSpinBox = QtWidgets.QSpinBox(self.layoutWidget)
        self.orderSpinBox.setObjectName("orderSpinBox")
        self.orderSpinBox.setAlignment(QtCore.Qt.AlignCenter)
        self.paramsLayout.addWidget(self.orderSpinBox)

        self.paramsLayout.addStretch(1)

        self.main_splitter.widget(1).setMaximumWidth(300)

        # Size splitter
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        self.retranslateUi(Filter)
        QtCore.QMetaObject.connectSlotsByName(Filter)

    def retranslateUi(self, Filter):
        _translate = QtCore.QCoreApplication.translate
        Filter.setWindowTitle(_translate("Filter", "Form"))
        self.parametersLabel.setText(_translate("Filter", "Parameters"))
        self.applyFilterButton.setText(_translate("Filter", "Filter"))
        self.filtersLabel.setText(_translate("Filter", "Filters"))
        self.typeLabel.setText(_translate("Filter", "type"))
        self.frequencyLabel.setText(_translate("Filter", "Frecuency (Hz)"))
        self.lowLabel.setText(_translate("Filter", "Low"))
        self.highLabel.setText(_translate("Filter", "High"))
        self.orderLabel.setText(_translate("Filter", "Order"))

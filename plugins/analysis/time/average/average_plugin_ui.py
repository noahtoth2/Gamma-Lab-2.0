from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Average(object):

    def setupUi(self, Average):
        Average.setObjectName("Average")

        self.mainWindow = QtWidgets.QHBoxLayout(Average)
        self.mainWindow.setObjectName("mainWindow")
        self.mainWindow.setSpacing(0)

        self.splitter = QtWidgets.QSplitter(Average)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.mainWindow.addWidget(self.splitter)

        # --- Left Area: Plot ---
        self.plotArea = QtWidgets.QFrame(self.splitter)
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setFrameShadow(QtWidgets.QFrame.Raised)
        self.plotArea.setObjectName("plotArea")

        # --- Right Area: Panel
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
        self.splitter.setSizes([700, 300])

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

        # # --- Trials ---
        # self.trials = QtWidgets.QVBoxLayout()
        # self.trials.setObjectName("trials")

        # self.trialsLabel = QtWidgets.QLabel(self.layoutWidget)
        # self.trialsLabel.setObjectName("trialsLabel")
        # self.trialsLabel.setProperty("variant", "subtitle")
        # self.trials.addWidget(self.trialsLabel)

        # self.trialsLine = QtWidgets.QFrame(self.layoutWidget)
        # self.trialsLine.setFrameShape(QtWidgets.QFrame.HLine)
        # self.trialsLine.setObjectName("trialsLine")
        # self.trialsLine.setProperty("role", "divider")
        # self.trials.addWidget(self.trialsLine)

        # self.trialsSelect = QtWidgets.QHBoxLayout()
        # self.trialsSelect.setObjectName("trialsSelect")
        # self.trialsSelect.setAlignment(QtCore.Qt.AlignLeft)

        # self.selectAllTrialsCheckBox = QtWidgets.QCheckBox(self.layoutWidget)
        # self.selectAllTrialsCheckBox.setObjectName("selectAllTrialsCheckBox")
        # self.trialsSelect.addWidget(self.selectAllTrialsCheckBox)

        # self.allTrialsLabel = QtWidgets.QLabel(self.layoutWidget)
        # self.allTrialsLabel.setObjectName("allTrialsLabel")
        # self.allTrialsLabel.setProperty("variant", "input")
        # self.trialsSelect.addWidget(self.allTrialsLabel)

        # self.trials.addLayout(self.trialsSelect)
        # self.paramsLayout.addLayout(self.trials)

        # # --- Range ---
        # self.rangeLayout = QtWidgets.QHBoxLayout()
        # self.rangeLayout.setObjectName("rangeLayout")

        # self.fromLabel = QtWidgets.QLabel(self.layoutWidget)
        # self.fromLabel.setObjectName("fromLabel")
        # self.fromLabel.setProperty("variant", "input")
        # self.rangeLayout.addWidget(self.fromLabel)

        # self.fromEditText = QtWidgets.QLineEdit(self.layoutWidget)
        # self.fromEditText.setObjectName("fromEditText")
        # self.rangeLayout.addWidget(self.fromEditText)

        # self.toLabel = QtWidgets.QLabel(self.layoutWidget)
        # self.toLabel.setObjectName("toLabel")
        # self.toLabel.setProperty("variant", "input")
        # self.rangeLayout.addWidget(self.toLabel)

        # self.toEditText = QtWidgets.QLineEdit(self.layoutWidget)
        # self.toEditText.setObjectName("toEditText")
        # self.rangeLayout.addWidget(self.toEditText)
        # self.paramsLayout.addLayout(self.rangeLayout)

        # --- Button Calculate Average ---
        self.paramsLayout.addStretch(1)

        self.calculateAverageButton = QtWidgets.QPushButton(self.layoutWidget)
        self.calculateAverageButton.setObjectName("mainActionButton")
        self.paramsLayout.addWidget(self.calculateAverageButton)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(Average)
        QtCore.QMetaObject.connectSlotsByName(Average)

    def retranslateUi(self, Average):
        _translate = QtCore.QCoreApplication.translate
        Average.setWindowTitle(_translate("Average", "Average"))
        self.parametersLabel.setText(_translate("Average", "Parameters"))
        # self.trialsLabel.setText(_translate("Average", "Trials"))
        # self.allTrialsLabel.setText(_translate("Average", "Select all trials"))
        # self.fromLabel.setText(_translate("Average", "From"))
        # self.toLabel.setText(_translate("Average", "To"))
        self.calculateAverageButton.setText(_translate("Average", "Calculate Average"))

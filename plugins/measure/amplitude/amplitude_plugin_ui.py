
# -*- coding: utf-8 -*-


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Amplitude(object):
    def setupUi(self, Form):
        Form.setObjectName("AmplitudeForm")
        Form.resize(810, 530)

        self.horizontalLayout = QtWidgets.QHBoxLayout(Form)
        self.horizontalLayout.setContentsMargins(10, 10, 10, 10)
        self.horizontalLayout.setSpacing(10)

        self.splitter = QtWidgets.QSplitter(Form)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")

        self.tableView = QtWidgets.QTableView(self.splitter)
        self.tableView.setObjectName("tableView")

        self.rightPanel = QtWidgets.QWidget(self.splitter)
        self.rightPanel.setObjectName("rightPanel")

        self.rightLayout = QtWidgets.QVBoxLayout(self.rightPanel)
        self.rightLayout.setContentsMargins(0, 0, 0, 0)
        self.rightLayout.setSpacing(8)

        self.verticalSpacer = QtWidgets.QSpacerItem(
            20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.rightLayout.addItem(self.verticalSpacer)

        self.horizontalLayout.addWidget(self.splitter)

        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Amplitude Measurements"))
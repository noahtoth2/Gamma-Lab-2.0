from PyQt5 import QtCore, QtGui, QtWidgets
import os

class Ui_ErpPlot(QtWidgets.QWidget):
    """
    ERP Plot panel (simplified version):
    - Center: QSplitter with two areas (butterflyPlot and heatmapPlot).
    - Right: parameters (Select all / Single / Range / Trials list / Plot).
    - No Advanced group and no auxiliary buttons in the trials list.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        self.setObjectName("ErpPlotWidget")

        root = QtWidgets.QHBoxLayout(self)
        root.setSpacing(0)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.main_splitter.setObjectName("main_splitter")

        root.addWidget(self.main_splitter)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.splitter.setObjectName("splitterPlots")

        self.butterflyPlot = QtWidgets.QFrame(self.splitter)
        self.butterflyPlot.setObjectName("butterflyPlot")
        self.butterflyPlot.setFrameShape(QtWidgets.QFrame.StyledPanel)

        self.heatmapPlot = QtWidgets.QFrame(self.splitter)
        self.heatmapPlot.setObjectName("heatmapPlot")
        self.heatmapPlot.setFrameShape(QtWidgets.QFrame.StyledPanel)

        self.main_splitter.addWidget(self.splitter)

        self.rightContainer = QtWidgets.QWidget(self.main_splitter)
        self.rightContainer.setObjectName("rightContainer")
        self.rightContainer.setMaximumWidth(360)

        self.rightLayoutOuter = QtWidgets.QVBoxLayout(self.rightContainer)
        self.rightLayoutOuter.setContentsMargins(8, 0, 8, 0)
        self.rightLayoutOuter.setSpacing(0)

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
        self.clearButton.setIconSize(QtCore.QSize(28, 28))
        self.clearButton.setAutoRaise(True)
        self.clearButton.setToolTip("Clear parameters")
        self.headerLayout.addWidget(self.clearButton)
        self.headerLayout.addSpacing(10)

        self.plotErpButton = QtWidgets.QPushButton(self.rightContainer)
        self.plotErpButton.setObjectName("headerGenerateButton")
        self.headerLayout.addWidget(self.plotErpButton)

        self.rightLayoutOuter.addLayout(self.headerLayout)

        self.paramsLine = QtWidgets.QFrame(self.rightContainer)
        self.paramsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.paramsLine.setObjectName("paramsLine")
        self.paramsLine.setProperty("role", "section-divider")
        self.rightLayoutOuter.addWidget(self.paramsLine)

        self.scrollArea = QtWidgets.QScrollArea(self.rightContainer)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scrollArea.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.rightLayoutOuter.addWidget(self.scrollArea)

        self.panel = QtWidgets.QWidget()
        self.panel.setObjectName("panel_param")

        self.panelLay = QtWidgets.QVBoxLayout(self.panel)
        self.panelLay.setContentsMargins(0, 10, 0, 0)
        self.panelLay.setSpacing(12)

        self.scrollArea.setWidget(self.panel)

        self.trialsSelection = QtWidgets.QVBoxLayout()
        self.trialsSelection.setObjectName("trialsSelection")

        self.trialsSelectionLabel = QtWidgets.QLabel(self.panel)
        self.trialsSelectionLabel.setObjectName("trialsSelectionLabel")
        self.trialsSelectionLabel.setProperty("variant", "subtitle")
        self.trialsSelection.addWidget(self.trialsSelectionLabel)

        self.trialsSelectionLine = QtWidgets.QFrame(self.panel)
        self.trialsSelectionLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.trialsSelectionLine.setObjectName("trialsSelectionLine")
        self.trialsSelectionLine.setProperty("role", "divider")
        self.trialsSelection.addWidget(self.trialsSelectionLine)

        self.chkSelectAll = QtWidgets.QCheckBox("Select all trials", self.panel)
        self.chkSelectAll.setObjectName("chkSelectAll")
        self.chkSelectAll.setChecked(True)
        self.trialsSelection.addWidget(self.chkSelectAll)

        self.singleTrialRow = QtWidgets.QHBoxLayout()
        self.singleTrialRow.setObjectName("singleTrialRow")

        self.chkSingleTrial = QtWidgets.QCheckBox("Single trial", self.panel)
        self.chkSingleTrial.setObjectName("chkSingleTrial")
        self.singleTrialRow.addWidget(self.chkSingleTrial)

        self.spnSingleTrial = QtWidgets.QSpinBox(self.panel)
        self.spnSingleTrial.setObjectName("spnSingleTrial")
        self.spnSingleTrial.setEnabled(False)
        self.spnSingleTrial.setMinimum(1)
        self.spnSingleTrial.setAlignment(QtCore.Qt.AlignCenter)
        self.singleTrialRow.addStretch(1)
        self.singleTrialRow.addWidget(self.spnSingleTrial)

        self.trialsSelection.addLayout(self.singleTrialRow)

        self.panelLay.addLayout(self.trialsSelection)

        self.rangeSection = QtWidgets.QVBoxLayout()
        self.rangeSection.setObjectName("rangeSection")

        self.rangeLabel = QtWidgets.QLabel(self.panel)
        self.rangeLabel.setObjectName("rangeLabel")
        self.rangeLabel.setProperty("variant", "subtitle")
        self.rangeSection.addWidget(self.rangeLabel)

        self.rangeLine = QtWidgets.QFrame(self.panel)
        self.rangeLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.rangeLine.setObjectName("rangeLine")
        self.rangeLine.setProperty("role", "divider")
        self.rangeSection.addWidget(self.rangeLine)

        self.rangeRow = QtWidgets.QHBoxLayout()
        self.rangeRow.setObjectName("rangeRow")

        self.chkUseRange = QtWidgets.QCheckBox(self.panel)
        self.chkUseRange.setObjectName("chkUseRange")
        self.chkUseRange.setChecked(False)
        self.rangeRow.addWidget(self.chkUseRange)

        self.spnFrom = QtWidgets.QSpinBox(self.panel)
        self.spnFrom.setObjectName("spnFrom")
        self.spnFrom.setEnabled(False)
        self.spnFrom.setMinimum(1)
        self.spnFrom.setAlignment(QtCore.Qt.AlignCenter)
        self.rangeRow.addWidget(self.spnFrom)

        self.toLabel = QtWidgets.QLabel(self.panel)
        self.toLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.toLabel.setProperty("variant", "input")
        self.rangeRow.addWidget(self.toLabel)

        self.spnTo = QtWidgets.QSpinBox(self.panel)
        self.spnTo.setObjectName("spnTo")
        self.spnTo.setEnabled(False)
        self.spnTo.setMinimum(1)
        self.spnTo.setAlignment(QtCore.Qt.AlignCenter)
        self.rangeRow.addWidget(self.spnTo)

        self.rangeRow.addStretch(1)
        self.rangeSection.addLayout(self.rangeRow)

        self.panelLay.addLayout(self.rangeSection)

        self.groupSection = QtWidgets.QVBoxLayout()
        self.groupSection.setObjectName("groupSection")

        self.groupLabel = QtWidgets.QLabel(self.panel)
        self.groupLabel.setObjectName("groupLabel")
        self.groupLabel.setProperty("variant", "subtitle")
        self.groupSection.addWidget(self.groupLabel)

        self.groupLine = QtWidgets.QFrame(self.panel)
        self.groupLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.groupLine.setObjectName("groupLine")
        self.groupLine.setProperty("role", "divider")
        self.groupSection.addWidget(self.groupLine)

        self.groupSizeRow = QtWidgets.QHBoxLayout()
        self.groupSizeLabel = QtWidgets.QLabel(self.panel)
        self.groupSizeLabel.setProperty("variant", "input")
        self.groupSizeRow.addWidget(self.groupSizeLabel)
        self.cmbGroupSize = QtWidgets.QComboBox(self.panel)
        self.cmbGroupSize.setObjectName("cmbGroupSize")
        self.cmbGroupSize.setProperty("variant", "input")
        self.cmbGroupSize.addItems(["All", "3", "6", "Custom"])
        self.groupSizeRow.addWidget(self.cmbGroupSize, 1)
        self.spnGroupSize = QtWidgets.QSpinBox(self.panel)
        self.spnGroupSize.setObjectName("spnGroupSize")
        self.spnGroupSize.setRange(1, 1000000)
        self.spnGroupSize.setValue(4)
        self.spnGroupSize.setAlignment(QtCore.Qt.AlignCenter)
        self.spnGroupSize.setEnabled(False)
        self.groupSizeRow.addWidget(self.spnGroupSize)
        self.groupSection.addLayout(self.groupSizeRow)

        self.groupNavRow = QtWidgets.QHBoxLayout()
        self.btnPrevGroup = QtWidgets.QToolButton(self.panel)
        self.btnPrevGroup.setObjectName("btnPrevGroup")
        self.btnPrevGroup.setArrowType(QtCore.Qt.LeftArrow)
        self.groupNavRow.addWidget(self.btnPrevGroup)
        self.lblGroup = QtWidgets.QLabel(self.panel)
        self.lblGroup.setObjectName("lblGroup")
        self.lblGroup.setAlignment(QtCore.Qt.AlignCenter)
        self.lblGroup.setProperty("variant", "input")
        self.groupNavRow.addWidget(self.lblGroup, 1)
        self.btnNextGroup = QtWidgets.QToolButton(self.panel)
        self.btnNextGroup.setObjectName("btnNextGroup")
        self.btnNextGroup.setArrowType(QtCore.Qt.RightArrow)
        self.groupNavRow.addWidget(self.btnNextGroup)
        self.groupSection.addLayout(self.groupNavRow)

        self.chkShowAverage = QtWidgets.QCheckBox(self.panel)
        self.chkShowAverage.setObjectName("chkShowAverage")
        self.chkShowAverage.setChecked(True)
        self.groupSection.addWidget(self.chkShowAverage)

        self.panelLay.addLayout(self.groupSection)

        self.trialsSection = QtWidgets.QVBoxLayout()
        self.trialsSection.setObjectName("trialsSection")

        self.trialsLabel = QtWidgets.QLabel(self.panel)
        self.trialsLabel.setObjectName("trialsLabel")
        self.trialsLabel.setProperty("variant", "subtitle")
        self.trialsSection.addWidget(self.trialsLabel)

        self.trialsLine = QtWidgets.QFrame(self.panel)
        self.trialsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.trialsLine.setObjectName("trialsLine")
        self.trialsLine.setProperty("role", "divider")
        self.trialsSection.addWidget(self.trialsLine)

        self.trialsFilterLayout = QtWidgets.QHBoxLayout()
        self.trialsFilterLayout.setObjectName("trialsFilterLayout")

        self.txtFilter = QtWidgets.QLineEdit(self.panel)
        self.txtFilter.setObjectName("txtFilter")
        self.txtFilter.setPlaceholderText("Filter…")
        self.trialsFilterLayout.addWidget(self.txtFilter)

        self.trialsSection.addLayout(self.trialsFilterLayout)

        self.lstTrials = QtWidgets.QListWidget(self.panel)
        self.lstTrials.setObjectName("lstTrials")
        self.lstTrials.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.lstTrials.setAlternatingRowColors(True)
        self.lstTrials.setMinimumHeight(120)
        self.trialsSection.addWidget(self.lstTrials)

        self.panelLay.addLayout(self.trialsSection)

        self.panelLay.addStretch(1)

        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        self._wireDefaultState()
        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(self)

    def _wireDefaultState(self):
        self.chkSelectAll.toggled.connect(self._onSelectAllToggled)
        self.chkSingleTrial.toggled.connect(self._onSingleToggled)
        self.chkUseRange.toggled.connect(self._onRangeToggled)

        self._onSelectAllToggled(self.chkSelectAll.isChecked())
        self._onSingleToggled(self.chkSingleTrial.isChecked())
        self._onRangeToggled(self.chkUseRange.isChecked())

    def _onSelectAllToggled(self, on: bool):
        if on:
            self.chkSingleTrial.setChecked(False)
            self.chkUseRange.setChecked(False)
        self._updateEnabled()

    def _onSingleToggled(self, on: bool):
        if on:
            self.chkSelectAll.setChecked(False)
            self.chkUseRange.setChecked(False)
        self._updateEnabled()

    def _onRangeToggled(self, on: bool):
        if on:
            self.chkSelectAll.setChecked(False)
            self.chkSingleTrial.setChecked(False)
        self._updateEnabled()

    def _updateEnabled(self):
        sel_all = self.chkSelectAll.isChecked()
        single  = self.chkSingleTrial.isChecked()
        rng     = self.chkUseRange.isChecked()

        self.spnSingleTrial.setEnabled(single)
        self.spnFrom.setEnabled(rng)
        self.spnTo.setEnabled(rng)

        manual = not (sel_all or single or rng)
        self.txtFilter.setEnabled(manual)
        self.lstTrials.setEnabled(manual)

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle("ERP Plot")
        self.parametersLabel.setText(_translate("ERP", "Parameters"))
        self.trialsSelectionLabel.setText(_translate("ERP", "Trials"))
        self.rangeLabel.setText(_translate("ERP", "Range"))
        self.toLabel.setText(_translate("ERP", "To"))
        self.trialsLabel.setText(_translate("ERP", "List"))
        self.groupLabel.setText(_translate("ERP", "Butterfly display"))
        self.groupSizeLabel.setText(_translate("ERP", "Trials per group"))
        self.lblGroup.setText(_translate("ERP", "Group 1/1"))
        self.chkShowAverage.setText(_translate("ERP", "Show average (black)"))
        self.cmbGroupSize.setToolTip("How many trials each butterfly shows at once; "
                                     "the arrows move to the next group.")
        self.btnPrevGroup.setToolTip("Previous group")
        self.btnNextGroup.setToolTip("Next group")
        self.plotErpButton.setText(_translate("ERP", "Generate"))

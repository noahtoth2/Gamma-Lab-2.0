from PyQt5 import QtCore, QtWidgets

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

        # ====== Root layout ======
        root = QtWidgets.QHBoxLayout(self)
        root.setSpacing(0)

        # ====== Main splitter (horizontal) ======
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.main_splitter.setObjectName("main_splitter")

        root.addWidget(self.main_splitter)

        # ====== Center: QSplitter with 2 graphic zones ======
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.splitter.setObjectName("splitterPlots")

        # Up: butterfly plot
        self.butterflyPlot = QtWidgets.QFrame(self.splitter)
        self.butterflyPlot.setObjectName("butterflyPlot")
        self.butterflyPlot.setFrameShape(QtWidgets.QFrame.StyledPanel)

        # Down: heatmap
        self.heatmapPlot = QtWidgets.QFrame(self.splitter)
        self.heatmapPlot.setObjectName("heatmapPlot")
        self.heatmapPlot.setFrameShape(QtWidgets.QFrame.StyledPanel)

        self.main_splitter.addWidget(self.splitter)

        # ====== Right: Parameters panel ======
        self.scrollArea = QtWidgets.QScrollArea(self.main_splitter)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.panel = QtWidgets.QWidget(self.main_splitter)
        self.panel.setObjectName("panel_param")
        self.panel.setMaximumWidth(360)

        self.panelLay = QtWidgets.QVBoxLayout(self.panel)
        self.panelLay.setContentsMargins(8, 8, 8, 8)
        self.panelLay.setSpacing(12)

        self.scrollArea.setWidget(self.panel)

        # === Parameters Header ===
        self.parametersLabel = QtWidgets.QLabel(self.panel)
        self.parametersLabel.setObjectName("parametersLabel")
        self.parametersLabel.setProperty("variant", "title")
        self.panelLay.addWidget(self.parametersLabel)

        self.paramsLine = QtWidgets.QFrame(self.panel)
        self.paramsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.paramsLine.setObjectName("paramsLine")
        self.paramsLine.setProperty("role", "section-divider")
        self.panelLay.addWidget(self.paramsLine)

        # --- Parameters: Trials Selection ---
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

        # Checkbox: Select all trials
        self.chkSelectAll = QtWidgets.QCheckBox("Select all trials", self.panel)
        self.chkSelectAll.setObjectName("chkSelectAll")
        self.chkSelectAll.setChecked(True)
        self.trialsSelection.addWidget(self.chkSelectAll)

        # Row: Single trial
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

        # Add section to main layout
        self.panelLay.addLayout(self.trialsSelection)

        # --- Range Section ---
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

        # Row: Trials range
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

        # --- Filter trials ---
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

        # --- Group: Trials (filter + list) ---
        # Filter input
        self.trialsFilterLayout = QtWidgets.QHBoxLayout()
        self.trialsFilterLayout.setObjectName("trialsFilterLayout")

        self.txtFilter = QtWidgets.QLineEdit(self.panel)
        self.txtFilter.setObjectName("txtFilter")
        self.txtFilter.setPlaceholderText("Filter…")
        self.trialsFilterLayout.addWidget(self.txtFilter)

        self.trialsSection.addLayout(self.trialsFilterLayout)

        # Trials list
        self.lstTrials = QtWidgets.QListWidget(self.panel)
        self.lstTrials.setObjectName("lstTrials")
        self.lstTrials.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.lstTrials.setAlternatingRowColors(True)
        self.lstTrials.setMinimumHeight(120)
        self.trialsSection.addWidget(self.lstTrials)

        self.panelLay.addLayout(self.trialsSection)

        # --- Button Plot ERP ---
        self.panelLay.addStretch(1)

        self.plotErpButton = QtWidgets.QPushButton(self.panel)
        self.plotErpButton.setObjectName("mainActionButton")
        self.panelLay.addWidget(self.plotErpButton)

        # Size splitter
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

        self._wireDefaultState()
        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(self)

    def _wireDefaultState(self):
        # Default states and enablement rules
        self.chkSelectAll.toggled.connect(self._onSelectAllToggled)
        self.chkSingleTrial.toggled.connect(self._onSingleToggled)
        self.chkUseRange.toggled.connect(self._onRangeToggled)

        self._onSelectAllToggled(self.chkSelectAll.isChecked())
        self._onSingleToggled(self.chkSingleTrial.isChecked())
        self._onRangeToggled(self.chkUseRange.isChecked())

    # ==== enablement rules ====
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

        # Trials list enabled only in manual mode
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
        self.plotErpButton.setText(_translate("ERP", "Plot ERP"))

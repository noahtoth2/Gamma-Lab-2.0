from PyQt5 import QtCore, QtGui, QtWidgets
import os

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

        # --- Right Area: Panel (fixed header + scrollable body) ---
        self.rightContainer = QtWidgets.QWidget(self.splitter)
        self.rightContainer.setObjectName("rightContainer")

        self.rightLayoutOuter = QtWidgets.QVBoxLayout(self.rightContainer)
        self.rightLayoutOuter.setContentsMargins(8, 0, 8, 0)
        self.rightLayoutOuter.setSpacing(0)

        # ===== Header: Parameters + clear + Calculate Average (always visible) =====
        self.headerLayout = QtWidgets.QHBoxLayout()
        self.headerLayout.setContentsMargins(0, 0, 0, 5)

        self.parametersLabel = QtWidgets.QLabel(self.rightContainer)
        self.parametersLabel.setObjectName("parametersLabel")
        self.parametersLabel.setProperty("variant", "title")
        self.headerLayout.addWidget(self.parametersLabel)

        self.headerLayout.addStretch(1)

        # --- Clear/ broom button ---
        self.clearButton = QtWidgets.QToolButton(self.rightContainer)
        self.clearButton.setObjectName("clearButton")
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "assets", "iconos", "clear.png")
        self.clearButton.setIcon(QtGui.QIcon(icon_path))
        self.clearButton.setIconSize(QtCore.QSize(20, 20))
        self.clearButton.setAutoRaise(True)
        self.clearButton.setToolTip("Clear parameters")
        self.headerLayout.addWidget(self.clearButton)
        self.headerLayout.addSpacing(10)

        self.calculateAverageButton = QtWidgets.QPushButton(self.rightContainer)
        self.calculateAverageButton.setObjectName("headerGenerateButton")
        self.headerLayout.addWidget(self.calculateAverageButton)

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
        self.paramsLayout.setObjectName("paramsLayout")
        self.paramsLayout.setContentsMargins(0, 10, 0, 0)
        self.paramsLayout.setSpacing(12)

        self.scrollArea.setWidget(self.layoutWidget)
        self.rightLayoutOuter.addWidget(self.scrollArea)

        # nueva sección trialsSelection...
        # --- Parameters: Trials Selection ---
        self.trialsSelection = QtWidgets.QVBoxLayout()
        self.trialsSelection.setObjectName("trialsSelection")

        self.trialsSelectionLabel = QtWidgets.QLabel(self.layoutWidget)
        self.trialsSelectionLabel.setObjectName("trialsSelectionLabel")
        self.trialsSelectionLabel.setProperty("variant", "subtitle")
        self.trialsSelection.addWidget(self.trialsSelectionLabel)

        self.trialsSelectionLine = QtWidgets.QFrame(self.layoutWidget)
        self.trialsSelectionLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.trialsSelectionLine.setObjectName("trialsSelectionLine")
        self.trialsSelectionLine.setProperty("role", "divider")
        self.trialsSelection.addWidget(self.trialsSelectionLine)

        # Checkbox: Select all trials
        self.chkSelectAll = QtWidgets.QCheckBox("Select all trials", self.layoutWidget)
        self.chkSelectAll.setObjectName("chkSelectAll")
        self.chkSelectAll.setChecked(True)
        self.trialsSelection.addWidget(self.chkSelectAll)

        # Row: Single trial
        self.singleTrialRow = QtWidgets.QHBoxLayout()
        self.singleTrialRow.setObjectName("singleTrialRow")

        self.chkSingleTrial = QtWidgets.QCheckBox("Single trial", self.layoutWidget)
        self.chkSingleTrial.setObjectName("chkSingleTrial")
        self.singleTrialRow.addWidget(self.chkSingleTrial)

        self.spnSingleTrial = QtWidgets.QSpinBox(self.layoutWidget)
        self.spnSingleTrial.setObjectName("spnSingleTrial")
        self.spnSingleTrial.setEnabled(False)
        self.spnSingleTrial.setMinimum(1)
        self.spnSingleTrial.setAlignment(QtCore.Qt.AlignCenter)
        self.singleTrialRow.addStretch(1)
        self.singleTrialRow.addWidget(self.spnSingleTrial)

        self.trialsSelection.addLayout(self.singleTrialRow)

        # Add section to main layout
        self.paramsLayout.addLayout(self.trialsSelection)

        # --- Range Section ---
        self.rangeSection = QtWidgets.QVBoxLayout()
        self.rangeSection.setObjectName("rangeSection")

        self.rangeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.rangeLabel.setObjectName("rangeLabel")
        self.rangeLabel.setProperty("variant", "subtitle")
        self.rangeSection.addWidget(self.rangeLabel)

        self.rangeLine = QtWidgets.QFrame(self.layoutWidget)
        self.rangeLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.rangeLine.setObjectName("rangeLine")
        self.rangeLine.setProperty("role", "divider")
        self.rangeSection.addWidget(self.rangeLine)

        # Row: Trials range
        self.rangeRow = QtWidgets.QHBoxLayout()
        self.rangeRow.setObjectName("rangeRow")

        self.chkUseRange = QtWidgets.QCheckBox(self.layoutWidget)
        self.chkUseRange.setObjectName("chkUseRange")
        self.chkUseRange.setChecked(False)
        self.rangeRow.addWidget(self.chkUseRange)

        self.spnFrom = QtWidgets.QSpinBox(self.layoutWidget)
        self.spnFrom.setObjectName("spnFrom")
        self.spnFrom.setEnabled(False)
        self.spnFrom.setMinimum(1)
        self.spnFrom.setAlignment(QtCore.Qt.AlignCenter)
        self.rangeRow.addWidget(self.spnFrom)

        self.toLabel = QtWidgets.QLabel(self.layoutWidget)
        self.toLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.toLabel.setProperty("variant", "input")
        self.rangeRow.addWidget(self.toLabel)

        self.spnTo = QtWidgets.QSpinBox(self.layoutWidget)
        self.spnTo.setObjectName("spnTo")
        self.spnTo.setEnabled(False)
        self.spnTo.setMinimum(1)
        self.spnTo.setAlignment(QtCore.Qt.AlignCenter)
        self.rangeRow.addWidget(self.spnTo)

        self.rangeRow.addStretch(1)
        self.rangeSection.addLayout(self.rangeRow)

        self.paramsLayout.addLayout(self.rangeSection)

        # --- Filter trials ---
        self.trialsSection = QtWidgets.QVBoxLayout()
        self.trialsSection.setObjectName("trialsSection")

        self.trialsLabel = QtWidgets.QLabel(self.layoutWidget)
        self.trialsLabel.setObjectName("trialsLabel")
        self.trialsLabel.setProperty("variant", "subtitle")
        self.trialsSection.addWidget(self.trialsLabel)

        self.trialsLine = QtWidgets.QFrame(self.layoutWidget)
        self.trialsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.trialsLine.setObjectName("trialsLine")
        self.trialsLine.setProperty("role", "divider")
        self.trialsSection.addWidget(self.trialsLine)

        # --- Group: Trials (filter + list) ---
        # Filter input
        self.trialsFilterLayout = QtWidgets.QHBoxLayout()
        self.trialsFilterLayout.setObjectName("trialsFilterLayout")

        self.txtFilter = QtWidgets.QLineEdit(self.layoutWidget)
        self.txtFilter.setObjectName("txtFilter")
        self.txtFilter.setPlaceholderText("Filter…")
        self.trialsFilterLayout.addWidget(self.txtFilter)

        self.trialsSection.addLayout(self.trialsFilterLayout)

        # Trials list
        self.lstTrials = QtWidgets.QListWidget(self.layoutWidget)
        self.lstTrials.setObjectName("lstTrials")
        self.lstTrials.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.lstTrials.setAlternatingRowColors(True)
        self.lstTrials.setMinimumHeight(120)
        self.trialsSection.addWidget(self.lstTrials)

        self.paramsLayout.addLayout(self.trialsSection)

        # --- Spacer ---
        self.paramsLayout.addStretch(1)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self._wireDefaultState()
        self.retranslateUi(Average)
        QtCore.QMetaObject.connectSlotsByName(Average)

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

    def retranslateUi(self, Average):
        _translate = QtCore.QCoreApplication.translate
        Average.setWindowTitle(_translate("Average", "Average"))
        self.parametersLabel.setText(_translate("Average", "Parameters"))
        self.trialsSelectionLabel.setText(_translate("Average", "Trials"))
        self.rangeLabel.setText(_translate("Average", "Range"))
        self.toLabel.setText(_translate("Average", "To"))
        self.trialsLabel.setText(_translate("Average", "List"))
        self.calculateAverageButton.setText(_translate("Average", "Generate"))

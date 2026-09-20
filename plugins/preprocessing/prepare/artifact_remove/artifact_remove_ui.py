from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_ArtifactRemove(object):
    def setupUi(self, ArtifactRemove):
        ArtifactRemove.setObjectName("ArtifactRemove")

        # === Main layout ===
        self.mainWindow = QtWidgets.QHBoxLayout(ArtifactRemove)
        self.mainWindow.setObjectName("mainWindow")
        self.mainWindow.setSpacing(0)

        # === Splitter ===
        self.splitter = QtWidgets.QSplitter(ArtifactRemove)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")
        self.mainWindow.addWidget(self.splitter)

        # === Left Plot Area ===
        self.plotArea = QtWidgets.QFrame(self.splitter)
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setFrameShadow(QtWidgets.QFrame.Raised)
        self.plotArea.setObjectName("plotArea")

        # === Right: Parameters panel (fixed header + scrollable body) ===
        self.rightContainer = QtWidgets.QWidget(self.splitter)
        self.rightLayoutOuter = QtWidgets.QVBoxLayout(self.rightContainer)
        self.rightLayoutOuter.setContentsMargins(8, 0, 8, 0)
        self.rightLayoutOuter.setSpacing(0)

        # --- Header: Parameters + clear + Remove (always visible, not scrollable) ---
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

        self.apply_button = QtWidgets.QPushButton(self.rightContainer)
        self.apply_button.setObjectName("headerGenerateButton")
        self.headerLayout.addWidget(self.apply_button)

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

        # === Total Trials / Current Trial readout ===
        self.totalTrialsRow = QtWidgets.QHBoxLayout()
        self.totalTrialsLabel = QtWidgets.QLabel(self.layoutWidget)
        self.totalTrialsLabel.setObjectName("totalTrialsLabel")
        self.totalTrialsLabel.setProperty("variant", "subtitle")
        self.totalTrialsRow.addWidget(self.totalTrialsLabel)
        self.totalTrialsRow.addStretch(1)
        self.totalTrialsValueBox = QtWidgets.QLineEdit(self.layoutWidget)
        self.totalTrialsValueBox.setObjectName("totalTrialsValueBox")
        self.totalTrialsValueBox.setReadOnly(True)
        self.totalTrialsValueBox.setMaximumWidth(140)
        self.totalTrialsValueBox.setStyleSheet("QLineEdit { max-width: 140px; }")
        self.totalTrialsValueBox.setAlignment(QtCore.Qt.AlignCenter)
        self.totalTrialsRow.addWidget(self.totalTrialsValueBox)
        self.paramsLayout.addLayout(self.totalTrialsRow)

        self.currentTrialRow = QtWidgets.QHBoxLayout()
        self.currentTrialLabel = QtWidgets.QLabel(self.layoutWidget)
        self.currentTrialLabel.setObjectName("currentTrialLabel")
        self.currentTrialLabel.setProperty("variant", "subtitle")
        self.currentTrialRow.addWidget(self.currentTrialLabel)
        self.currentTrialRow.addStretch(1)
        self.currentTrialValueBox = QtWidgets.QLineEdit(self.layoutWidget)
        self.currentTrialValueBox.setObjectName("currentTrialValueBox")
        self.currentTrialValueBox.setReadOnly(True)
        self.currentTrialValueBox.setMaximumWidth(140)
        self.currentTrialValueBox.setStyleSheet("QLineEdit { max-width: 140px; }")
        self.currentTrialValueBox.setAlignment(QtCore.Qt.AlignCenter)
        self.currentTrialRow.addWidget(self.currentTrialValueBox)
        self.paramsLayout.addLayout(self.currentTrialRow)

        # Kept for the plugin's existing status text (not shown in the reference layout,
        # but the plugin logic still writes richer "Viewing Valid X/Y..." text into it).
        self.trial_status_label = QtWidgets.QLabel(self.layoutWidget)
        self.trial_status_label.setObjectName("trial_status_label")
        self.trial_status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.trial_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.trial_status_label.setVisible(False)
        self.paramsLayout.addWidget(self.trial_status_label)

        # === Mode ===
        self.modeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.modeLabel.setObjectName("modeLabel")
        self.modeLabel.setProperty("variant", "subtitle")
        self.paramsLayout.addWidget(self.modeLabel)

        self.modeLine = QtWidgets.QFrame(self.layoutWidget)
        self.modeLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.modeLine.setObjectName("modeLine")
        self.modeLine.setProperty("role", "divider")
        self.paramsLayout.addWidget(self.modeLine)

        self.modeNameLabel = QtWidgets.QLabel(self.layoutWidget)
        self.modeNameLabel.setObjectName("modeNameLabel")
        self.modeNameLabel.setText("Name")
        self.modeNameLabel.setProperty("variant", "input")
        self.paramsLayout.addWidget(self.modeNameLabel)

        self.mode_combo = QtWidgets.QComboBox(self.layoutWidget)
        self.mode_combo.setObjectName("mode_combo")
        self.paramsLayout.addWidget(self.mode_combo)

        # === Points (two columns, side by side) ===
        self.pointsLabel = QtWidgets.QLabel(self.layoutWidget)
        self.pointsLabel.setObjectName("pointsLabel")
        self.pointsLabel.setProperty("variant", "subtitle")
        self.paramsLayout.addWidget(self.pointsLabel)

        self.pointsLine = QtWidgets.QFrame(self.layoutWidget)
        self.pointsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.pointsLine.setObjectName("pointsLine")
        self.pointsLine.setProperty("role", "divider")
        self.paramsLayout.addWidget(self.pointsLine)

        self.pointsBodyRow = QtWidgets.QHBoxLayout()

        self.pointACol = QtWidgets.QVBoxLayout()
        self.label_a = QtWidgets.QLabel(self.layoutWidget)
        self.label_a.setObjectName("label_a")
        self.label_a.setProperty("variant", "input")
        self.pointACol.addWidget(self.label_a)
        self.point_a = QtWidgets.QLineEdit(self.layoutWidget)
        self.point_a.setObjectName("point_a")
        self.point_a.setAlignment(QtCore.Qt.AlignCenter)
        self.pointACol.addWidget(self.point_a)
        self.pointsBodyRow.addLayout(self.pointACol, 1)

        self.pointBCol = QtWidgets.QVBoxLayout()
        self.label_b = QtWidgets.QLabel(self.layoutWidget)
        self.label_b.setObjectName("label_b")
        self.label_b.setProperty("variant", "input")
        self.pointBCol.addWidget(self.label_b)
        self.point_b = QtWidgets.QLineEdit(self.layoutWidget)
        self.point_b.setObjectName("point_b")
        self.point_b.setAlignment(QtCore.Qt.AlignCenter)
        self.pointBCol.addWidget(self.point_b)
        self.pointsBodyRow.addLayout(self.pointBCol, 1)

        self.paramsLayout.addLayout(self.pointsBodyRow)

        # === Trials (navigation, at the bottom like the other Preprocessing panels) ===
        self.trialsLabel = QtWidgets.QLabel(self.layoutWidget)
        self.trialsLabel.setObjectName("trialsLabel")
        self.trialsLabel.setProperty("variant", "subtitle")
        self.paramsLayout.addWidget(self.trialsLabel)

        self.trialsLine = QtWidgets.QFrame(self.layoutWidget)
        self.trialsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.trialsLine.setObjectName("trialsLine")
        self.trialsLine.setProperty("role", "divider")
        self.paramsLayout.addWidget(self.trialsLine)

        self.navigationLayout = QtWidgets.QHBoxLayout()
        self.navigationLayout.setObjectName("navigationLayout")

        self.prev_button = QtWidgets.QPushButton(self.layoutWidget)
        self.prev_button.setObjectName("trialNavButton")
        self.prev_button.setMinimumHeight(32)
        self.navigationLayout.addWidget(self.prev_button)

        self.next_button = QtWidgets.QPushButton(self.layoutWidget)
        self.next_button.setObjectName("trialNavButton")
        self.next_button.setMinimumHeight(32)
        self.navigationLayout.addWidget(self.next_button)

        self.paramsLayout.addLayout(self.navigationLayout)

        self.paramsLayout.addStretch(1)

        self.splitter.setSizes([700, 300])

        # --- Stretch configuration (responsive panel) ---
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        # --- Retranslate & connections ---
        self.retranslateUi(ArtifactRemove)
        QtCore.QMetaObject.connectSlotsByName(ArtifactRemove)

        # --- Behavior ---
        self.mode_combo.addItems(["Interpolate Interval", "Cut From The Start"])
        self.point_a.setValidator(QtGui.QDoubleValidator())
        self.point_b.setValidator(QtGui.QDoubleValidator())
        self.mode_combo.currentIndexChanged.connect(self.update_ui_for_mode)
        self.update_ui_for_mode()

    def update_ui_for_mode(self):
        is_cut_mode = self.mode_combo.currentText() == "Cut From The Start"
        self.label_a.setText("Cut until (s):" if is_cut_mode else "Point A (s):")
        self.label_b.setVisible(not is_cut_mode)
        self.point_b.setVisible(not is_cut_mode)

    def retranslateUi(self, ArtifactRemove):
        _translate = QtCore.QCoreApplication.translate
        ArtifactRemove.setWindowTitle(_translate("ArtifactRemove", "Artifact Remove"))
        self.parametersLabel.setText(_translate("ArtifactRemove", "Parameters"))
        self.apply_button.setText(_translate("ArtifactRemove", "Remove"))
        self.totalTrialsLabel.setText(_translate("ArtifactRemove", "Total Trials"))
        self.currentTrialLabel.setText(_translate("ArtifactRemove", "Current Trial"))
        self.modeLabel.setText(_translate("ArtifactRemove", "Mode"))
        self.pointsLabel.setText(_translate("ArtifactRemove", "points"))
        self.trialsLabel.setText(_translate("ArtifactRemove", "Trials"))
        self.prev_button.setText(_translate("ArtifactRemove", "Previous"))
        self.next_button.setText(_translate("ArtifactRemove", "Next"))
        self.trial_status_label.setText(_translate("ArtifactRemove", "Trial: - / -"))
        self.label_a.setText(_translate("ArtifactRemove", "Point A (s):"))
        self.label_b.setText(_translate("ArtifactRemove", "Point B (s):"))

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

        # === Right Scroll Area ===
        self.scrollArea = QtWidgets.QScrollArea(self.splitter)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scrollArea.setObjectName("scrollArea")

        # === Scroll Widget ===
        self.layoutWidget = QtWidgets.QWidget()
        self.layoutWidget.setObjectName("layoutWidget")
        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setObjectName("paramsLayout")
        self.paramsLayout.setContentsMargins(8, 0, 8, 0)
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

        # === Artifact Removal Section ===
        self.artifactLayout = QtWidgets.QVBoxLayout()
        self.artifactLayout.setObjectName("artifactLayout")

        self.artifactLabel = QtWidgets.QLabel(self.layoutWidget)
        self.artifactLabel.setObjectName("artifactLabel")
        self.artifactLabel.setProperty("variant", "subtitle")
        self.artifactLayout.addWidget(self.artifactLabel)

        self.artifactLine = QtWidgets.QFrame(self.layoutWidget)
        self.artifactLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.artifactLine.setObjectName("artifactLine")
        self.artifactLine.setProperty("role", "divider")
        self.artifactLayout.addWidget(self.artifactLine)

        # --- Navigation ---
        self.navigationLayout = QtWidgets.QHBoxLayout()
        self.navigationLayout.setObjectName("navigationLayout")

        self.prev_button = QtWidgets.QPushButton(self.layoutWidget)
        self.prev_button.setObjectName("trialNavButton")
        self.navigationLayout.addWidget(self.prev_button)

        self.next_button = QtWidgets.QPushButton(self.layoutWidget)
        self.next_button.setObjectName("trialNavButton")
        self.navigationLayout.addWidget(self.next_button)

        self.artifactLayout.addLayout(self.navigationLayout)

        # Trial status
        self.trial_status_label = QtWidgets.QLabel(self.layoutWidget)
        self.trial_status_label.setObjectName("trial_status_label")
        self.trial_status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.trial_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.artifactLayout.addWidget(self.trial_status_label)

        # --- Mode Section ---
        self.modeLayout = QtWidgets.QVBoxLayout()
        self.modeLayout.setObjectName("modeLayout")

        self.modeLabel = QtWidgets.QLabel(self.layoutWidget)
        self.modeLabel.setObjectName("modeLabel")
        self.modeLabel.setProperty("variant", "subtitle")
        self.modeLayout.addWidget(self.modeLabel)

        self.modeLine = QtWidgets.QFrame(self.layoutWidget)
        self.modeLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.modeLine.setObjectName("modeLine")
        self.modeLine.setProperty("role", "divider")
        self.modeLayout.addWidget(self.modeLine)

        self.mode_combo = QtWidgets.QComboBox(self.layoutWidget)
        self.mode_combo.setObjectName("mode_combo")
        self.modeLayout.addWidget(self.mode_combo)
        self.artifactLayout.addLayout(self.modeLayout)

        # --- Points ---
        self.pointsLayout = QtWidgets.QVBoxLayout()
        self.pointsLayout.setObjectName("pointsLayout")

        self.pointsLabel = QtWidgets.QLabel(self.layoutWidget)
        self.pointsLabel.setObjectName("pointsLabel")
        self.pointsLabel.setProperty("variant", "subtitle")
        self.pointsLayout.addWidget(self.pointsLabel)

        self.pointsLine = QtWidgets.QFrame(self.layoutWidget)
        self.pointsLine.setFrameShape(QtWidgets.QFrame.HLine)
        self.pointsLine.setObjectName("pointsLine")
        self.pointsLine.setProperty("role", "divider")
        self.pointsLayout.addWidget(self.pointsLine)

        # --- Point A ---
        self.pointALayout = QtWidgets.QHBoxLayout()
        self.pointALayout.setObjectName("pointALayout")

        self.label_a = QtWidgets.QLabel(self.layoutWidget)
        self.label_a.setObjectName("label_a")
        self.label_a.setProperty("variant", "input")
        self.pointALayout.addWidget(self.label_a)

        self.point_a = QtWidgets.QLineEdit(self.layoutWidget)
        self.point_a.setObjectName("point_a")
        self.point_a.setAlignment(QtCore.Qt.AlignCenter)
        self.pointALayout.addWidget(self.point_a)
        self.pointsLayout.addLayout(self.pointALayout)

        # --- Point B ---
        self.pointBLayout = QtWidgets.QHBoxLayout()
        self.pointBLayout.setObjectName("pointBLayout")

        self.label_b = QtWidgets.QLabel(self.layoutWidget)
        self.label_b.setObjectName("label_b")
        self.label_b.setProperty("variant", "input")
        self.pointBLayout.addWidget(self.label_b)

        self.point_b = QtWidgets.QLineEdit(self.layoutWidget)
        self.point_b.setObjectName("point_b")
        self.point_b.setAlignment(QtCore.Qt.AlignCenter)
        self.pointBLayout.addWidget(self.point_b)
        self.pointsLayout.addLayout(self.pointBLayout)

        # --- Add Artifact section to panel ---
        self.artifactLayout.addLayout(self.pointsLayout)
        self.paramsLayout.addLayout(self.artifactLayout)

        # --- Apply Button ---
        self.paramsLayout.addStretch(1)
        self.apply_button = QtWidgets.QPushButton(self.layoutWidget)
        self.apply_button.setObjectName("mainActionButton")
        self.paramsLayout.addWidget(self.apply_button)

        # --- Add scroll area to splitter ---
        self.splitter.addWidget(self.scrollArea)

        # --- Stretch configuration (responsive panel) ---
        # Give the plot more space but allow the panel to grow/shrink too
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        # Keep a sensible minimum width so the panel doesn't collapse
        self.layoutWidget.setMinimumWidth(280)
        self.scrollArea.setMinimumWidth(300)

        # --- Retranslate & connections ---
        self.retranslateUi(ArtifactRemove)
        QtCore.QMetaObject.connectSlotsByName(ArtifactRemove)

        # --- Behavior ---
        self.mode_combo.addItems(["Interpolate Interval", "Cut From Start"])
        self.point_a.setValidator(QtGui.QDoubleValidator())
        self.point_b.setValidator(QtGui.QDoubleValidator())
        self.mode_combo.currentIndexChanged.connect(self.update_ui_for_mode)
        self.update_ui_for_mode()

    def update_ui_for_mode(self):
        is_cut_mode = self.mode_combo.currentText() == "Cut From Start"
        self.label_a.setText("Cut until (s):" if is_cut_mode else "Point A (s):")
        self.label_b.setVisible(not is_cut_mode)
        self.point_b.setVisible(not is_cut_mode)

    def retranslateUi(self, ArtifactRemove):
        _translate = QtCore.QCoreApplication.translate
        ArtifactRemove.setWindowTitle(_translate("ArtifactRemove", "Artifact Remove"))
        self.parametersLabel.setText(_translate("ArtifactRemove", "Parameters"))
        self.artifactLabel.setText(_translate("ArtifactRemove", "Artifact Removal"))
        self.prev_button.setText(_translate("ArtifactRemove", "Previous"))
        self.next_button.setText(_translate("ArtifactRemove", "Next"))
        self.trial_status_label.setText(_translate("ArtifactRemove", "Trial: - / -"))
        self.modeLabel.setText(_translate("ArtifactRemove", "Mode"))
        self.pointsLabel.setText(_translate("ArtifactRemove", "Points"))
        self.label_a.setText(_translate("ArtifactRemove", "Point A (s):"))
        self.label_b.setText(_translate("ArtifactRemove", "Point B (s):"))
        self.apply_button.setText(_translate("ArtifactRemove", "Remove Artifact"))

from PyQt5 import QtCore, QtGui, QtWidgets
import os


class Ui_ModulationIndex(object):

    def setupUi(self, ModulationIndex):
        ModulationIndex.setObjectName("ModulationIndex")
        ModulationIndex.resize(825, 609)

        self.mainWindow = QtWidgets.QHBoxLayout(ModulationIndex)
        self.mainWindow.setObjectName("mainWindow")
        self.mainWindow.setSpacing(0)

        self.splitter = QtWidgets.QSplitter(ModulationIndex)
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

        # ===== Header: Parameters + clear + Generate (always visible) =====
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

        self.generateButton = QtWidgets.QPushButton(self.rightContainer)
        self.generateButton.setObjectName("headerGenerateButton")
        self.headerLayout.addWidget(self.generateButton)

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

        self.splitter.widget(1).setMaximumWidth(300)

        # --- Sample frequency ---
        # MI la necesita: f_PAC_sing recibe `srt` y hace downsample(v_Data, srt).
        # En MATLAB la lee de `ResampleFr`, que vive en el panel Frequency y vale
        # 1000 —no del campo de 2000 que esta dibujado justo al lado del boton MI,
        # que es el de PAC—. Aqui lleva el suyo propio: un plugin no lee los
        # widgets de otro.
        self.sampleSection = self._section_layout("sampleFqLabel")
        self.sampleFqLabel = self.sampleSection.title
        self.sampleFqRowLabel, self.sampleFqSpinBox, self.sampleFqHzLabel = \
            self._add_spin_row(self.sampleSection, "sampleFq", QtWidgets.QSpinBox)
        self.paramsLayout.addLayout(self.sampleSection)

        # --- Phase band ---
        self.phaseSection = self._section_layout("phaseBandLabel")
        self.phaseBandLabel = self.phaseSection.title
        self.fqP1Label, self.fqP1SpinBox, self.fqP1HzLabel = self._add_spin_row(self.phaseSection, "fqP1")
        self.fqP2Label, self.fqP2SpinBox, self.fqP2HzLabel = self._add_spin_row(self.phaseSection, "fqP2")
        self.pStepLabel, self.pStepSpinBox, self.pStepHzLabel = self._add_spin_row(self.phaseSection, "pStep")
        self.paramsLayout.addLayout(self.phaseSection)

        # --- Amplitude band ---
        self.amplitudeSection = self._section_layout("amplitudeBandLabel")
        self.amplitudeBandLabel = self.amplitudeSection.title
        self.fqA1Label, self.fqA1SpinBox, self.fqA1HzLabel = self._add_spin_row(self.amplitudeSection, "fqA1")
        self.fqA2Label, self.fqA2SpinBox, self.fqA2HzLabel = self._add_spin_row(self.amplitudeSection, "fqA2")
        self.aStepLabel, self.aStepSpinBox, self.aStepHzLabel = self._add_spin_row(self.amplitudeSection, "aStep")
        self.paramsLayout.addLayout(self.amplitudeSection)

        # --- Trial ---
        # f_PAC_sing hace v_Data(:,Tr): trabaja sobre UN trial, como PAC. En
        # MATLAB es una casilla numerica global; aqui lleva ademas flechas,
        # porque la directora pidio poder navegar entre los trials.
        self.trialSection = self._section_layout("trialLabel")
        self.trialLabel = self.trialSection.title
        self.prevTrialButton, self.trialSpinBox, self.nextTrialButton, self.trialTotalLabel = \
            self._add_trial_row(self.trialSection)
        self.paramsLayout.addLayout(self.trialSection)

        # --- Spacer ---
        self.paramsLayout.addStretch(1)

        # Size splitter
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(ModulationIndex)
        QtCore.QMetaObject.connectSlotsByName(ModulationIndex)

    # ---------- helpers (same widgets/properties the other plugins build by hand) ----------
    def _section_layout(self, title_name):
        section = QtWidgets.QVBoxLayout()
        section.setObjectName(title_name + "Layout")

        title = QtWidgets.QLabel(self.layoutWidget)
        title.setObjectName(title_name)
        title.setProperty("variant", "subtitle")
        section.addWidget(title)

        line = QtWidgets.QFrame(self.layoutWidget)
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setObjectName(title_name + "Line")
        line.setProperty("role", "divider")
        section.addWidget(line)

        section.title = title
        return section

    def _add_spin_row(self, section, name, spin_class=QtWidgets.QDoubleSpinBox):
        row = QtWidgets.QHBoxLayout()
        row.setObjectName(name + "Layout")

        label = QtWidgets.QLabel(self.layoutWidget)
        label.setObjectName(name + "Label")
        label.setProperty("variant", "input")
        row.addWidget(label)

        spin = spin_class(self.layoutWidget)
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setObjectName(name + "SpinBox")
        row.addWidget(spin)

        hz_label = QtWidgets.QLabel(self.layoutWidget)
        hz_label.setObjectName(name + "HzLabel")
        hz_label.setProperty("variant", "input")
        row.addWidget(hz_label)

        section.addLayout(row)
        return label, spin, hz_label

    def _add_trial_row(self, section):
        """La fila del trial: flecha, casilla, flecha y el «de N»."""
        row = QtWidgets.QHBoxLayout()
        row.setObjectName("trialLayout")

        anterior = QtWidgets.QToolButton(self.layoutWidget)
        anterior.setObjectName("prevTrialButton")
        anterior.setCursor(QtCore.Qt.PointingHandCursor)
        row.addWidget(anterior)

        # Muestra 1 para el primer trial, como MATLAB; el plugin resta uno al
        # indexar, porque Python cuenta desde cero.
        spin = QtWidgets.QSpinBox(self.layoutWidget)
        spin.setAlignment(QtCore.Qt.AlignCenter)
        spin.setMinimum(1)
        spin.setObjectName("trialSpinBox")
        row.addWidget(spin)

        siguiente = QtWidgets.QToolButton(self.layoutWidget)
        siguiente.setObjectName("nextTrialButton")
        siguiente.setCursor(QtCore.Qt.PointingHandCursor)
        row.addWidget(siguiente)

        total = QtWidgets.QLabel(self.layoutWidget)
        total.setObjectName("trialTotalLabel")
        total.setProperty("variant", "input")
        row.addWidget(total)

        section.addLayout(row)
        return anterior, spin, siguiente, total

    def retranslateUi(self, ModulationIndex):
        _translate = QtCore.QCoreApplication.translate
        ModulationIndex.setWindowTitle(_translate("ModulationIndex", "Modulation Index"))

        self.parametersLabel.setText(_translate("ModulationIndex", "Parameters"))
        self.generateButton.setText(_translate("ModulationIndex", "Generate"))

        self.sampleFqLabel.setText(_translate("ModulationIndex", "Sample frequency"))
        self.sampleFqRowLabel.setText(_translate("ModulationIndex", ""))
        self.sampleFqHzLabel.setText(_translate("ModulationIndex", "Hz"))

        self.trialLabel.setText(_translate("ModulationIndex", "Trial"))
        self.prevTrialButton.setText(_translate("ModulationIndex", "◄"))
        self.nextTrialButton.setText(_translate("ModulationIndex", "►"))
        self.trialTotalLabel.setText(_translate("ModulationIndex", "de 0"))

        self.phaseBandLabel.setText(_translate("ModulationIndex", "Phase Band"))
        self.fqP1Label.setText(_translate("ModulationIndex", "Fq P1"))
        self.fqP2Label.setText(_translate("ModulationIndex", "Fq P2"))
        self.pStepLabel.setText(_translate("ModulationIndex", "P step"))

        self.amplitudeBandLabel.setText(_translate("ModulationIndex", "Amplitude Band"))
        self.fqA1Label.setText(_translate("ModulationIndex", "Fq A1"))
        self.fqA2Label.setText(_translate("ModulationIndex", "Fq A2"))
        self.aStepLabel.setText(_translate("ModulationIndex", "A step"))

        for hz in (self.fqP1HzLabel, self.fqP2HzLabel, self.pStepHzLabel,
                   self.fqA1HzLabel, self.fqA2HzLabel, self.aStepHzLabel):
            hz.setText(_translate("ModulationIndex", "Hz"))

from PyQt5 import QtCore, QtWidgets

class Ui_Trials(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        self.setObjectName("TrialsWidget")

        # ===== Root =====
        self._root = QtWidgets.QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 5, 0)
        self._root.setSpacing(0)

        # ===== Splitter L/R =====
        self.splitter = QtWidgets.QSplitter(self)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self._root.addWidget(self.splitter)

        # ----- Left: VTK viewer frame (keep name) -----
        self.plotArea = QtWidgets.QFrame(self.splitter)
        self.plotArea.setObjectName("plotArea")
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setFrameShadow(QtWidgets.QFrame.Raised)
        self.plotArea.setMinimumWidth(520)

        # ----- Right: Parameters panel con scroll -----
        self.scrollArea = QtWidgets.QScrollArea(self.splitter)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Contenedor interno del scroll
        self.panel = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.panel)
        self.vbox.setContentsMargins(8, 0, 8, 0)
        self.vbox.setSpacing(12)

        # Asignar el panel como contenido del scroll
        self.scrollArea.setWidget(self.panel)
        self.splitter.setSizes([700, 300])

        # ===== Header: Parameters =====
        self.lblParameters = QtWidgets.QLabel(self.panel)
        self.lblParameters.setText("Parameters")
        self.lblParameters.setProperty("variant", "title")     # 👈
        self.vbox.addWidget(self.lblParameters)

        self.sep0 = QtWidgets.QFrame(self.panel)
        self.sep0.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep0.setProperty("role", "section-divider")       # 👈
        self.vbox.addWidget(self.sep0)

        # ===== Subtitle: Channel =====
        self.lblChannelTitle = QtWidgets.QLabel(self.panel)
        self.lblChannelTitle.setText("Channel")
        self.lblChannelTitle.setProperty("variant", "subtitle")  # 👈
        self.vbox.addWidget(self.lblChannelTitle)

        self.sep1 = QtWidgets.QFrame(self.panel)
        self.sep1.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep1.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep1.setProperty("role", "divider")                 # 👈
        self.vbox.addWidget(self.sep1)

        # --- Form Channel ---
        self.formChannel = QtWidgets.QFormLayout()
        self.formChannel.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.formChannel.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        self.channelLabel = QtWidgets.QLabel(self.panel)
        self.channelLabel.setText("Name")
        self.channelLabel.setProperty("variant", "input")        # 👈
        self.channelComboBox = QtWidgets.QComboBox(self.panel)
        self.channelComboBox.setObjectName("channelComboBox")
        self.formChannel.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.channelLabel)
        self.formChannel.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.channelComboBox)

        self.vbox.addLayout(self.formChannel)

        # ===== Subtitle: Stim Channel =====
        self.lblStimChanTitle = QtWidgets.QLabel(self.panel)
        self.lblStimChanTitle.setText("Stim Channel")
        self.lblStimChanTitle.setProperty("variant", "subtitle")  # 👈
        self.vbox.addWidget(self.lblStimChanTitle)

        self.sep1b = QtWidgets.QFrame(self.panel)
        self.sep1b.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep1b.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep1b.setProperty("role", "divider")                 # 👈
        self.vbox.addWidget(self.sep1b)

        self.formStimChan = QtWidgets.QFormLayout()
        self.formStimChan.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.formStimChan.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        self.stimChannelLabel = QtWidgets.QLabel(self.panel)
        self.stimChannelLabel.setText("Name")
        self.stimChannelLabel.setProperty("variant", "input")     # 👈

        self.stimChannelComboBox = QtWidgets.QComboBox(self.panel)
        self.stimChannelComboBox.setObjectName("stimChannelComboBox")
        self.stimChannelComboBox.setToolTip("Channel used to detect onsets/stimuli")

        self.formStimChan.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.stimChannelLabel)
        self.formStimChan.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.stimChannelComboBox)

        self.vbox.addLayout(self.formStimChan)

        # ===== Subtitle: Threshold =====
        self.lblThTitle = QtWidgets.QLabel(self.panel)
        self.lblThTitle.setText("Threshold")
        self.lblThTitle.setProperty("variant", "subtitle")        # 👈
        self.vbox.addWidget(self.lblThTitle)

        self.sep2 = QtWidgets.QFrame(self.panel)
        self.sep2.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep2.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep2.setProperty("role", "divider")                  # 👈
        self.vbox.addWidget(self.sep2)

        self.formTh = QtWidgets.QFormLayout()
        self.formTh.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.thresholdLabel = QtWidgets.QLabel(self.panel)
        self.thresholdLabel.setText("")
        self.thresholdLabel.setProperty("variant", "input")       # left intentionally blank
        self.thresholdDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.panel)
        self.thresholdDoubleSpinBox.setDecimals(4)
        self.thresholdDoubleSpinBox.setRange(-1e9, 1e9)
        self.thresholdDoubleSpinBox.setSingleStep(0.01)
        self.thresholdDoubleSpinBox.setValue(0.05)
        self.thresholdDoubleSpinBox.setSuffix(" Hz")
        self.formTh.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.thresholdLabel)
        self.formTh.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.thresholdDoubleSpinBox)

        self.vbox.addLayout(self.formTh)

        # ===== Subtitle: Stim Number =====
        self.lblStimTitle = QtWidgets.QLabel(self.panel)
        self.lblStimTitle.setText("Stim Number")
        self.lblStimTitle.setProperty("variant", "subtitle")       # 👈
        self.vbox.addWidget(self.lblStimTitle)

        self.sep3 = QtWidgets.QFrame(self.panel)
        self.sep3.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep3.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep3.setProperty("role", "divider")                   # 👈
        self.vbox.addWidget(self.sep3)

        self.formStim = QtWidgets.QFormLayout()
        self.formStim.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.stimNumberLabel = QtWidgets.QLabel(self.panel)
        self.stimNumberLabel.setText("")
        self.stimNumberLabel.setProperty("variant", "input")       # 👈
        self.stimNumberSpinBox = QtWidgets.QSpinBox(self.panel)
        self.stimNumberSpinBox.setRange(0, 1_000_000)
        self.stimNumberSpinBox.setValue(1)
        self.formStim.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.stimNumberLabel)
        self.formStim.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.stimNumberSpinBox)

        self.vbox.addLayout(self.formStim)

        # ===== Subtitle: Time =====
        self.lblTimeTitle = QtWidgets.QLabel(self.panel)
        self.lblTimeTitle.setText("Time")
        self.lblTimeTitle.setProperty("variant", "subtitle")        # 👈
        self.vbox.addWidget(self.lblTimeTitle)

        self.sep4 = QtWidgets.QFrame(self.panel)
        self.sep4.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep4.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep4.setProperty("role", "divider")                    # 👈
        self.vbox.addWidget(self.sep4)

        self.formTime = QtWidgets.QFormLayout()
        self.formTime.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.initialTimeLabel = QtWidgets.QLabel(self.panel)
        self.initialTimeLabel.setText("Initial Time")
        self.initialTimeLabel.setProperty("variant", "input")       # 👈
        self.initialTimeDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.panel)
        self.initialTimeDoubleSpinBox.setDecimals(4)
        self.initialTimeDoubleSpinBox.setRange(-1e9, 1e9)
        self.initialTimeDoubleSpinBox.setSingleStep(0.001)
        self.initialTimeDoubleSpinBox.setValue(-0.05)
        self.initialTimeDoubleSpinBox.setSuffix(" s")

        self.finalTimeLabel = QtWidgets.QLabel(self.panel)
        self.finalTimeLabel.setText("Final Time")
        self.finalTimeLabel.setProperty("variant", "input")         # 👈
        self.finalTimeDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.panel)
        self.finalTimeDoubleSpinBox.setDecimals(4)
        self.finalTimeDoubleSpinBox.setRange(-1e9, 1e9)
        self.finalTimeDoubleSpinBox.setSingleStep(0.001)
        self.finalTimeDoubleSpinBox.setValue(3.0)
        self.finalTimeDoubleSpinBox.setSuffix(" s")

        self.interStimTimeLabel = QtWidgets.QLabel(self.panel)
        self.interStimTimeLabel.setText("Inter Stim Time")
        self.interStimTimeLabel.setProperty("variant", "input")     # 👈
        self.interStimTimeDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.panel)
        self.interStimTimeDoubleSpinBox.setDecimals(4)
        self.interStimTimeDoubleSpinBox.setRange(-1e9, 1e9)
        self.interStimTimeDoubleSpinBox.setSingleStep(0.001)
        self.interStimTimeDoubleSpinBox.setValue(0.0)
        self.interStimTimeDoubleSpinBox.setSuffix(" s")
        

        # Trial End Mode
        self.endModeComboLabel = QtWidgets.QLabel(self.panel)
        self.endModeComboLabel.setText("Trial End Mode")
        self.endModeComboLabel.setProperty("variant", "input")      # 👈
        self.endModeCombo = QtWidgets.QComboBox(self.panel)
        self.endModeCombo.addItem("Cut to the next stim", userData="until_next_onset")
        self.endModeCombo.addItem("Fixed window", userData="fixed")

        self.formTime.addRow(self.initialTimeLabel, self.initialTimeDoubleSpinBox)
        self.formTime.addRow(self.finalTimeLabel, self.finalTimeDoubleSpinBox)
        self.formTime.addRow(self.interStimTimeLabel, self.interStimTimeDoubleSpinBox)
        self.formTime.addRow(self.endModeComboLabel, self.endModeCombo)

        self.vbox.addLayout(self.formTime)

        # ===== Subtitle: Trials =====
        self.lblTrialsTitle = QtWidgets.QLabel(self.panel)
        self.lblTrialsTitle.setText("Trials")
        self.lblTrialsTitle.setProperty("variant", "subtitle")      # 👈
        self.vbox.addWidget(self.lblTrialsTitle)

        self.sep5 = QtWidgets.QFrame(self.panel)
        self.sep5.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep5.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep5.setProperty("role", "divider")                    # 👈
        self.vbox.addWidget(self.sep5)

        # ==== Trials navigation buttons ====
        self.trialNavLayout = QtWidgets.QHBoxLayout()

        self.Btn_prev_trial = QtWidgets.QPushButton(self.panel)
        self.Btn_prev_trial.setObjectName("trialNavButton")
        self.Btn_prev_trial.setText("Previous")
        self.Btn_prev_trial.setMinimumHeight(32)
        self.trialNavLayout.addWidget(self.Btn_prev_trial)

        self.Btn_next_trial = QtWidgets.QPushButton(self.panel)
        self.Btn_next_trial.setObjectName("trialNavButton")
        self.Btn_next_trial.setText("Next")
        self.Btn_next_trial.setMinimumHeight(32)
        self.trialNavLayout.addWidget(self.Btn_next_trial)

        self.Btn_discard_trial = QtWidgets.QPushButton(self.panel)
        self.Btn_discard_trial.setObjectName("trialNavButton")
        self.Btn_discard_trial.setText("Discard")
        self.Btn_discard_trial.setMinimumHeight(32)
        self.trialNavLayout.addWidget(self.Btn_discard_trial)

        self.vbox.addLayout(self.trialNavLayout)

        # label para numero de trial revisado
        self.currentTrialLabel = QtWidgets.QLabel(self.panel)
        self.currentTrialLabel.setText("Current Trial : -")
        self.currentTrialLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.currentTrialLabel.setProperty("variant", "subtitle")    # 👈
        self.vbox.addWidget(self.currentTrialLabel)

        # ===== Spacer & Actions =====
        self.vbox.addStretch(1)

        self.Btn_generate_trials = QtWidgets.QPushButton(self.panel)
        self.Btn_generate_trials.setObjectName("mainActionButton")
        self.Btn_generate_trials.setText("Generate Trials")
        self.Btn_generate_trials.setMinimumHeight(36)
        self.vbox.addWidget(self.Btn_generate_trials)

        # Default splitter sizes
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi()

    def retranslateUi(self):
        self.setWindowTitle("Trials")

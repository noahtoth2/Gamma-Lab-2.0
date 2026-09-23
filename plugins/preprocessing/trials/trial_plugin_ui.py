from PyQt5 import QtCore, QtGui, QtWidgets

from core.utils.results_tables_widget import ResultsTablesWidget

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

        # ----- Left: VTK viewer (top) + Results panel (bottom) -----
        self.plotSplitter = QtWidgets.QSplitter(self.splitter)
        self.plotSplitter.setOrientation(QtCore.Qt.Vertical)
        self.plotSplitter.setObjectName("plotSplitter")
        self.plotSplitter.setMinimumWidth(520)

        self.plotArea = QtWidgets.QFrame(self.plotSplitter)
        self.plotArea.setObjectName("plotArea")
        self.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.plotArea.setFrameShadow(QtWidgets.QFrame.Raised)

        self.resultsPanel = ResultsTablesWidget(self.plotSplitter)
        self.resultsPanel.setObjectName("resultsPanel")

        self.plotSplitter.setStretchFactor(0, 1)
        self.plotSplitter.setStretchFactor(1, 0)

        # ----- Right: Parameters panel (fixed header + scrollable body) -----
        self.rightContainer = QtWidgets.QWidget(self.splitter)
        self.rightLayoutOuter = QtWidgets.QVBoxLayout(self.rightContainer)
        self.rightLayoutOuter.setContentsMargins(8, 0, 8, 0)
        self.rightLayoutOuter.setSpacing(0)

        # ===== Header: Parameters + clear + Generate (always visible, not scrollable) =====
        self.headerLayout = QtWidgets.QHBoxLayout()

        self.lblParameters = QtWidgets.QLabel(self.rightContainer)
        self.lblParameters.setText("Parameters")
        self.lblParameters.setProperty("variant", "title")     
        self.headerLayout.addWidget(self.lblParameters)

        self.headerLayout.addStretch(1)

        self.Btn_clear_params = QtWidgets.QToolButton(self.rightContainer)
        self.Btn_clear_params.setObjectName("clearParamsButton")
        self.Btn_clear_params.setIcon(QtGui.QIcon("assets/iconos/clear.png"))
        self.Btn_clear_params.setIconSize(QtCore.QSize(28, 28))
        self.Btn_clear_params.setAutoRaise(True)
        self.Btn_clear_params.setToolTip("Clear parameters")
        self.headerLayout.addWidget(self.Btn_clear_params)
        self.headerLayout.addSpacing(10)

        self.Btn_generate_trials = QtWidgets.QPushButton(self.rightContainer)
        self.Btn_generate_trials.setObjectName("headerGenerateButton")
        self.Btn_generate_trials.setText("Generate")
        self.headerLayout.addWidget(self.Btn_generate_trials)

        self.rightLayoutOuter.addLayout(self.headerLayout)

        self.sep0 = QtWidgets.QFrame(self.rightContainer)
        self.sep0.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep0.setProperty("role", "section-divider")       
        self.rightLayoutOuter.addWidget(self.sep0)

        # ===== Scrollable body (only scrolls if the panel is squeezed, e.g. by Results) =====
        self.scrollArea = QtWidgets.QScrollArea(self.rightContainer)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scrollArea.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.panel = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.panel)
        self.vbox.setContentsMargins(0, 10, 0, 0)
        self.vbox.setSpacing(6)

        self.scrollArea.setWidget(self.panel)
        self.rightLayoutOuter.addWidget(self.scrollArea)

        self.splitter.setSizes([700, 300])

        # ===== Total Trials / Current Trial readout =====
        self.totalTrialsRow = QtWidgets.QHBoxLayout()
        self.totalTrialsLabel = QtWidgets.QLabel(self.panel)
        self.totalTrialsLabel.setText("Total Trials")
        self.totalTrialsLabel.setProperty("variant", "subtitle")
        self.totalTrialsRow.addWidget(self.totalTrialsLabel)
        self.totalTrialsRow.addStretch(1)
        self.totalTrialsValueBox = QtWidgets.QLineEdit(self.panel)
        self.totalTrialsValueBox.setReadOnly(True)
        self.totalTrialsValueBox.setMaximumWidth(140)
        self.totalTrialsValueBox.setStyleSheet("QLineEdit { max-width: 140px; }")
        self.totalTrialsRow.addWidget(self.totalTrialsValueBox)
        self.vbox.addLayout(self.totalTrialsRow)

        self.currentTrialRow = QtWidgets.QHBoxLayout()
        self.currentTrialTitleLabel = QtWidgets.QLabel(self.panel)
        self.currentTrialTitleLabel.setText("Current Trial")
        self.currentTrialTitleLabel.setProperty("variant", "subtitle")
        self.currentTrialRow.addWidget(self.currentTrialTitleLabel)
        self.currentTrialRow.addStretch(1)
        self.currentTrialValueBox = QtWidgets.QLineEdit(self.panel)
        self.currentTrialValueBox.setReadOnly(True)
        self.currentTrialValueBox.setMaximumWidth(140)
        self.currentTrialValueBox.setStyleSheet("QLineEdit { max-width: 140px; }")
        self.currentTrialRow.addWidget(self.currentTrialValueBox)
        self.vbox.addLayout(self.currentTrialRow)

        # ===== Channel / Stim Channel (two columns, one shared header+divider) =====
        self.channelHeaderRow = QtWidgets.QHBoxLayout()

        self.lblChannelTitle = QtWidgets.QLabel(self.panel)
        self.lblChannelTitle.setText("Channel")
        self.lblChannelTitle.setProperty("variant", "subtitle")  
        self.channelHeaderRow.addWidget(self.lblChannelTitle, 1)

        self.lblStimChanTitle = QtWidgets.QLabel(self.panel)
        self.lblStimChanTitle.setText("Stim Channel")
        self.lblStimChanTitle.setProperty("variant", "subtitle")  
        self.channelHeaderRow.addWidget(self.lblStimChanTitle, 1)

        self.vbox.addLayout(self.channelHeaderRow)

        self.sep1 = QtWidgets.QFrame(self.panel)
        self.sep1.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep1.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep1.setProperty("role", "divider")                 
        self.vbox.addWidget(self.sep1)

        self.channelBodyRow = QtWidgets.QHBoxLayout()

        self.channelCol = QtWidgets.QVBoxLayout()
        self.channelLabel = QtWidgets.QLabel(self.panel)
        self.channelLabel.setText("Name")
        self.channelLabel.setProperty("variant", "input")        
        self.channelCol.addWidget(self.channelLabel)
        self.channelComboBox = QtWidgets.QComboBox(self.panel)
        self.channelComboBox.setObjectName("channelComboBox")
        self.channelCol.addWidget(self.channelComboBox)
        self.channelBodyRow.addLayout(self.channelCol, 1)

        self.stimChannelCol = QtWidgets.QVBoxLayout()
        self.stimChannelLabel = QtWidgets.QLabel(self.panel)
        self.stimChannelLabel.setText("Name")
        self.stimChannelLabel.setProperty("variant", "input")     
        self.stimChannelCol.addWidget(self.stimChannelLabel)
        self.stimChannelComboBox = QtWidgets.QComboBox(self.panel)
        self.stimChannelComboBox.setObjectName("stimChannelComboBox")
        self.stimChannelComboBox.setToolTip("Channel used to detect onsets/stimuli")
        self.stimChannelCol.addWidget(self.stimChannelComboBox)
        self.channelBodyRow.addLayout(self.stimChannelCol, 1)

        self.vbox.addLayout(self.channelBodyRow)

        # ===== Threshold / Stim Number (two columns, one shared header+divider) =====
        self.thresholdHeaderRow = QtWidgets.QHBoxLayout()

        self.lblThTitle = QtWidgets.QLabel(self.panel)
        self.lblThTitle.setText("Treshold")
        self.lblThTitle.setProperty("variant", "subtitle")        
        self.thresholdHeaderRow.addWidget(self.lblThTitle, 1)

        self.lblStimTitle = QtWidgets.QLabel(self.panel)
        self.lblStimTitle.setText("Stim Number")
        self.lblStimTitle.setProperty("variant", "subtitle")       
        self.thresholdHeaderRow.addWidget(self.lblStimTitle, 1)

        self.vbox.addLayout(self.thresholdHeaderRow)

        self.sep2 = QtWidgets.QFrame(self.panel)
        self.sep2.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep2.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep2.setProperty("role", "divider")                  
        self.vbox.addWidget(self.sep2)

        self.thresholdBodyRow = QtWidgets.QHBoxLayout()

        self.thresholdDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.panel)
        self.thresholdDoubleSpinBox.setDecimals(4)
        self.thresholdDoubleSpinBox.setRange(-1e9, 1e9)
        self.thresholdDoubleSpinBox.setSingleStep(0.01)
        self.thresholdDoubleSpinBox.setValue(0.05)
        self.thresholdDoubleSpinBox.setSuffix(" Hz")
        self.thresholdBodyRow.addWidget(self.thresholdDoubleSpinBox, 1)

        self.stimNumberSpinBox = QtWidgets.QSpinBox(self.panel)
        self.stimNumberSpinBox.setRange(0, 1_000_000)
        self.stimNumberSpinBox.setValue(1)
        self.thresholdBodyRow.addWidget(self.stimNumberSpinBox, 1)

        self.vbox.addLayout(self.thresholdBodyRow)

        # ===== Time (one title, 2x2 grid of label-above-field cells) =====
        self.lblTimeTitle = QtWidgets.QLabel(self.panel)
        self.lblTimeTitle.setText("Time")
        self.lblTimeTitle.setProperty("variant", "subtitle")        
        self.vbox.addWidget(self.lblTimeTitle)

        self.sep4 = QtWidgets.QFrame(self.panel)
        self.sep4.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep4.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep4.setProperty("role", "divider")                    
        self.vbox.addWidget(self.sep4)

        def _time_cell(label_text, spinbox):
            col = QtWidgets.QVBoxLayout()
            label = QtWidgets.QLabel(self.panel)
            label.setText(label_text)
            label.setProperty("variant", "input")
            col.addWidget(label)
            col.addWidget(spinbox)
            return col, label

        self.initialTimeDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.panel)
        self.initialTimeDoubleSpinBox.setDecimals(4)
        self.initialTimeDoubleSpinBox.setRange(-1e9, 1e9)
        self.initialTimeDoubleSpinBox.setSingleStep(0.001)
        self.initialTimeDoubleSpinBox.setValue(-0.05)
        self.initialTimeDoubleSpinBox.setSuffix(" s")

        self.finalTimeDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.panel)
        self.finalTimeDoubleSpinBox.setDecimals(4)
        self.finalTimeDoubleSpinBox.setRange(-1e9, 1e9)
        self.finalTimeDoubleSpinBox.setSingleStep(0.001)
        self.finalTimeDoubleSpinBox.setValue(3.0)
        self.finalTimeDoubleSpinBox.setSuffix(" s")

        self.interStimTimeDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.panel)
        self.interStimTimeDoubleSpinBox.setDecimals(4)
        self.interStimTimeDoubleSpinBox.setRange(-1e9, 1e9)
        self.interStimTimeDoubleSpinBox.setSingleStep(0.001)
        self.interStimTimeDoubleSpinBox.setValue(0.0)
        self.interStimTimeDoubleSpinBox.setSuffix(" s")

        self.endModeCombo = QtWidgets.QComboBox(self.panel)
        self.endModeCombo.addItem("Cut to the next stim", userData="until_next_onset")
        self.endModeCombo.addItem("Fixed window", userData="fixed")

        initialCol, self.initialTimeLabel = _time_cell("Initial Time", self.initialTimeDoubleSpinBox)
        finalCol, self.finalTimeLabel = _time_cell("Final Time", self.finalTimeDoubleSpinBox)
        interStimCol, self.interStimTimeLabel = _time_cell("Inter Stim Time", self.interStimTimeDoubleSpinBox)
        endModeCol, self.endModeComboLabel = _time_cell("Trial End mode", self.endModeCombo)

        self.timeRow1 = QtWidgets.QHBoxLayout()
        self.timeRow1.addLayout(initialCol, 1)
        self.timeRow1.addLayout(finalCol, 1)
        self.vbox.addLayout(self.timeRow1)

        self.timeRow2 = QtWidgets.QHBoxLayout()
        self.timeRow2.addLayout(interStimCol, 1)
        self.timeRow2.addLayout(endModeCol, 1)
        self.vbox.addLayout(self.timeRow2)

        # ===== Subtitle: Trials =====
        self.lblTrialsTitle = QtWidgets.QLabel(self.panel)
        self.lblTrialsTitle.setText("Trials")
        self.lblTrialsTitle.setProperty("variant", "subtitle")      
        self.vbox.addWidget(self.lblTrialsTitle)

        self.sep5 = QtWidgets.QFrame(self.panel)
        self.sep5.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep5.setFrameShadow(QtWidgets.QFrame.Plain)
        self.sep5.setProperty("role", "divider")                    
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
        self.currentTrialLabel.setProperty("variant", "subtitle")    
        self.vbox.addWidget(self.currentTrialLabel)

        # ===== Spacer =====
        self.vbox.addStretch(1)

        # Default splitter sizes
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi()

    def retranslateUi(self):
        self.setWindowTitle("Trials")

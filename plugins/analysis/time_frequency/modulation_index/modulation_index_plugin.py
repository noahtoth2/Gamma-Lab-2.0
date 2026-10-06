from PyQt5.QtWidgets import QWidget
from core.plugins.interfaces import IPlugin
from plugins.analysis.time_frequency.modulation_index.modulation_index_plugin_ui import Ui_ModulationIndex


class Modulation_index_plugin(IPlugin):
    DEFAULTS = {
        "fq_p1": 0.1,
        "fq_p2": 10.0,
        "p_step": 0.1,
        "fq_a1": 10.0,
        "fq_a2": 500.0,
        "a_step": 0.5,
    }

    def process(self, data): pass
    def stop(self): pass

    def get_widget(self, parent=None):
        if self.widget is None:
            self.widget = QWidget(parent)
            self.ui = Ui_ModulationIndex()
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget
            self._init_controls()
            self.ui.clearButton.clicked.connect(self._on_clear_clicked)
        else:
            self.widget.setParent(parent)
        return self.widget

    def _init_controls(self):
        for spin in (self.ui.fqP1SpinBox, self.ui.fqP2SpinBox, self.ui.fqA1SpinBox, self.ui.fqA2SpinBox):
            spin.setDecimals(2)
            spin.setRange(0.0, 100000.0)
            spin.setSingleStep(1.0)
        for spin in (self.ui.pStepSpinBox, self.ui.aStepSpinBox):
            spin.setDecimals(2)
            spin.setRange(0.0, 100000.0)
            spin.setSingleStep(0.1)
        self._on_clear_clicked()

    def _on_clear_clicked(self):
        d = self.DEFAULTS
        self.ui.fqP1SpinBox.setValue(d["fq_p1"])
        self.ui.fqP2SpinBox.setValue(d["fq_p2"])
        self.ui.pStepSpinBox.setValue(d["p_step"])
        self.ui.fqA1SpinBox.setValue(d["fq_a1"])
        self.ui.fqA2SpinBox.setValue(d["fq_a2"])
        self.ui.aStepSpinBox.setValue(d["a_step"])

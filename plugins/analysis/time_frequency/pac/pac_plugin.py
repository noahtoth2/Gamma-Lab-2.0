from PyQt5.QtWidgets import QWidget
from core.plugins.interfaces import IPlugin
from plugins.analysis.time_frequency.pac.pac_plugin_ui import Ui_Pac

class Pac_plugin(IPlugin):
    PAC_TYPES = ["PAC", "PAC Average", "PAC Psel"]
    DEFAULTS = {
        "sample_fq": 2000,
        "p1": 3.0,
        "p2": 8.0,
        "a1": 25.0,
        "a2": 500.0,
    }

    def process(self, data): pass
    def stop(self): pass

    def get_widget(self, parent=None):
        if self.widget is None:
            self.widget = QWidget(parent)
            self.ui = Ui_Pac()
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget
            self.ui.pacTypeComboBox.addItems(self.PAC_TYPES)
            self._init_controls()
            self.ui.clearButton.clicked.connect(self._on_clear_clicked)
        else:
            self.widget.setParent(parent)
        return self.widget

    def _init_controls(self):
        self.ui.sampleDensitySpinBox.setRange(0, 1_000_000)
        self.ui.sampleDensitySpinBox.setSingleStep(100)
        for spin in (self.ui.lowFrequencySpinBox, self.ui.highFrequencySpinBox,
                     self.ui.ampLowFrequencySpinBox, self.ui.ampHighFrequencySpinBox):
            spin.setDecimals(2)
            spin.setRange(0.0, 100000.0)
            spin.setSingleStep(1.0)
        self._on_clear_clicked()

    def _on_clear_clicked(self):
        d = self.DEFAULTS
        self.ui.pacTypeComboBox.setCurrentIndex(0)
        self.ui.sampleDensitySpinBox.setValue(d["sample_fq"])
        self.ui.lowFrequencySpinBox.setValue(d["p1"])
        self.ui.highFrequencySpinBox.setValue(d["p2"])
        self.ui.ampLowFrequencySpinBox.setValue(d["a1"])
        self.ui.ampHighFrequencySpinBox.setValue(d["a2"])

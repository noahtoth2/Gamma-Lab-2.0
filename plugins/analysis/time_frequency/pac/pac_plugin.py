from PyQt5.QtWidgets import QWidget
from core.plugins.interfaces import IPlugin
from plugins.analysis.time_frequency.pac.pac_plugin_ui import Ui_Pac

class Pac_plugin(IPlugin):
    def process(self, data): pass
    def stop(self): pass

    def get_widget(self, parent=None):
        if self.widget is None:
            self.widget = QWidget(parent)
            self.ui = Ui_Pac()
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget
            self.ui.trialModeComboBox.addItems(["trials"])
        else:
            self.widget.setParent(parent)
        return self.widget
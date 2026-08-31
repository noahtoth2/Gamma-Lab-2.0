from PyQt5 import QtWidgets
from PyQt5.QtCore import QUrl
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
import os
import webbrowser

from plugins.faq.help.help_ui import Ui_FAQ


class HelpPlugin(IPlugin):
    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.ui = None
        self.widget = None

    def stop(self):
        pass

    def process(self, data: any):
        pass

    def get_widget(self, parent=None):
        if self.widget is None:
            self.widget = QtWidgets.QWidget(parent)
            self.ui = Ui_FAQ()
            self.ui.setupUi(self.widget)
            self.init_buttons()

            # Cargar PDF
            pdf_path = os.path.join(os.path.dirname(__file__), "MU_GAMMA_LAB.pdf")
            self.load_pdf(pdf_path)
        else:
            self.widget.setParent(parent)

        return self.widget

    def load_pdf(self, pdf_path):
        """Carga el PDF en el QWebEngineView."""
        if os.path.exists(pdf_path):
            file_url = QUrl.fromLocalFile(pdf_path)
            self.ui.pdfView.load(file_url)
        else:
            self.ui.pdfView.setHtml("<h2>PDF not found</h2>")

    def init_buttons(self):
        self.ui.repoButton.clicked.connect(
            lambda: webbrowser.open("https://github.com/GAMMA-BOARD-FTD-PACC/gamma-lab-desktop-app")
        )
        self.ui.docsButton.clicked.connect(
            lambda: webbrowser.open("https://github.com/GAMMA-BOARD-FTD-PACC/Documentos")
        )
        self.ui.videosButton.clicked.connect(
            lambda: webbrowser.open("https://youtube.com/playlist?list=PLTiLHF2jqOJZLib1CLtq1JnGZeNTktVmm&si=6JOE_WovbWcczJy2")
        )
        self.ui.downloadButton.clicked.connect(
            lambda: webbrowser.open("https://github.com/GAMMA-BOARD-FTD-PACC/gamma-lab-desktop-app/releases")
        )

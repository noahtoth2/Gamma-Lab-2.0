from PyQt5 import QtCore, QtWidgets, QtWebEngineWidgets

class Ui_FAQ(object):
    def setupUi(self, FAQ):
        FAQ.setObjectName("FAQ")

        # Layout principal horizontal
        self.mainLayout = QtWidgets.QHBoxLayout(FAQ)
        self.mainLayout.setSpacing(0)

        # Splitter horizontal
        self.splitter = QtWidgets.QSplitter(FAQ)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.mainLayout.addWidget(self.splitter)

        # --- Left Area: PDF Workspace ---
        self.pdfArea = QtWidgets.QFrame(self.splitter)
        self.pdfArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.pdfArea.setFrameShadow(QtWidgets.QFrame.Raised)

        self.pdfLayout = QtWidgets.QVBoxLayout(self.pdfArea)
        self.pdfLayout.setContentsMargins(0, 0, 0, 0)
        self.pdfLayout.setSpacing(0)

        self.pdfView = QtWebEngineWidgets.QWebEngineView(self.pdfArea)
        # Activar visor de PDF
        self.pdfView.settings().setAttribute(QtWebEngineWidgets.QWebEngineSettings.PluginsEnabled, True)
        self.pdfView.settings().setAttribute(QtWebEngineWidgets.QWebEngineSettings.PdfViewerEnabled, True)
        self.pdfLayout.addWidget(self.pdfView)

        # --- Right Area: Button Panel ---
        self.scrollArea = QtWidgets.QScrollArea(self.splitter)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        self.layoutWidget = QtWidgets.QWidget()
        self.paramsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.paramsLayout.setContentsMargins(8, 0, 8, 0)
        self.paramsLayout.setSpacing(12)

        self.scrollArea.setWidget(self.layoutWidget)
        self.splitter.addWidget(self.scrollArea)

        # ==== Title ====
        self.titleLabel = QtWidgets.QLabel(self.layoutWidget)
        self.titleLabel.setAlignment(QtCore.Qt.AlignLeft)
        self.titleLabel.setProperty("variant", "title")  # mantiene el estilo QSS
        self.paramsLayout.addWidget(self.titleLabel)

        self.line = QtWidgets.QFrame(self.layoutWidget)
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setProperty("role", "section-divider")
        self.paramsLayout.addWidget(self.line)

        # ==== Buttons ====
        self.repoButton = QtWidgets.QPushButton(self.layoutWidget)
        self.docsButton = QtWidgets.QPushButton(self.layoutWidget)
        self.videosButton = QtWidgets.QPushButton(self.layoutWidget)
        self.downloadButton = QtWidgets.QPushButton(self.layoutWidget)

        # Asignar objectName igual que antes para que la QSS los aplique
        for btn in [self.repoButton, self.docsButton, self.videosButton, self.downloadButton]:
            btn.setObjectName("mainActionButton")
            btn.setProperty("role", "action-button")  # opcional si tu QSS lo necesita
            self.paramsLayout.addWidget(btn)

        self.paramsLayout.addStretch(1)

        # Ajustar tamaños del splitter
        self.splitter.setSizes([700, 300])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        self.retranslateUi(FAQ)
        QtCore.QMetaObject.connectSlotsByName(FAQ)

    def retranslateUi(self, FAQ):
        _translate = QtCore.QCoreApplication.translate
        FAQ.setWindowTitle(_translate("FAQ", "Documentation"))
        self.titleLabel.setText(_translate("FAQ", "Resources and Documentation"))
        self.repoButton.setText(_translate("FAQ", "Official project repository"))
        self.docsButton.setText(_translate("FAQ", "Project documentation"))
        self.videosButton.setText(_translate("FAQ", "Tutorial videos and guides"))
        self.downloadButton.setText(_translate("FAQ", "Download Gamma Lab"))

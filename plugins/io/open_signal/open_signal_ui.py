from PyQt5 import QtCore, QtWidgets

class Ui_OpenSignal(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        self.setObjectName("OpenAbfSignalForm")
        self.resize(1200, 720)

        # ===== Root =====
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ===== Splitter (izq: VTK, der: panel) =====
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.splitter.setObjectName("openSignalSplitter")
        root.addWidget(self.splitter, 1)

        # ---------- IZQUIERDA: contenedor VTK ----------
        self.frameVtk = QtWidgets.QFrame(self.splitter)
        self.frameVtk.setObjectName("VtkViewer")
        self.frameVtk.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frameVtk.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frameVtk.setMinimumWidth(600)
        self.frameVtk.setMinimumHeight(400)

        leftLayout = QtWidgets.QVBoxLayout(self.frameVtk)
        leftLayout.setContentsMargins(8, 8, 8, 8)
        leftLayout.setSpacing(6)

        self.vtkContainer = QtWidgets.QFrame(self.frameVtk)
        self.vtkContainer.setObjectName("vtkContainer")
        self.vtkContainer.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.vtkContainer.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        leftLayout.addWidget(self.vtkContainer, 1)

        # ---------- DERECHA: barra lateral ----------
        self.sidebar = QtWidgets.QWidget(self.splitter)
        self.sidebar.setObjectName("sidebarPanel")
        sideLayout = QtWidgets.QVBoxLayout(self.sidebar)
        sideLayout.setContentsMargins(8, 8, 8, 8)
        sideLayout.setSpacing(10)
        self.splitter.widget(1).setMaximumWidth(300)

        # ====== Panel title ======
        self.lblParams = QtWidgets.QLabel("Parameters", self.sidebar)
        self.lblParams.setProperty("variant", "title")          # 👈 usa tu QSS
        sideLayout.addWidget(self.lblParams)

        self.divParams = QtWidgets.QFrame(self.sidebar)
        self.divParams.setFrameShape(QtWidgets.QFrame.HLine)
        self.divParams.setProperty("role", "section-divider")   # 👈 usa tu QSS
        sideLayout.addWidget(self.divParams)

        # ====== Subtitle: Shown Channels ======
        self.lblShowed = QtWidgets.QLabel("Showed Channels", self.sidebar)
        self.lblShowed.setProperty("variant", "subtitle")       # 👈
        sideLayout.addWidget(self.lblShowed)

        self.divShowed = QtWidgets.QFrame(self.sidebar)
        self.divShowed.setFrameShape(QtWidgets.QFrame.HLine)
        self.divShowed.setProperty("role", "divider")           # 👈
        sideLayout.addWidget(self.divShowed)

        # ====== Channel list (without QGroupBox) ======
        self.listChannels = QtWidgets.QListWidget(self.sidebar)
        self.listChannels.setObjectName("listChannels")
        self.listChannels.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.listChannels.setAlternatingRowColors(True)
        sideLayout.addWidget(self.listChannels, 1)

        # ====== Action button ======
        self.Btn_abrir_senal = QtWidgets.QPushButton("Open Signal", self.sidebar)
        self.Btn_abrir_senal.setObjectName("mainActionButton")
        self.Btn_abrir_senal.setMinimumHeight(34)
        sideLayout.addWidget(self.Btn_abrir_senal)

        sideLayout.addStretch(0)

        # ---------- Splitter sizes / stretch ----------
        self.sidebar.setMinimumWidth(240)
        self.sidebar.setMaximumWidth(480)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([900, 300])

    def retranslateUi(self):
        self.setWindowTitle("Open Signal")

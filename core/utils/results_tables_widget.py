from PyQt5 import QtCore, QtWidgets


class ResultsTablesWidget(QtWidgets.QWidget):
    """Reusable 'RESULTS' panel: header (title + '...' + 'x') over a slope/amplitude table.

    Used under the Measurements plot in Home and under plotArea in Preprocessing > Trials.
    """

    closeRequested = QtCore.pyqtSignal()
    menuRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        self.setObjectName("ResultsTablesWidget")

        self._root = QtWidgets.QVBoxLayout(self)
        self._root.setContentsMargins(0, 6, 0, 0)
        self._root.setSpacing(4)

        # === Header bar ===
        self.headerLayout = QtWidgets.QHBoxLayout()
        self.headerLayout.setObjectName("resultsHeaderLayout")

        self.titleLabel = QtWidgets.QLabel(self)
        self.titleLabel.setObjectName("resultsTitleLabel")
        self.titleLabel.setProperty("variant", "title")
        self.titleLabel.setText("RESULTS")
        self.headerLayout.addWidget(self.titleLabel)

        self.headerLayout.addStretch(1)

        self.menuButton = QtWidgets.QToolButton(self)
        self.menuButton.setObjectName("resultsMenuButton")
        self.menuButton.setText("...")
        self.menuButton.setAutoRaise(True)
        self.menuButton.clicked.connect(self.menuRequested.emit)
        self.headerLayout.addWidget(self.menuButton)

        self.closeButton = QtWidgets.QToolButton(self)
        self.closeButton.setObjectName("resultsCloseButton")
        self.closeButton.setText("x")
        self.closeButton.setAutoRaise(True)
        self.closeButton.clicked.connect(self.closeRequested.emit)
        self.headerLayout.addWidget(self.closeButton)

        self._root.addLayout(self.headerLayout)

        self.sep = QtWidgets.QFrame(self)
        self.sep.setFrameShape(QtWidgets.QFrame.HLine)
        self.sep.setProperty("role", "section-divider")
        self._root.addWidget(self.sep)

        # === Table: fixed rows Slope / Amplitude ===
        self.table = QtWidgets.QTableWidget(self)
        self.table.setObjectName("resultsTable")
        self.table.setRowCount(2)
        self.table.setColumnCount(1)
        self.table.setVerticalHeaderLabels(["Slope", "Amplitude"])
        self.table.setHorizontalHeaderLabels(["Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.setMaximumHeight(110)
        self._root.addWidget(self.table)

        # By default the "x" button just hides the panel; whoever integrates it
        # can override/disconnect this if they need different behavior.
        self.closeRequested.connect(self.hide)

    def set_values(self, slope=None, amplitude=None):
        """Fill the table's single value column. Pass None to leave a cell blank."""
        self.table.setItem(0, 0, QtWidgets.QTableWidgetItem("" if slope is None else str(slope)))
        self.table.setItem(1, 0, QtWidgets.QTableWidgetItem("" if amplitude is None else str(amplitude)))

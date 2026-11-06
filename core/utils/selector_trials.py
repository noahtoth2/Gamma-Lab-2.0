"""Selector de los trials que participan en un análisis (R27).

Una lista con casilla por trial válido (los descartados ya no aparecen) y botones para marcar
todos o ninguno. `posiciones()` devuelve las posiciones base 1 marcadas, la numeración que usa
toda la aplicación (`core.utils.trial_labels`).
"""
import numpy as np
from PyQt5 import QtCore, QtWidgets


class SelectorDeTrials(QtWidgets.QWidget):

    def __init__(self, parent=None, unico=False):
        super().__init__(parent)
        self.unico = bool(unico)
        capa = QtWidgets.QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        titulo = QtWidgets.QLabel("Trial to use" if self.unico else "Trials to use", self)
        titulo.setProperty("variant", "subtitle")
        capa.addWidget(titulo)
        self.lista = QtWidgets.QListWidget(self)
        self.lista.setMaximumHeight(130)
        self.lista.setToolTip("Marca los trials que participan en este análisis. Los trials descartados no aparecen.")
        capa.addWidget(self.lista)
        fila = QtWidgets.QHBoxLayout()
        self.btn_todos = QtWidgets.QPushButton("All", self)
        self.btn_todos.setToolTip("Marca todos los trials")
        self.btn_ninguno = QtWidgets.QPushButton("None", self)
        self.btn_ninguno.setToolTip("Desmarca todos los trials")
        fila.addWidget(self.btn_todos)
        fila.addWidget(self.btn_ninguno)
        capa.addLayout(fila)
        self.btn_todos.clicked.connect(lambda: self._marcar(True))
        self.btn_ninguno.clicked.connect(lambda: self._marcar(False))
        if self.unico:      # un solo trial a la vez: marcar uno desmarca los demás
            self.btn_todos.setVisible(False)
            self.btn_ninguno.setVisible(False)
            self.lista.itemChanged.connect(self._dejar_uno)

    def _dejar_uno(self, item):
        if item.checkState() != QtCore.Qt.Checked:
            return
        self.lista.blockSignals(True)
        for i in range(self.lista.count()):
            otro = self.lista.item(i)
            if otro is not item:
                otro.setCheckState(QtCore.Qt.Unchecked)
        self.lista.blockSignals(False)

    def _marcar(self, marcado):
        for i in range(self.lista.count()):
            self.lista.item(i).setCheckState(QtCore.Qt.Checked if marcado else QtCore.Qt.Unchecked)

    def establecer_total(self, n):
        """Reconstruye la lista (todos marcados) si cambió el número de trials válidos."""
        n = int(n)
        if self.lista.count() == n:
            return
        self.lista.clear()
        for i in range(1, n + 1):
            item = QtWidgets.QListWidgetItem(f"Trial-{i}")
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if (i == 1 or not self.unico) else QtCore.Qt.Unchecked)
            self.lista.addItem(item)

    def posiciones(self):
        """Posiciones base 1 de los trials marcados."""
        return [i + 1 for i in range(self.lista.count())
                if self.lista.item(i).checkState() == QtCore.Qt.Checked]


def columnas_elegidas(X, posiciones):
    """Las columnas (trials) de `X` en las posiciones base 1 dadas; `X` si son todas."""
    X = np.asarray(X)
    if posiciones is None or len(posiciones) == X.shape[1]:
        return X
    return X[:, [p - 1 for p in posiciones]]

"""Barra de progreso de las tareas del orquestador: no modal, con porcentaje y Cancelar.

Reemplaza al spinner de PluginAlerts, que era modal —bloqueaba toda la
aplicación aunque el cálculo corriera en otro hilo— e indeterminado, sin
porcentaje ni forma de cancelar (problema nº 9).

Va una sola en la barra de estado de la ventana principal y se engancha a
`TaskService.task_started`, así que sirve para cualquier plugin que use el
orquestador sin que el plugin tenga que hacer nada. Es la misma decisión de la
Fase 3.3: resolverlo en un sitio en vez de que cada plugin se acuerde.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy, QWidget)


class TaskProgressBar(QWidget):
    """Muestra el avance de la tarea en curso y permite cancelarla."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handle = None

        self._etiqueta = QLabel("", self)
        self._etiqueta.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self._barra = QProgressBar(self)
        self._barra.setRange(0, 100)
        self._barra.setValue(0)
        self._barra.setTextVisible(True)
        self._barra.setFixedWidth(160)

        self._cancelar = QPushButton("Cancelar", self)
        self._cancelar.setCursor(Qt.PointingHandCursor)
        self._cancelar.clicked.connect(self._on_cancelar)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._etiqueta)
        layout.addWidget(self._barra)
        layout.addWidget(self._cancelar)

        self.setVisible(False)

    # ---------------------------------------------------------------- publico

    def seguir(self, handle, titulo: str = ""):
        """Engancha un TaskHandle y se muestra mientras la tarea viva.

        Si ya estaba siguiendo otra tarea, la suelta: el orquestador ejecuta una
        sola a la vez y `submit()` descarta las que ese mismo dueño tuviera en
        cola, así que la última es siempre la vigente.
        """
        if handle is None:
            return
        self._soltar()
        self._handle = handle

        handle.progress.connect(self._on_progress)
        handle.finished.connect(self._on_terminada)
        handle.failed.connect(self._on_terminada)
        handle.cancelled.connect(self._on_terminada)

        self._etiqueta.setText(titulo or self._titulo_de(handle))
        self._barra.setValue(0)
        self._cancelar.setEnabled(True)
        self.setVisible(True)

    def ocultar(self):
        self._soltar()
        self.setVisible(False)

    # ---------------------------------------------------------------- interno

    @staticmethod
    def _titulo_de(handle) -> str:
        dueno = getattr(handle, "owner", "") or ""
        return f"{dueno}:" if dueno else "Calculando:"

    def _soltar(self):
        """Desconecta el handle anterior para que sus señales tardías no muevan
        la barra de la tarea nueva."""
        if self._handle is None:
            return
        for senal in (self._handle.progress, self._handle.finished,
                      self._handle.failed, self._handle.cancelled):
            try:
                senal.disconnect(self._on_progress)
            except (TypeError, RuntimeError):
                pass
            try:
                senal.disconnect(self._on_terminada)
            except (TypeError, RuntimeError):
                pass
        self._handle = None

    def _on_cancelar(self):
        if self._handle is None:
            return
        self._cancelar.setEnabled(False)
        self._etiqueta.setText("Cancelando…")
        try:
            self._handle.cancel()
        except Exception:
            self.ocultar()

    def _on_progress(self, percent, message=""):
        if not self.isVisible():
            return
        self._barra.setValue(max(0, min(100, int(percent))))
        if message:
            self._etiqueta.setText(str(message))

    def _on_terminada(self, *_):
        self.ocultar()

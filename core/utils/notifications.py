from PyQt5.QtCore import Qt, QTimer, QEvent, QObject
from PyQt5.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton


class NotificationCard(QFrame):
    """Una tarjeta de aviso no modal. El color sale del QSS por `severity`."""

    _ICONS = {"info": "ℹ", "warning": "⚠", "error": "✖"}

    def __init__(self, level: str, title: str, message: str, on_close, parent=None):
        super().__init__(parent)
        self.level = level
        self.key = None
        self._on_close = on_close
        self.setObjectName("notificationCard")
        self.setProperty("severity", level)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 6, 8)
        row.setSpacing(8)

        icon = QLabel(self._ICONS.get(level, ""), self)
        icon.setObjectName("notificationIcon")
        icon.setProperty("severity", level)
        icon.setAlignment(Qt.AlignTop)
        row.addWidget(icon)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        if title:
            lbl_title = QLabel(title, self)
            lbl_title.setObjectName("notificationTitle")
            lbl_title.setProperty("severity", level)
            textos.addWidget(lbl_title)
        lbl_msg = QLabel(message, self)
        lbl_msg.setObjectName("notificationMessage")
        lbl_msg.setWordWrap(True)
        lbl_msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        textos.addWidget(lbl_msg)
        row.addLayout(textos, 1)

        close_btn = QToolButton(self)
        close_btn.setObjectName("notificationClose")
        close_btn.setText("✕")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Cerrar")
        close_btn.clicked.connect(self.close_card)
        row.addWidget(close_btn, 0, Qt.AlignTop)

    def close_card(self):
        if self._on_close is not None:
            cb, self._on_close = self._on_close, None
            cb(self)


class NotificationCenter(QObject):
    """Pila de avisos no modales en la esquina inferior izquierda del workspace.

    Abajo a la izquierda caen sobre la grafica y no sobre los paneles de
    parametros, que en todos los plugins estan a la derecha.

    - `info`: se cierra sola a los `INFO_TIMEOUT_MS`.
    - `warning`: se queda hasta que el usuario la cierra.
    Los errores no pasan por aqui: siguen siendo un dialogo modal
    (`PluginAlerts.error`), porque detienen lo que el usuario estaba haciendo.

    Cada tarjeta es una ventana nativa hija del workspace. Las graficas de VTK
    son ventanas nativas y taparian a un widget normal superpuesto; una
    nativa con `raise_()` si queda por encima.
    """

    INFO_TIMEOUT_MS = 4500
    MAX_CARDS = 4
    WIDTH = 380
    MARGIN = 12
    SPACING = 6

    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        self._cards = []
        host.installEventFilter(self)

    def window(self):
        return self._host.window()

    # ---------- API ----------
    def show_message(self, level: str, title: str, message: str):
        # Un mismo aviso repetido (p. ej. al pulsar varias veces) no se apila.
        for card in self._cards:
            if card.level == level and card.key == (title, message):
                self._cards.remove(card)
                self._cards.append(card)
                self._arm_timer(card)
                self._reposition()
                return

        card = NotificationCard(level, title, message, self._remove_card, self._host)
        card.key = (title, message)
        card.setAttribute(Qt.WA_NativeWindow, True)
        self._cards.append(card)
        self._arm_timer(card)
        self._trim()
        card.show()
        self._reposition()

    def clear(self):
        for card in list(self._cards):
            self._remove_card(card)

    def restack(self):
        """Vuelve a subir las tarjetas; se llama al mostrar otro plugin, cuyas
        ventanas nativas de VTK se crean despues y quedarian encima."""
        if self._cards:
            self._reposition()

    # ---------- internos ----------
    def _arm_timer(self, card):
        if card.level != "info":
            return
        old = getattr(card, "_timer", None)
        if old is not None:
            old.stop()
        timer = QTimer(card)
        timer.setSingleShot(True)
        timer.timeout.connect(card.close_card)
        timer.start(self.INFO_TIMEOUT_MS)
        card._timer = timer

    def _trim(self):
        # Se descartan primero los info mas antiguos; los warning solo si no queda otra.
        while len(self._cards) > self.MAX_CARDS:
            victim = next((c for c in self._cards if c.level == "info"), self._cards[0])
            self._remove_card(victim)

    def _remove_card(self, card):
        if card in self._cards:
            self._cards.remove(card)
        card.hide()
        card.deleteLater()
        self._reposition()

    def _reposition(self):
        host = self._host
        width = min(self.WIDTH, max(200, host.width() - 2 * self.MARGIN))
        x = self.MARGIN
        y = host.height() - self.MARGIN
        # El mas reciente abajo; los anteriores se apilan hacia arriba
        for card in reversed(self._cards):
            card.setFixedWidth(width)
            h = card.heightForWidth(width) if card.hasHeightForWidth() else card.sizeHint().height()
            card.setFixedHeight(max(h, card.minimumSizeHint().height()))
            y -= card.height()
            card.move(x, y)
            card.raise_()
            y -= self.SPACING

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() == QEvent.Resize and self._cards:
            self._reposition()
        return False

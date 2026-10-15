# app/view/splash_screen.py
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtGui import QPixmap, QColor, QFont
from PyQt5.QtCore import Qt, QRectF

SPLASH_IMAGE = Path(__file__).resolve().parents[2] / "assets" / "images" / "splash.png"

# Geometry relative to the 735x413 splash image
BAR_WIDTH = 240
BAR_HEIGHT = 4
BAR_TOP = 352
MESSAGE_TOP = 360


class SplashScreen(QSplashScreen):
    """Startup splash: background image plus a progress bar and status line."""

    def __init__(self):
        pixmap = QPixmap(str(SPLASH_IMAGE))
        super().__init__(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self._progress = 0
        self._message = ""

    def set_progress(self, value: int, message: str = ""):
        self._progress = max(0, min(100, value))
        self._message = message
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter):
        painter.setRenderHint(painter.Antialiasing)
        width = self.pixmap().width()

        # Progress bar (track + fill)
        bar = QRectF((width - BAR_WIDTH) / 2, BAR_TOP, BAR_WIDTH, BAR_HEIGHT)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#D5DBE3"))
        painter.drawRoundedRect(bar, 2, 2)
        if self._progress > 0:
            fill = QRectF(bar.x(), bar.y(), BAR_WIDTH * self._progress / 100, BAR_HEIGHT)
            painter.setBrush(QColor("#2E60A9"))
            painter.drawRoundedRect(fill, 2, 2)

        # Current step
        if self._message:
            font = QFont(QApplication.font())
            font.setPointSize(7)
            painter.setFont(font)
            painter.setPen(QColor("#6f7a86"))
            painter.drawText(QRectF(0, MESSAGE_TOP, width, 16), Qt.AlignHCenter | Qt.AlignTop, self._message)

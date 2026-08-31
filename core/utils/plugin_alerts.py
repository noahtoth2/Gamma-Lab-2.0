from PyQt5.QtWidgets import QMessageBox, QWidget, QDialog, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt, QTimer, QEventLoop
from PyQt5.QtGui import QMovie


class PluginAlerts:

    def __init__(self, parent: QWidget = None):
        self.parent = parent
        self._spinner_dialog = None


    def __show_message(self, title: str, message: str, level: str):
        """Internal helper to show alerts with different levels."""
        print(f"[PluginAlerts] {level.upper()}: {message}")

        if not self.parent:
            # No UI context (console or test mode)
            return

        if level == "error":
            QMessageBox.critical(self.parent, title, message)
        elif level == "warning":
            QMessageBox.warning(self.parent, title, message)
        elif level == "info":
            QMessageBox.information(self.parent, title, message)
        else:
            raise ValueError(f"Unknown alert level: {level}")

    def error(self, message: str, title: str = "Error"):
        self.__show_message(title, message, "error")

    def warning(self, message: str, title: str = "Warning"):
        self.__show_message(title, message, "warning")

    def info(self, message: str, title: str = "Information"):
        self.__show_message(title, message, "info")

    #  LOADING SPINNER
    def show_spinner(self, text: str = "Processing...", gif_path: str = None):
        if self._spinner_dialog and self._spinner_dialog.isVisible():
            return

        self._spinner_dialog = QDialog(self.parent)
        self._spinner_dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self._spinner_dialog.setModal(True)
        self._spinner_dialog.setAttribute(Qt.WA_TranslucentBackground)
        self._spinner_dialog.setObjectName("spinnerDialog")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(20, 20, 20, 20)

        # -------- Spinner GIF or ProgressBar --------
        if gif_path:
            spinner_label = QLabel()
            movie = QMovie(gif_path)
            spinner_label.setMovie(movie)
            movie.start()
            layout.addWidget(spinner_label, alignment=Qt.AlignCenter)
        else:
            bar = QProgressBar()
            bar.setRange(0, 0)
            bar.setFixedWidth(160)
            bar.setObjectName("spinnerProgressBar")
            layout.addWidget(bar, alignment=Qt.AlignCenter)

        # -------- Text --------
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setObjectName("spinnerText")
        layout.addWidget(label)

        self._spinner_dialog.setLayout(layout)
        self._spinner_dialog.resize(240, 140)

        # -------- INLINE CSS STYLES --------
        self._spinner_dialog.setStyleSheet("""
            #spinnerDialog {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }

            QLabel#spinnerText {
                color: #555555;
                font-size: 14px;
                font-weight: 500;
            }

            QProgressBar#spinnerProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                height: 10px;
            }

            QProgressBar#spinnerProgressBar::chunk {
                background-color: #3a7bd5;
                border-radius: 6px;
            }
        """)

        # -------- Optional Shadow (looks premium) --------
        try:
            from PyQt5.QtWidgets import QGraphicsDropShadowEffect
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(20)
            shadow.setOffset(0, 0)
            shadow.setColor(Qt.gray)
            self._spinner_dialog.setGraphicsEffect(shadow)
        except Exception:
            pass

        self._spinner_dialog.show()
        QEventLoop().processEvents()



    def hide_spinner(self):
        """Close the loading spinner if active."""
        if self._spinner_dialog:
            self._spinner_dialog.accept()
            self._spinner_dialog = None

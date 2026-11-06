"""Diálogo de bienvenida de la primera ejecución (R10), con la paleta y la tipografía de GammaLab."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

ESTILO = """
#dialogoBienvenida { background-color: #FFFFFF; }
#bienvenidaTitulo { color: #2E60A9; font-size: 17pt; font-weight: 700; }
#bienvenidaSubtitulo { color: #6f7a86; font-size: 10pt; }
#bienvenidaLinea { background-color: #E3E7EC; max-height: 1px; border: none; }
#pasoTarjeta { background-color: #F0F2F5; border: 1px solid #E3E7EC; border-radius: 8px; }
#pasoNumero { background-color: #2E60A9; color: #FFFFFF; border-radius: 13px; font-weight: 700; font-size: 10pt; }
#pasoTitulo { color: #2E60A9; font-size: 10.5pt; font-weight: 600; background: transparent; }
#pasoDescripcion { color: #33475b; font-size: 10pt; background: transparent; }
#bienvenidaPie { color: #6f7a86; font-size: 9pt; }
"""


class DialogoBienvenida(QDialog):
    """Presenta `pasos`, una secuencia de (título, descripción), con el botón «Comenzar»."""

    def __init__(self, pasos, parent=None):
        super().__init__(parent)
        self.setObjectName("dialogoBienvenida")
        self.setWindowTitle("Bienvenido a Gamma Lab 2.0")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(ESTILO)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(32, 28, 32, 24)
        raiz.setSpacing(14)

        raiz.addLayout(self._cabecera())
        linea = QFrame(self)
        linea.setObjectName("bienvenidaLinea")
        linea.setFrameShape(QFrame.HLine)
        raiz.addWidget(linea)

        for i, (titulo, descripcion) in enumerate(pasos, start=1):
            raiz.addWidget(self._tarjeta(i, titulo, descripcion))

        pie = QHBoxLayout()
        nota = QLabel("Puedes volver a consultar esta ayuda en la sección FAQ.", self)
        nota.setObjectName("bienvenidaPie")
        pie.addWidget(nota)
        pie.addStretch(1)
        boton = QPushButton("Comenzar", self)
        boton.setObjectName("headerGenerateButton")      # mismo estilo que el botón principal de los paneles
        boton.setCursor(Qt.PointingHandCursor)
        boton.setDefault(True)
        boton.clicked.connect(self.accept)
        pie.addWidget(boton)
        raiz.addSpacing(4)
        raiz.addLayout(pie)

    def _cabecera(self):
        fila = QHBoxLayout()
        fila.setSpacing(16)
        logo = QLabel(self)
        pix = QPixmap("assets/logos/app-logo.png")
        if not pix.isNull():
            logo.setPixmap(pix.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            fila.addWidget(logo, 0, Qt.AlignVCenter)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = QLabel("Bienvenido a Gamma Lab 2.0", self)
        titulo.setObjectName("bienvenidaTitulo")
        subtitulo = QLabel("Para empezar, este es el recorrido básico de la aplicación:", self)
        subtitulo.setObjectName("bienvenidaSubtitulo")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        fila.addLayout(textos, 1)
        return fila

    def _tarjeta(self, numero, titulo, descripcion) -> QWidget:
        tarjeta = QFrame(self)
        tarjeta.setObjectName("pasoTarjeta")
        fila = QHBoxLayout(tarjeta)
        fila.setContentsMargins(14, 10, 14, 10)
        fila.setSpacing(14)

        num = QLabel(str(numero), tarjeta)
        num.setObjectName("pasoNumero")
        num.setFixedSize(26, 26)
        num.setAlignment(Qt.AlignCenter)
        fila.addWidget(num, 0, Qt.AlignTop)

        textos = QVBoxLayout()
        textos.setSpacing(1)
        t = QLabel(titulo, tarjeta)
        t.setObjectName("pasoTitulo")
        d = QLabel(descripcion[:1].upper() + descripcion[1:], tarjeta)
        d.setObjectName("pasoDescripcion")
        d.setWordWrap(True)
        textos.addWidget(t)
        textos.addWidget(d)
        fila.addLayout(textos, 1)
        return tarjeta

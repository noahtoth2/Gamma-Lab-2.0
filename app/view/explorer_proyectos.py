"""Explorer con varios proyectos abiertos.

Cada carpeta de proyecto se muestra en su propio árbol (`ArbolProyecto`), apilados en un
`QSplitter` vertical. Solo un proyecto está activo (el que tiene cargado el `ProjectService`);
su carpeta y su `.glab` se dibujan en negrita. Para cambiar de proyecto se hace doble clic
en el `.glab` de otro.

También están aquí los diálogos de File > Close project (`DialogoCerrarProyecto`) y de
File > New project / Duplicate project (`DialogoProyectoNuevo`).
"""
import html
import os
from pathlib import Path

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileSystemModel,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStyledItemDelegate,
    QTreeView,
    QVBoxLayout,
)


def clave_ruta(ruta) -> str:
    """Forma comparable de una ruta (absoluta y sin distinguir mayúsculas en Windows)."""
    return os.path.normcase(os.path.abspath(str(ruta)))


class _DelegadoActivo(QStyledItemDelegate):
    """Pone en negrita la carpeta y el `.glab` del proyecto activo."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        arbol = self.parent()
        if arbol.es_ruta_activa(arbol.model().filePath(index)):
            option.font.setBold(True)


class ArbolProyecto(QTreeView):
    """Árbol de archivos de una carpeta de proyecto: se ve la carpeta y nada de lo que la rodea."""

    def __init__(self, carpeta: Path, parent=None):
        super().__init__(parent)
        self.carpeta = Path(carpeta)
        self._glab_activo = None  # clave del .glab activo si está en esta carpeta

        self.modelo = QFileSystemModel(self)
        # Permite renombrar, mover y borrar desde el árbol (por defecto es de solo lectura).
        self.modelo.setReadOnly(False)
        self.modelo.directoryLoaded.connect(self._al_cargar_directorio)
        self.modelo.rowsInserted.connect(self._al_insertar_filas)

        self.setObjectName("explorerTreeWidget")
        self.setModel(self.modelo)
        self.setItemDelegate(_DelegadoActivo(self))
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.setIconSize(QSize(16, 16))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # En la barra lateral solo sirve la columna del nombre.
        for col in range(1, 4):
            self.setColumnHidden(col, True)
        self.setEditTriggers(QAbstractItemView.EditKeyPressed)

        # Arrastrar archivos entre carpetas para moverlos.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self._mostrar_carpeta()

    # ---------- raíz: la carpeta del proyecto, sin sus hermanas ----------
    def _mostrar_carpeta(self):
        self.modelo.setRootPath(str(self.carpeta.parent))
        indice = self.modelo.index(str(self.carpeta))
        padre = self.modelo.parent(indice)
        self.setRootIndex(padre)
        self._ocultar_hermanas(padre)
        self.expand(indice)

    def _ocultar_hermanas(self, padre):
        for fila in range(self.modelo.rowCount(padre)):
            hermana = self.modelo.index(fila, 0, padre)
            es_proyecto = clave_ruta(self.modelo.filePath(hermana)) == clave_ruta(self.carpeta)
            self.setRowHidden(fila, padre, not es_proyecto)

    def _al_cargar_directorio(self, ruta):
        if clave_ruta(ruta) == clave_ruta(self.carpeta.parent):
            self._ocultar_hermanas(self.modelo.index(ruta))
            self.expand(self.modelo.index(str(self.carpeta)))

    def _al_insertar_filas(self, padre, primera, ultima):
        if clave_ruta(self.modelo.filePath(padre)) == clave_ruta(self.carpeta.parent):
            self._ocultar_hermanas(padre)

    # ---------- proyecto activo ----------
    def marcar_activo(self, glab_activo):
        """`glab_activo`: ruta del .glab activo, o None. Solo cuenta si está en esta carpeta."""
        clave = None
        if glab_activo is not None and clave_ruta(Path(glab_activo).parent) == clave_ruta(self.carpeta):
            clave = clave_ruta(glab_activo)
        if clave != self._glab_activo:
            self._glab_activo = clave
            self.viewport().update()

    def es_ruta_activa(self, ruta) -> bool:
        if not self._glab_activo or not ruta:
            return False
        clave = clave_ruta(ruta)
        return clave == self._glab_activo or clave == clave_ruta(self.carpeta)


class DialogoCerrarProyecto(QDialog):
    """File > Close project con varios proyectos abiertos: elegir cuál se cierra.

    `opciones` es una lista de `(titulo, detalle, activo)`; se muestra el nombre del `.glab`
    y debajo, en gris, la carpeta (dos proyectos pueden llamarse igual).
    """

    def __init__(self, opciones, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Close Project")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("¿Qué proyecto quieres cerrar?", self))

        self.lista = QListWidget(self)
        self.lista.setSelectionMode(QAbstractItemView.SingleSelection)
        fila_activa = 0
        for fila, (titulo, detalle, activo) in enumerate(opciones):
            marca = " <i>(activo)</i>" if activo else ""
            etiqueta = QLabel(
                f"<b>{_escapar(titulo)}</b>{marca}<br>"
                f"<span style='color:gray'>{_escapar(detalle)}</span>"
            )
            etiqueta.setContentsMargins(6, 4, 6, 4)
            item = QListWidgetItem(self.lista)
            item.setSizeHint(etiqueta.sizeHint())
            item.setToolTip(detalle)
            self.lista.setItemWidget(item, etiqueta)
            if activo:
                fila_activa = fila
        self.lista.setCurrentRow(fila_activa)
        self.lista.itemDoubleClicked.connect(lambda _item: self.accept())
        layout.addWidget(self.lista)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        botones.button(QDialogButtonBox.Ok).setText("Close project")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def fila_elegida(self):
        return self.lista.currentRow()

    @classmethod
    def elegir(cls, opciones, parent=None):
        """Devuelve el índice de la opción elegida, o None si se canceló."""
        dialogo = cls(opciones, parent)
        if dialogo.exec_() != QDialog.Accepted:
            return None
        fila = dialogo.fila_elegida()
        return fila if 0 <= fila < len(opciones) else None


_CARACTERES_PROHIBIDOS = set('<>:"/\\|?*')


class DialogoProyectoNuevo(QDialog):
    """File > New project y Duplicate project: nombre, ubicación y en qué ventana se abre.

    El proyecto queda en `ubicación/nombre/nombre.glab`. `validar_extra(carpeta)` puede
    devolver un mensaje de error (por ejemplo, para que una copia no caiga dentro del original).
    """

    def __init__(self, titulo, nombre, ubicacion, texto_boton, validar_extra=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(480)
        self._validar_extra = validar_extra

        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        self.campo_nombre = QLineEdit(nombre, self)
        self.campo_nombre.selectAll()
        formulario.addRow("Nombre:", self.campo_nombre)

        fila_ubicacion = QHBoxLayout()
        self.campo_ubicacion = QLineEdit(str(ubicacion), self)
        boton_buscar = QPushButton("Browse…", self)
        boton_buscar.clicked.connect(self._buscar_ubicacion)
        fila_ubicacion.addWidget(self.campo_ubicacion)
        fila_ubicacion.addWidget(boton_buscar)
        formulario.addRow("Ubicación:", fila_ubicacion)
        layout.addLayout(formulario)

        self.etiqueta_ruta = QLabel(self)
        self.etiqueta_ruta.setWordWrap(True)
        self.etiqueta_ruta.setStyleSheet("color: gray;")
        layout.addWidget(self.etiqueta_ruta)

        grupo = QGroupBox("Abrir en", self)
        caja = QVBoxLayout(grupo)
        self.opcion_misma = QRadioButton("Esta ventana (se añade al Explorer)", grupo)
        self.opcion_nueva = QRadioButton("Una ventana nueva", grupo)
        self.opcion_misma.setChecked(True)
        caja.addWidget(self.opcion_misma)
        caja.addWidget(self.opcion_nueva)
        layout.addWidget(grupo)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        botones.button(QDialogButtonBox.Ok).setText(texto_boton)
        botones.accepted.connect(self._aceptar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        self.campo_nombre.textChanged.connect(self._actualizar_ruta)
        self.campo_ubicacion.textChanged.connect(self._actualizar_ruta)
        self._actualizar_ruta()

    def _buscar_ubicacion(self):
        carpeta = QFileDialog.getExistingDirectory(
            self, "Select Location", self.campo_ubicacion.text(), QFileDialog.ShowDirsOnly)
        if carpeta:
            self.campo_ubicacion.setText(carpeta)

    def nombre(self) -> str:
        return self.campo_nombre.text().strip()

    def carpeta_proyecto(self) -> Path:
        return Path(self.campo_ubicacion.text().strip()) / self.nombre()

    def ventana_nueva(self) -> bool:
        return self.opcion_nueva.isChecked()

    def _actualizar_ruta(self):
        if self.nombre() and self.campo_ubicacion.text().strip():
            glab = self.carpeta_proyecto() / f"{self.nombre()}.glab"
            self.etiqueta_ruta.setText(f"Se creará: {glab}")
        else:
            self.etiqueta_ruta.setText("")

    def error(self):
        """Mensaje de por qué no se puede crear, o None."""
        nombre = self.nombre()
        if not nombre:
            return "Escribe un nombre para el proyecto."
        if any(c in _CARACTERES_PROHIBIDOS for c in nombre) or nombre.endswith((".", " ")):
            return 'El nombre no puede contener  < > : " / \\ | ? *  ni terminar en punto o espacio.'
        ubicacion = Path(self.campo_ubicacion.text().strip())
        if not self.campo_ubicacion.text().strip() or not ubicacion.is_dir():
            return "La ubicación no existe. Elige una carpeta con Browse…"
        carpeta = self.carpeta_proyecto()
        if carpeta.exists() and (not carpeta.is_dir() or any(carpeta.iterdir())):
            return f"Ya existe «{carpeta.name}» en esa ubicación y no está vacía. Elige otro nombre."
        if self._validar_extra is not None:
            return self._validar_extra(carpeta)
        return None

    def _aceptar(self):
        mensaje = self.error()
        if mensaje:
            QMessageBox.warning(self, self.windowTitle(), mensaje)
            return
        self.accept()

    @classmethod
    def pedir(cls, titulo, nombre, ubicacion, texto_boton, validar_extra=None, parent=None):
        """Devuelve `(carpeta_proyecto, nombre, ventana_nueva)`, o None si se canceló."""
        dialogo = cls(titulo, nombre, ubicacion, texto_boton, validar_extra, parent)
        if dialogo.exec_() != QDialog.Accepted:
            return None
        return dialogo.carpeta_proyecto(), dialogo.nombre(), dialogo.ventana_nueva()


def _escapar(texto: str) -> str:
    return html.escape(str(texto))

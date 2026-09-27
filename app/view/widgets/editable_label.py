from PyQt5 import QtCore, QtWidgets


class _RenameLineEdit(QtWidgets.QLineEdit):
    """QLineEdit that reports Escape so the caller can cancel the rename."""

    cancelled = QtCore.pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)


class EditableLabel(QtWidgets.QWidget):
    """QLabel that turns into a QLineEdit on double-click, for inline renaming."""

    renamed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._edit_value = None

        self._stack = QtWidgets.QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self.label = QtWidgets.QLabel(self)
        self.label.setObjectName("editableLabelText")
        self.label.setToolTip("Double-click to rename")
        self.label.mouseDoubleClickEvent = self._start_edit

        self.edit = _RenameLineEdit(self)
        self.edit.setObjectName("editableLabelEdit")
        self.edit.editingFinished.connect(self._commit_edit)
        self.edit.cancelled.connect(self._cancel_edit)

        self._stack.addWidget(self.label)
        self._stack.addWidget(self.edit)
        self._stack.setCurrentWidget(self.label)

    def text(self) -> str:
        return self.label.text()

    def setText(self, text: str):
        self.label.setText(text or "")

    def setEditableValue(self, value: str):
        self._edit_value = value

    def _start_edit(self, event=None):
        if not self.isEnabled():
            return
        current = self._edit_value if self._edit_value is not None else self.label.text()
        self.edit.setText(current)
        self._stack.setCurrentWidget(self.edit)
        self.edit.setFocus()
        self.edit.selectAll()

    def _cancel_edit(self):
        self._stack.setCurrentWidget(self.label)

    def _commit_edit(self):
        if self._stack.currentWidget() is not self.edit:
            return
        new_value = self.edit.text().strip()
        self._stack.setCurrentWidget(self.label)
        if new_value and new_value != self._edit_value:
            self.renamed.emit(new_value)

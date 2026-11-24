"""Left panel: VS Code settings-style property rows for the selected control."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..core.actions import KeysAction, MediaAction, NoneAction, TextAction
from .theme import DIM, FAINT, MONO

TYPE_NAMES = [("keys", "Keys"), ("text", "Text"), ("media", "Media"),
              ("macro", "Macro"), ("none", "None")]

_SPECIAL = {
    Qt.Key_Home: "home", Qt.Key_End: "end", Qt.Key_Delete: "delete",
    Qt.Key_Insert: "insert", Qt.Key_PageUp: "pageup", Qt.Key_PageDown: "pagedown",
    Qt.Key_Left: "left", Qt.Key_Right: "right", Qt.Key_Up: "up",
    Qt.Key_Down: "down", Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
    Qt.Key_Escape: "esc", Qt.Key_Tab: "tab", Qt.Key_Space: "space",
    Qt.Key_Backspace: "backspace", Qt.Key_Plus: "+", Qt.Key_Minus: "-",
    Qt.Key_Equal: "=", Qt.Key_Comma: ",", Qt.Key_Period: ".",
    Qt.Key_Slash: "/", Qt.Key_Semicolon: ";", Qt.Key_Apostrophe: "'",
}
for i in range(1, 13):
    _SPECIAL[getattr(Qt, f"Key_F{i}")] = f"f{i}"

NAME_COL = 96


def _qt_to_name(key: int) -> str | None:
    if key in _SPECIAL:
        return _SPECIAL[key]
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key).lower()
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    return None


class ChordRecorder(QPushButton):
    """Button that arms a one-shot keyboard grab to capture a chord."""
    captured = Signal(list)

    def __init__(self, parent=None):
        super().__init__("● rec", parent)
        self.armed = False

    def mousePressEvent(self, e):
        if not self.armed:
            self.armed = True
            self.setText("● press…")
            self.setFocus(Qt.OtherFocusReason)
        super().mousePressEvent(e)

    def keyPressEvent(self, e):
        if not self.armed:
            super().keyPressEvent(e)
            return
        name = _qt_to_name(e.key())
        if name is None:
            return
        mods = e.modifiers()
        chord = []
        if mods & Qt.ControlModifier:
            chord.append("ctrl")
        if mods & Qt.ShiftModifier:
            chord.append("shift")
        if mods & Qt.AltModifier:
            chord.append("alt")
        if mods & Qt.MetaModifier:
            chord.append("super")
        chord.append(name)
        self.armed = False
        self.setText("● rec")
        self.captured.emit(chord)


class PropRow(QWidget):
    """One settings row: name | type combo | value control."""
    changed = Signal()

    def __init__(self, name: str, accent: str, parent=None):
        super().__init__(parent)
        self.accent = accent
        self.action = NoneAction()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.name_lbl = QLabel(name)
        self.name_lbl.setObjectName("dim")
        self.name_lbl.setFixedWidth(NAME_COL)
        lay.addWidget(self.name_lbl)

        self.type_combo = QComboBox()
        for _, tname in TYPE_NAMES:
            self.type_combo.addItem(tname)
        self.type_combo.setFixedWidth(88)
        lay.addWidget(self.type_combo)

        self.stack = QStackedWidget()
        # 0 keys
        keys_page = QWidget()
        kl = QHBoxLayout(keys_page)
        kl.setContentsMargins(0, 0, 0, 0)
        self.chords = QLabel("")
        self.chords.setObjectName("mono")
        self.chords.setStyleSheet(f"color: {DIM}; font-family: '{MONO}';")
        kl.addWidget(self.chords, 1)
        self.recorder = ChordRecorder()
        self.recorder.setFixedWidth(78)
        kl.addWidget(self.recorder)
        self.stack.addWidget(keys_page)
        # 1 text
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("text to type")
        self.stack.addWidget(self.text_edit)
        # 2 media
        self.media_combo = QComboBox()
        for k in MediaAction.MEDIA_KEYS:
            self.media_combo.addItem(k.replace("_", " "), k)
        self.stack.addWidget(self.media_combo)
        # 3 macro
        self.macro_lbl = QLabel("editor coming soon")
        self.macro_lbl.setStyleSheet(f"color: {FAINT};")
        self.stack.addWidget(self.macro_lbl)
        # 4 none
        none_lbl = QLabel("unbound")
        none_lbl.setStyleSheet(f"color: {FAINT};")
        self.stack.addWidget(none_lbl)
        lay.addWidget(self.stack, 1)

        self.type_combo.currentIndexChanged.connect(self._type_changed)
        self.recorder.captured.connect(self._chord_captured)
        self.text_edit.textEdited.connect(lambda _: self._commit())
        self.media_combo.currentIndexChanged.connect(
            lambda _: self._commit() if self.type_combo.currentIndex() == 2 else None)

    def _type_changed(self, idx):
        self.stack.setCurrentIndex(idx)
        self._commit()

    def _chord_captured(self, chord):
        self.action = KeysAction(keys=chord)
        self.chords.setText(" + ".join(chord))
        self.type_combo.setCurrentIndex(0)
        self.changed.emit()

    def _commit(self):
        t = TYPE_NAMES[self.type_combo.currentIndex()][0]
        if t == "keys" and isinstance(self.action, KeysAction):
            pass
        elif t == "text":
            self.action = TextAction(text=self.text_edit.text())
        elif t == "media":
            self.action = MediaAction(key=self.media_combo.currentData())
        elif t == "none":
            self.action = NoneAction()
        self.changed.emit()

    def set_action(self, action):
        self.action = action if action is not None else NoneAction()
        t = getattr(self.action, "type", "none")
        idx = next((i for i, (n, _) in enumerate(TYPE_NAMES) if n == t), 4)
        self.type_combo.blockSignals(True)
        self.type_combo.setCurrentIndex(idx)
        self.stack.setCurrentIndex(idx)
        self.type_combo.blockSignals(False)
        if t == "keys":
            self.chords.setText(" + ".join(self.action.keys))
        elif t == "text":
            self.text_edit.setText(self.action.text)
        elif t == "media":
            i = self.media_combo.findData(self.action.key)
            self.media_combo.setCurrentIndex(max(0, i))

    def get_action(self):
        return self.action


class BindingEditor(QFrame):
    """Settings-style editor for one key or encoder binding."""
    binding_changed = Signal()

    def __init__(self, accent: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.accent = accent
        self.kind: str | None = None
        self.id: str | None = None
        self._binding_ref = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        self.title = QLabel("—")
        self.title.setStyleSheet("font-size: 18px; font-weight: 700;")
        head.addWidget(self.title)
        head.addStretch(1)
        self.sub = QLabel("")
        self.sub.setObjectName("dim")
        head.addWidget(self.sub)
        lay.addLayout(head)

        self.rows_host = QVBoxLayout()
        self.rows_host.setSpacing(8)
        lay.addLayout(self.rows_host)

        self.hint = QLabel("Select a key or knob on the pad to edit it.")
        self.hint.setObjectName("dim")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        lay.addStretch(1)

    def set_accent(self, accent: str):
        self.accent = accent

    def clear(self):
        self.kind = self.id = None
        self._binding_ref = None
        self.title.setText("—")
        self.sub.setText("")
        while self.rows_host.count():
            item = self.rows_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.hint.show()

    def _add_label_row(self, binding):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        lbl = QLabel("Label")
        lbl.setObjectName("dim")
        lbl.setFixedWidth(NAME_COL)
        rl.addWidget(lbl)
        self.label_edit = QLineEdit(binding.label)
        self.label_edit.setPlaceholderText("shown on the key")
        self.label_edit.textEdited.connect(lambda _: self.binding_changed.emit())
        rl.addWidget(self.label_edit, 1)
        self.rows_host.addWidget(row)

    def _add_prop_row(self, name, action, on_changed):
        row = PropRow(name, self.accent)
        row.set_action(action)
        row.changed.connect(on_changed)
        self.rows_host.addWidget(row)
        return row

    def show_key(self, kid: str, binding):
        self.clear()
        self.kind, self.id = "key", kid
        self.hint.hide()
        self.title.setText(kid)
        self.sub.setText("key press")
        self._binding_ref = binding
        self._add_label_row(binding)
        row = self._add_prop_row("Action", binding.action, lambda: None)
        row.changed.connect(lambda: self._set_action(row.get_action()))

    def show_encoder(self, eid: str, binding):
        self.clear()
        self.kind, self.id = "encoder", eid
        self.hint.hide()
        self.title.setText(eid)
        self.sub.setText("encoder")
        self._binding_ref = binding
        self._add_label_row(binding)
        for attr, name in (("cw", "↻ Turn right"), ("ccw", "↺ Turn left"),
                           ("press", "Press")):
            row = self._add_prop_row(name, getattr(binding, attr), lambda: None)
            row.changed.connect(lambda a=attr, r=row: self._set_enc(a, r.get_action()))

    def _set_action(self, action):
        self._binding_ref.action = action
        self.binding_changed.emit()

    def _set_enc(self, attr, action):
        setattr(self._binding_ref, attr, action)
        self.binding_changed.emit()

    def current_label(self) -> str:
        return self.label_edit.text().strip()

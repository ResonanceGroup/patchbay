"""Left panel: VS Code settings-editor style property window for the selected control.

Each setting is a row: name + description on the left, control on the right,
with a separator between rows. Sections group related settings.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSizePolicy,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..core.actions import KeysAction, MediaAction, NoneAction, TextAction
from .theme import BORDER, DIM, FAINT, MONO

TYPE_NAMES = [("keys", "Keys"), ("text", "Text"), ("media", "Media"),
              ("macro", "Macro"), ("none", "None")]
VALUE_NAME = {"keys": "Keys", "text": "Text", "media": "Media",
              "macro": "Macro", "none": "Value"}

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

CTRL_W = 230


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


class SettingRow(QFrame):
    """One VS Code-style setting: name+description left, control right."""

    def __init__(self, name: str, desc: str, control: QWidget, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 8, 2, 8)
        lay.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(1)
        n = QLabel(name)
        d = QLabel(desc)
        d.setObjectName("faint")
        d.setStyleSheet(f"color: {FAINT}; font-size: 12px;")
        left.addWidget(n)
        left.addWidget(d)
        lay.addLayout(left, 1)
        control.setFixedWidth(CTRL_W)
        lay.addWidget(control, 0)


class TypeControl(QWidget):
    """Type combo + matching value control; get/set a core Action."""
    changed = Signal()

    def __init__(self, value_name_lbl: QLabel | None = None, parent=None):
        super().__init__(parent)
        self.action = NoneAction()
        self.value_name_lbl = value_name_lbl
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.type_combo = QComboBox()
        for _, tname in TYPE_NAMES:
            self.type_combo.addItem(tname)
        self.type_combo.setFixedWidth(86)
        lay.addWidget(self.type_combo)
        self.stack = QStackedWidget()
        keys_page = QWidget()
        kl = QHBoxLayout(keys_page)
        kl.setContentsMargins(0, 0, 0, 0)
        self.chords = QLabel("")
        self.chords.setStyleSheet(f"color: {DIM}; font-family: '{MONO}';")
        kl.addWidget(self.chords, 1)
        self.recorder = ChordRecorder()
        self.recorder.setFixedWidth(74)
        kl.addWidget(self.recorder)
        self.stack.addWidget(keys_page)
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("text to type")
        self.stack.addWidget(self.text_edit)
        self.media_combo = QComboBox()
        for k in MediaAction.MEDIA_KEYS:
            self.media_combo.addItem(k.replace("_", " "), k)
        self.stack.addWidget(self.media_combo)
        macro_lbl = QLabel("editor coming soon")
        macro_lbl.setStyleSheet(f"color: {FAINT};")
        self.stack.addWidget(macro_lbl)
        none_lbl = QLabel("unbound")
        none_lbl.setStyleSheet(f"color: {FAINT};")
        self.stack.addWidget(none_lbl)
        lay.addWidget(self.stack, 1)

        self.type_combo.currentIndexChanged.connect(self._type_changed)
        self.recorder.captured.connect(self._chord_captured)
        self.text_edit.textEdited.connect(lambda _: self._commit())
        self.media_combo.currentIndexChanged.connect(
            lambda _: self._commit() if self.type_combo.currentIndex() == 2 else None)

    def _tname(self) -> str:
        return TYPE_NAMES[self.type_combo.currentIndex()][0]

    def _type_changed(self, idx):
        self.stack.setCurrentIndex(idx)
        if self.value_name_lbl:
            self.value_name_lbl.setText(VALUE_NAME[self._tname()])
        self._commit()

    def _chord_captured(self, chord):
        self.action = KeysAction(keys=chord)
        self.chords.setText(" + ".join(chord))
        self.type_combo.setCurrentIndex(0)
        self.changed.emit()

    def _commit(self):
        t = self._tname()
        if t == "text":
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
        if self.value_name_lbl:
            self.value_name_lbl.setText(VALUE_NAME[TYPE_NAMES[idx][0]])
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
    """Settings window for one key or encoder binding."""
    binding_changed = Signal()

    def __init__(self, accent: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.accent = accent
        self.kind: str | None = None
        self.id: str | None = None
        self._binding_ref = None
        self.label_edit = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)

        head = QHBoxLayout()
        self.title = QLabel("—")
        self.title.setStyleSheet("font-size: 18px; font-weight: 700;")
        head.addWidget(self.title)
        head.addStretch(1)
        self.sub = QLabel("")
        self.sub.setObjectName("dim")
        head.addWidget(self.sub)
        lay.addLayout(head)

        self.rows = QVBoxLayout()
        self.rows.setSpacing(0)
        lay.addLayout(self.rows)
        lay.addStretch(1)

        self.hint = QLabel("Select a key or knob on the pad to edit it.")
        self.hint.setObjectName("dim")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

    def set_accent(self, accent: str):
        self.accent = accent

    def clear(self):
        self.kind = self.id = None
        self._binding_ref = None
        self.title.setText("—")
        self.sub.setText("")
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.hint.show()

    # ---- building blocks ----
    def _section(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {DIM};"
                         f" padding-top: 10px;")
        self.rows.addWidget(lbl)

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {BORDER}; background: {BORDER};"
                           " max-height: 1px; border: none;")
        self.rows.addWidget(line)

    def _row(self, name: str, desc: str, control: QWidget):
        self.rows.addWidget(SettingRow(name, desc, control))
        self._sep()

    def _label_row(self, binding):
        self.label_edit = QLineEdit(binding.label)
        self.label_edit.setPlaceholderText("shown on the key")
        self.label_edit.textEdited.connect(lambda _: self.binding_changed.emit())
        self._row("Label", "text shown on the key", self.label_edit)

    # ---- public ----
    def show_key(self, kid: str, binding):
        self.clear()
        self.kind, self.id = "key", kid
        self.hint.hide()
        self.title.setText(kid)
        self.sub.setText("key press")
        self._binding_ref = binding
        self._section("GENERAL")
        self._label_row(binding)
        self._section("ACTION")
        value_name = QLabel("Keys")
        tc = TypeControl(value_name)
        tc.set_action(binding.action)
        tc.changed.connect(lambda: self._set_action(tc.get_action()))
        self._row("Type", "what this key does", tc.type_combo)
        self._row(VALUE_NAME[getattr(binding.action, "type", "none")],
                  "the action's value", tc)

    def show_encoder(self, eid: str, binding):
        self.clear()
        self.kind, self.id = "encoder", eid
        self.hint.hide()
        self.title.setText(eid)
        self.sub.setText("encoder")
        self._binding_ref = binding
        self._section("GENERAL")
        self._label_row(binding)
        for attr, sec, desc in (("cw", "TURN RIGHT", "turn the knob clockwise"),
                                ("ccw", "TURN LEFT", "turn the knob counter-clockwise"),
                                ("press", "PRESS", "press the knob down")):
            self._section(sec)
            tc = TypeControl()
            tc.set_action(getattr(binding, attr))
            tc.changed.connect(lambda a=attr, t=tc: self._set_enc(a, t.get_action()))
            self._row("Type", desc, tc.type_combo)
            self._row("Value", "the action's value", tc)

    def _set_action(self, action):
        self._binding_ref.action = action
        self.binding_changed.emit()

    def _set_enc(self, attr, action):
        setattr(self._binding_ref, attr, action)
        self.binding_changed.emit()

    def current_label(self) -> str:
        return self.label_edit.text().strip() if self.label_edit else ""

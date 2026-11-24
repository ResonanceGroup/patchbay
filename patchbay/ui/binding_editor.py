"""Left panel: a Properties-window style grid (property grid) for the
selected control — categories with expand arrows, name | editor rows,
horizontal grid lines, editors embedded in the value column."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QPushButton, QStackedWidget,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from ..core.actions import KeysAction, MediaAction, NoneAction, TextAction
from .theme import DIM, FAINT, MONO

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


GRID_QSS = """
QTreeWidget#propgrid { background: transparent; border: none; outline: 0; }
QTreeWidget#propgrid::item { border-bottom: 1px solid #333336; padding: 4px 2px; }
QTreeWidget#propgrid::item:selected { background: transparent; color: inherit; }
QTreeWidget#propgrid::branch { background: transparent; }
"""


class PropertyGrid(QTreeWidget):
    """Two-column property grid: category rows + name|editor property rows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("propgrid")
        self.setStyleSheet(GRID_QSS)
        self.setHeaderHidden(True)
        self.setColumnCount(2)
        self.setRootIsDecorated(True)
        self.setIndentation(14)
        h = self.header()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        self.setColumnWidth(0, 118)

    def add_category(self, text: str) -> QTreeWidgetItem:
        it = QTreeWidgetItem([text])
        f = QFont(self.font())
        f.setBold(True)
        it.setFont(0, f)
        self.addTopLevelItem(it)
        it.setExpanded(True)
        return it

    def add_property(self, cat: QTreeWidgetItem, name: str,
                     widget: QWidget) -> QTreeWidgetItem:
        it = QTreeWidgetItem([name])
        cat.addChild(it)
        self.setItemWidget(it, 1, widget)
        return it


class ValueStack(QStackedWidget):
    """Editor for an action's value; pages match TYPE_NAMES order."""
    chord_captured = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        keys_page = QWidget()
        kl = QHBoxLayout(keys_page)
        kl.setContentsMargins(0, 2, 0, 2)
        kl.setSpacing(4)
        self.chords = QLabel("")
        self.chords.setStyleSheet(f"color: {DIM}; font-family: '{MONO}';")
        kl.addWidget(self.chords, 1)
        self.recorder = ChordRecorder()
        self.recorder.setFixedWidth(70)
        kl.addWidget(self.recorder)
        self.addWidget(keys_page)
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("text to type")
        self.addWidget(self.text_edit)
        self.media_combo = QComboBox()
        for k in MediaAction.MEDIA_KEYS:
            self.media_combo.addItem(k.replace("_", " "), k)
        self.addWidget(self.media_combo)
        macro_lbl = QLabel("editor coming soon")
        macro_lbl.setStyleSheet(f"color: {FAINT};")
        self.addWidget(macro_lbl)
        none_lbl = QLabel("unbound")
        none_lbl.setStyleSheet(f"color: {FAINT};")
        self.addWidget(none_lbl)
        self.recorder.captured.connect(self.chord_captured)


class BindingEditor(QFrame):
    """Properties window for one key or encoder binding."""
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
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self.title = QLabel("—")
        self.title.setStyleSheet("font-size: 16px; font-weight: 700;")
        head.addWidget(self.title)
        head.addStretch(1)
        self.sub = QLabel("")
        self.sub.setObjectName("dim")
        head.addWidget(self.sub)
        lay.addLayout(head)

        self.grid = PropertyGrid()
        lay.addWidget(self.grid, 1)

        self.hint = QLabel("Select a key or knob on the pad to edit it.")
        self.hint.setObjectName("dim")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

    def set_accent(self, accent: str):
        self.accent = accent

    def clear(self):
        self.kind = self.id = None
        self._binding_ref = None
        self.grid.clear()
        self.title.setText("—")
        self.sub.setText("")
        self.hint.show()

    # ---- action editor wiring for one category ----
    def _add_action(self, cat, action, get, setv):
        combo = QComboBox()
        for _, tname in TYPE_NAMES:
            combo.addItem(tname)
        stack = ValueStack()

        t = getattr(action, "type", "none") if action is not None else "none"
        idx = next((i for i, (n, _) in enumerate(TYPE_NAMES) if n == t), 4)
        combo.setCurrentIndex(idx)
        stack.setCurrentIndex(idx)
        if t == "keys":
            stack.chords.setText(" + ".join(action.keys))
        elif t == "text":
            stack.text_edit.setText(action.text)
        elif t == "media":
            i = stack.media_combo.findData(action.key)
            stack.media_combo.setCurrentIndex(max(0, i))

        self.grid.add_property(cat, "Type", combo)
        vitem = self.grid.add_property(cat, VALUE_NAME[TYPE_NAMES[idx][0]], stack)

        def on_type(i):
            stack.setCurrentIndex(i)
            vitem.setText(0, VALUE_NAME[TYPE_NAMES[i][0]])
            _commit()

        def on_chord(chord):
            setv(KeysAction(keys=chord))
            stack.chords.setText(" + ".join(chord))
            combo.setCurrentIndex(0)
            self.binding_changed.emit()

        def _commit():
            tn = TYPE_NAMES[combo.currentIndex()][0]
            if tn == "text":
                setv(TextAction(text=stack.text_edit.text()))
            elif tn == "media":
                setv(MediaAction(key=stack.media_combo.currentData()))
            elif tn == "none":
                setv(NoneAction())
            self.binding_changed.emit()

        combo.currentIndexChanged.connect(on_type)
        stack.chord_captured.connect(on_chord)
        stack.text_edit.textEdited.connect(lambda _: _commit())
        stack.media_combo.currentIndexChanged.connect(
            lambda _: _commit() if combo.currentIndex() == 2 else None)

    def _label_row(self, cat, binding):
        self.label_edit = QLineEdit(binding.label)
        self.label_edit.setPlaceholderText("shown on the key")
        self.label_edit.textEdited.connect(lambda _: self.binding_changed.emit())
        self.grid.add_property(cat, "Label", self.label_edit)

    # ---- public ----
    def show_key(self, kid: str, binding):
        self.clear()
        self.kind, self.id = "key", kid
        self.hint.hide()
        self.title.setText(kid)
        self.sub.setText("key press")
        self._binding_ref = binding
        gen = self.grid.add_category("General")
        self._label_row(gen, binding)
        act = self.grid.add_category("Action")
        self._add_action(act, binding.action,
                         lambda: binding.action,
                         lambda a: self._set_action(a))

    def show_encoder(self, eid: str, binding):
        self.clear()
        self.kind, self.id = "encoder", eid
        self.hint.hide()
        self.title.setText(eid)
        self.sub.setText("encoder")
        self._binding_ref = binding
        gen = self.grid.add_category("General")
        self._label_row(gen, binding)
        for attr, sec in (("cw", "Turn right"), ("ccw", "Turn left"),
                          ("press", "Press")):
            cat = self.grid.add_category(sec)
            self._add_action(cat, getattr(binding, attr),
                             lambda: getattr(binding, attr),
                             lambda a, at=attr: self._set_enc(at, a))

    def _set_action(self, action):
        self._binding_ref.action = action
        self.binding_changed.emit()

    def _set_enc(self, attr, action):
        setattr(self._binding_ref, attr, action)
        self.binding_changed.emit()

    def current_label(self) -> str:
        return self.label_edit.text().strip() if self.label_edit else ""

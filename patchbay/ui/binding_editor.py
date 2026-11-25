"""Left panel: a replica of the classic WinForms PropertyGrid control.

Anatomy (System.Windows.Forms.PropertyGrid):
  - toolbar strip (sort: categorized / alphabetical)
  - object header combo showing the selected object
  - two-column grid: property name | value editor, vertical divider,
    horizontal row lines, categories with +/- boxes and bold labels
  - help/description panel at the bottom for the selected property
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPalette, QPolygon
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QScrollBar, QStackedWidget,
                               QStyledItemDelegate,
                               QStyleOptionViewItem, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.actions import KeysAction, MediaAction, NoneAction, TextAction
from ..core.profile import ENCODER_IDS, KEY_IDS
from .theme import DIM, FAINT, MONO, TEXT

TYPE_NAMES = [("keys", "Keys"), ("text", "Text"), ("media", "Media"),
              ("macro", "Macro"), ("none", "None")]
VALUE_NAME = {"keys": "Keys", "text": "Text", "media": "Media",
              "macro": "Macro", "none": "Value"}
VALUE_DESC = {"keys": "Chord to send on press",
              "text": "Text typed on press",
              "media": "Media key sent on press",
              "macro": "Sequence of actions",
              "none": "No action"}

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

LINE = "#3f3f46"
CAT_BG = "#2d2d30"


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
        # own rule so the page's cascade doesn't flatten the button
        self.setStyleSheet("background: #2d2d30; border: 1px solid #3f3f46;"
                           " border-radius: 4px; padding: 5px 8px;"
                           " color: #d4d4d4;")

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


class WinScrollBar(QScrollBar):
    """Windows-style scrollbar: dark track, chunky handle, up/down arrow
    buttons. Painted directly — Qt 6 QSS cannot render scrollbar arrows and
    the Windows QStyle segfaults under a QSS ancestor."""

    BTN = 21

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(self.BTN)
        self.setMouseTracking(True)
        self._hover = 0
        self._drag_off = None

    def _rects(self):
        w, h = self.width(), self.height()
        top = QRect(0, 0, w, self.BTN)
        bot = QRect(0, h - self.BTN, w, self.BTN)
        ttop, theight = self.BTN, h - 2 * self.BTN
        rng = self.maximum() - self.minimum()
        page = max(1, self.pageStep())
        if rng <= 0:
            hh, yy = theight, ttop
        else:
            hh = max(30, int(theight * page / (rng + page)))
            span = theight - hh
            yy = ttop + int(span * (self.value() - self.minimum()) / rng)
        return top, bot, QRect(0, yy, w, hh), (ttop, theight)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#1e1e1e"))
        top, bot, handle, _ = self._rects()
        for r, idx in ((top, 1), (bot, 2)):
            p.fillRect(r, QColor("#4a4a52") if self._hover == idx
                       else QColor("#3e3e42"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#d4d4d4"))
        cx = self.width() // 2
        p.drawPolygon(QPolygon([QPoint(cx - 6, top.y() + 13),
                                QPoint(cx, top.y() + 7),
                                QPoint(cx + 6, top.y() + 13)]))
        p.drawPolygon(QPolygon([QPoint(cx - 6, bot.y() + 8),
                                QPoint(cx + 6, bot.y() + 8),
                                QPoint(cx, bot.y() + 14)]))
        # when there is nothing to scroll, the thumb would fill the whole
        # track — hide just the thumb, keep the track and arrow buttons.
        if self.maximum() > self.minimum():
            p.setBrush(QColor("#565660"))
            p.drawRect(handle)
            p.setPen(QPen(QColor("#6e6e78")))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(handle.adjusted(0, 0, -1, -1))
        p.setPen(QPen(QColor("#1e1e1e")))
        p.drawLine(0, self.BTN - 1, self.width(), self.BTN - 1)
        p.drawLine(0, self.height() - self.BTN,
                   self.width(), self.height() - self.BTN)

    def mousePressEvent(self, e):
        top, bot, handle, _ = self._rects()
        pos = e.position().toPoint()
        if top.contains(pos):
            self.setValue(self.value() - self.singleStep())
        elif bot.contains(pos):
            self.setValue(self.value() + self.singleStep())
        elif handle.contains(pos):
            self._drag_off = pos.y() - handle.top()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        top, bot, handle, (ttop, theight) = self._rects()
        pos = e.position().toPoint()
        if self._drag_off is not None:
            rng = self.maximum() - self.minimum()
            hh = handle.height()
            yy = max(ttop, min(ttop + theight - hh, pos.y() - self._drag_off))
            if theight > hh:
                self.setValue(self.minimum() +
                              round((yy - ttop) * rng / (theight - hh)))
            return
        h = 1 if top.contains(pos) else 2 if bot.contains(pos) else 0
        if h != self._hover:
            self._hover = h
            self.update()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_off = None
        super().mouseReleaseEvent(e)


class GridComboBox(QComboBox):
    """Combo whose popup opens below the box and has no white container bands."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = self.view()
        pal = v.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#2d2d30"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#2d2d30"))
        v.setPalette(pal)

    def showPopup(self):
        super().showPopup()
        v = self.view()
        c = v.parentWidget()  # the popup container (top-level)
        cpal = c.palette()
        cpal.setColor(QPalette.ColorRole.Window, QColor("#2d2d30"))
        cpal.setColor(QPalette.ColorRole.Base, QColor("#2d2d30"))
        c.setPalette(cpal)
        # no dead space around the view inside the container: the popup
        # container adds 4px spacer items above/below the view
        orig = c.size()
        c.setFrameShape(QFrame.Shape.NoFrame)
        if c.layout() is not None:
            c.layout().setContentsMargins(0, 0, 0, 0)
            lay = c.layout()
            i = 0
            while i < lay.count():
                if lay.itemAt(i).spacerItem() is not None:
                    lay.removeItem(lay.itemAt(i))
                else:
                    i += 1
        c.setFixedSize(orig.width(), orig.height() - 8)
        # arrow flips while open
        self.setProperty("open", True)
        self.style().polish(self)
        h = c.size().height()
        below = self.mapToGlobal(QPoint(0, self.height()))
        screen = self.screen().geometry()
        if below.y() + h > screen.bottom():
            # flip above the box, never covering it
            c.setGeometry(QRect(below + QPoint(0, -self.height() - h),
                                c.size()))
        else:
            c.setGeometry(QRect(below, c.size()))

    def hidePopup(self):
        super().hidePopup()
        self.setProperty("open", False)
        self.style().polish(self)


class ValueStack(QStackedWidget):
    """Editor for an action's value; pages match TYPE_NAMES order."""
    chord_captured = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("vstack")
        # bare own-rule covers every page; children that need a different
        # color (the rec button) carry their own rule. border-bottom on the
        # stack spans the full cell, including under the rec button.
        self.setStyleSheet("background: #252526;"
                           " border-bottom: 1px solid #37373d;")
        keys_page = QWidget()
        keys_page.setObjectName("keyspage")
        # bare own-rule: beats the global QWidget bg rule (id selectors lose
        # across stylesheet boundaries in Qt's cascade)
        keys_page.setStyleSheet("background: #252526;")
        kl = QHBoxLayout(keys_page)
        kl.setContentsMargins(0, 0, 3, 0)
        kl.setSpacing(4)
        self.chords = QLabel("")
        self.chords.setStyleSheet(f"color: {DIM}; font-family: '{MONO}';"
                                  " padding-left: 6px;")
        kl.addWidget(self.chords, 1)
        self.recorder = ChordRecorder()
        self.recorder.setFixedWidth(70)
        kl.addWidget(self.recorder)
        self.addWidget(keys_page)
        self.text_edit = QLineEdit()
        self.text_edit.setMinimumHeight(26)
        self.text_edit.setPlaceholderText("text to type")
        self.addWidget(self.text_edit)
        self.media_combo = GridComboBox()
        self.media_combo.setMinimumHeight(26)
        for k in MediaAction.MEDIA_KEYS:
            self.media_combo.addItem(k.replace("_", " "), k)
        self.addWidget(self.media_combo)
        macro_lbl = QLabel("editor coming soon")
        macro_lbl.setStyleSheet(f"color: {FAINT}; padding-left: 6px;")
        self.addWidget(macro_lbl)
        none_lbl = QLabel("unbound")
        none_lbl.setStyleSheet(f"color: {FAINT}; padding-left: 6px;")
        self.addWidget(none_lbl)
        self.recorder.captured.connect(self.chord_captured)


class _GridDelegate(QStyledItemDelegate):
    """Draws the vertical column divider and KiCad-style chevron toggles."""

    def paint(self, p, opt, index):
        is_cat = index.sibling(index.row(), 0).data(Qt.UserRole) == "cat"
        r = opt.rect
        if is_cat:
            p.fillRect(r, QColor("#37373d"))
        else:
            p.fillRect(r, QColor("#252526"))
            if index.column() == 0:
                # narrow heading-colored gutter along the left edge
                p.fillRect(QRect(r.left(), r.top(), 22, r.height()),
                           QColor("#37373d"))
        text = index.data(Qt.DisplayRole) or ""
        p.setFont(opt.font)
        if index.column() == 0 and text:
            off = 22 if is_cat else 28
            p.setPen(QColor("#e8e8e8") if is_cat else QColor("#d4d4d4"))
            p.drawText(r.adjusted(off, 0, -4, 0),
                       int(Qt.AlignVCenter | Qt.AlignLeft), text)
        if is_cat:
            if index.column() != 0:
                return
            cx, cy = r.left() + 10, r.center().y()
            pen = QPen(QColor("#c8c8c8"))
            pen.setWidthF(1.6)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            if index.data(Qt.UserRole + 1):  # expanded: down chevron
                p.drawPolyline([QPoint(cx - 4, cy - 2), QPoint(cx, cy + 2),
                                QPoint(cx + 4, cy - 2)])
            else:  # collapsed: right chevron
                p.drawPolyline([QPoint(cx - 2, cy - 4), QPoint(cx + 2, cy),
                                QPoint(cx - 2, cy + 4)])
            return
        p.setPen(QPen(QColor("#37373d")))
        if index.column() == 0:
            # row line starts after the gutter; gutter itself stays clean
            p.drawLine(QPoint(r.left() + 22, r.bottom()), r.bottomRight())
            p.drawLine(r.topRight(), r.bottomRight())
        else:
            p.drawLine(r.bottomLeft(), r.bottomRight())


GRID_QSS = """
QTreeWidget#propgrid { background: #252526; border: 1px solid #3f3f46;
    outline: 0; font-size: 14px; }
QTreeWidget#propgrid QLineEdit, QTreeWidget#propgrid QComboBox {
    background: #252526; border: none; border-bottom: 1px solid #37373d;
    padding: 4px 6px; min-height: 18px; }
QTreeWidget#propgrid QComboBox::drop-down { background: transparent;
    border: none; width: 18px; margin-right: 6px; }
QTreeWidget#propgrid QComboBox::down-arrow { image: url(_ARROW_PNG_);
    width: 12px; height: 8px; }
QTreeWidget#propgrid QComboBox[open="true"]::down-arrow {
    image: url(_UP_ARROW_PNG_); }
QTreeWidget#propgrid QLineEdit:focus { border: 1px solid #007acc; }
QTreeWidget#propgrid QComboBox QAbstractItemView { background: #2d2d30;
    border: 1px solid #3f3f46; selection-background-color: #3399ff; }
QTreeWidget#propgrid QScrollBar:vertical {
    background: #1e1e1e; width: 21px; margin: 0; }
"""
# absolute paths to the arrow assets (QSS url() is cwd-relative otherwise);
# replace the compound placeholders first — they contain _ARROW_PNG_ as a
# substring
GRID_QSS = GRID_QSS.replace(
    "_UP_ARROW_PNG_", str(Path(__file__).parent / "assets" / "up_arrow.png"))
GRID_QSS = GRID_QSS.replace(
    "_DOWN_ARROW_PNG_", str(Path(__file__).parent / "assets" / "down_arrow.png"))
GRID_QSS = GRID_QSS.replace(
    "_UP_BTN_PNG_", str(Path(__file__).parent / "assets" / "up_btn.png"))
GRID_QSS = GRID_QSS.replace(
    "_DOWN_BTN_PNG_", str(Path(__file__).parent / "assets" / "down_btn.png"))
GRID_QSS = GRID_QSS.replace(
    "_ARROW_PNG_", str(Path(__file__).parent / "assets" / "down_arrow.png"))


class PropertyGrid(QTreeWidget):
    """Two-column property grid with +/- category toggles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("propgrid")
        self.setStyleSheet(GRID_QSS)
        self.setHeaderHidden(True)
        self.setColumnCount(2)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setItemDelegate(_GridDelegate())
        self.header().setStretchLastSection(True)
        self.setColumnWidth(0, 118)

    def mousePressEvent(self, e):
        it = self.itemAt(e.position().toPoint())
        if (it is not None and it.parent() is None
                and it.childCount() > 0
                and e.position().x() <= 22):
            it.setExpanded(not it.isExpanded())
            self._sync_cat_state(it)
            return
        super().mousePressEvent(e)

    def add_category(self, text: str) -> QTreeWidgetItem:
        it = QTreeWidgetItem([text])
        f = QFont(self.font())
        f.setBold(True)
        it.setFont(0, f)
        it.setData(0, Qt.UserRole, "cat")
        it.setBackground(0, QColor("#45454b"))
        it.setBackground(1, QColor("#45454b"))
        it.setSizeHint(0, QSize(0, 25))
        self.addTopLevelItem(it)
        it.setExpanded(True)
        self._sync_cat_state(it)
        return it

    def _sync_cat_state(self, it: QTreeWidgetItem):
        it.setData(0, Qt.UserRole + 1, it.isExpanded())

    def add_property(self, cat: QTreeWidgetItem | None, name: str,
                     widget: QWidget, desc: str = "") -> QTreeWidgetItem:
        if cat is None:
            it = QTreeWidgetItem([name])
            self.addTopLevelItem(it)
        else:
            it = QTreeWidgetItem([name])
            cat.addChild(it)
        it.setSizeHint(0, QSize(0, 34))
        it.setBackground(0, QColor("#3c3c3c"))
        it.setBackground(1, QColor("#3c3c3c"))
        it.setData(0, Qt.UserRole + 2, desc)
        self.setItemWidget(it, 1, widget)
        return it


class BindingEditor(QFrame):
    """PropertyGrid-style editor for one key or encoder binding."""
    binding_changed = Signal()
    control_selected = Signal(str, str)  # ("key"|"encoder"), id

    def __init__(self, accent: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.accent = accent
        self.kind: str | None = None
        self.id: str | None = None
        self._binding_ref = None
        self.label_edit = None
        self.categorized = True

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        # panel title, same style as the Profiles heading
        ptitle = QLabel("Properties")
        ptitle.setStyleSheet("font-weight: 700; font-size: 14px;")
        lay.addWidget(ptitle)

        # toolbar strip
        tb = QHBoxLayout()
        tb.setSpacing(4)
        self.sort_btn = QToolButton()
        self.sort_btn.setCheckable(True)
        self.sort_btn.clicked.connect(self._toggle_sort)
        self._update_sort_btn()
        tb.addWidget(self.sort_btn)
        tb.addStretch(1)
        self.sub = QLabel("")
        self.sub.setObjectName("dim")
        tb.addWidget(self.sub)
        lay.addLayout(tb)

        # object header combo
        self.obj_combo = GridComboBox()
        self.obj_combo.setObjectName("objheader")
        self.obj_combo.setStyleSheet(
            "QComboBox#objheader { background: #2d2d30; border: 1px solid "
            "#3f3f46; border-radius: 4px; font-size: 15px; padding: 5px 8px; }"
            "QComboBox#objheader::drop-down { border: none; width: 18px; }"
            "QComboBox#objheader QAbstractItemView { background: #2d2d30; "
            "border: 1px solid #3f3f46; selection-background-color: #37373d; }")
        self.obj_combo.setEditable(False)
        for kid in KEY_IDS:
            self.obj_combo.addItem(kid, ("key", kid))
        for eid in ENCODER_IDS:
            self.obj_combo.addItem(eid, ("encoder", eid))
        self.obj_combo.currentIndexChanged.connect(self._obj_changed)
        lay.addWidget(self.obj_combo)

        self.grid = PropertyGrid()
        self.grid.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.grid.setVerticalScrollBar(WinScrollBar(self.grid))
        lay.addWidget(self.grid, 1)
        self.grid.currentItemChanged.connect(self._help_update)

        # help/description panel — VS Properties style: flat, same background
        # as the grid, no box, just a divider line above; labels fill the frame
        self.help_panel = QFrame()
        self.help_panel.setStyleSheet(
            "QFrame#helppanel { border: none; border-top: 1px solid #37373d;"
            " background: #252526; }")
        self.help_panel.setObjectName("helppanel")
        hp = QVBoxLayout(self.help_panel)
        hp.setContentsMargins(0, 0, 0, 0)
        hp.setSpacing(0)
        self.help_name = QLabel("")
        f = QFont()
        f.setBold(True)
        self.help_name.setFont(f)
        self.help_name.setStyleSheet("padding: 5px 6px 0 6px;")
        self.help_desc = QLabel("")
        self.help_desc.setObjectName("dim")
        self.help_desc.setWordWrap(True)
        self.help_desc.setStyleSheet("padding: 1px 6px 5px 6px;")
        hp.addWidget(self.help_name)
        hp.addWidget(self.help_desc)
        lay.addWidget(self.help_panel)

        self.hint = QLabel("Select a key or knob on the pad to edit it.")
        self.hint.setObjectName("dim")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

    def set_accent(self, accent: str):
        self.accent = accent

    def _update_sort_btn(self):
        if self.categorized:
            self.sort_btn.setText("Cat")
            self.sort_btn.setToolTip("Sorted by category — click for A→Z")
        else:
            self.sort_btn.setText("A→Z")
            self.sort_btn.setToolTip("Sorted A→Z — click for category")

    def _toggle_sort(self):
        self.categorized = not self.categorized
        self._update_sort_btn()
        if self._binding_ref is not None:
            self._rebuild()

    def _obj_changed(self, idx):
        data = self.obj_combo.itemData(idx)
        if data:
            self.control_selected.emit(*data)

    def clear(self):
        self.kind = self.id = None
        self._binding_ref = None
        self.grid.clear()
        self.sub.setText("")
        self.help_name.setText("")
        self.help_desc.setText("")
        self.hint.show()

    # ---- action editor wiring ----
    def _add_action(self, cat, action, setv, prefix=""):
        combo = GridComboBox()
        combo.setMinimumHeight(26)
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

        self.grid.add_property(cat, prefix + "Type", combo,
                               "What this control does")
        vitem = self.grid.add_property(cat, prefix + VALUE_NAME[TYPE_NAMES[idx][0]],
                                       stack, VALUE_DESC[TYPE_NAMES[idx][0]])

        def on_type(i):
            stack.setCurrentIndex(i)
            vitem.setText(0, prefix + VALUE_NAME[TYPE_NAMES[i][0]])
            vitem.setData(0, Qt.UserRole + 2, VALUE_DESC[TYPE_NAMES[i][0]])
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

    def _build(self):
        """Populate the grid for the current binding (used by both modes)."""
        b = self._binding_ref
        enc = self.kind == "encoder"

        def gen_label(cat):
            self.label_edit = QLineEdit(b.label)
            self.label_edit.setMinimumHeight(26)
            self.label_edit.setPlaceholderText("shown on the key")
            self.label_edit.textEdited.connect(
                lambda _: self.binding_changed.emit())
            self.grid.add_property(cat, "Label", self.label_edit,
                                   "Text shown on the control")

        def gen_action(cat, attr, sec, prefix=""):
            act = getattr(b, attr) if enc else b.action
            self._add_action(cat, act,
                             lambda a, at=attr: (
                                 setattr(b, at, a) if enc
                                 else setattr(b, "action", a))
                             or self.binding_changed.emit(), prefix)

        if enc:
            if self.categorized:
                gen_label(self.grid.add_category("General"))
                for attr, sec in (("cw", "Turn right"), ("ccw", "Turn left"),
                                  ("press", "Press")):
                    gen_action(self.grid.add_category(sec), attr, sec)
            else:
                gen_label(None)
                for attr, sec, pre in (("cw", "Turn right", "Right "),
                                       ("ccw", "Turn left", "Left "),
                                       ("press", "Press", "Press ")):
                    gen_action(None, attr, sec, pre)
                self._sort_flat()
        else:
            if self.categorized:
                gen_label(self.grid.add_category("General"))
                gen_action(self.grid.add_category("Action"), "action", "Action")
            else:
                gen_label(None)
                gen_action(None, "action", "Action")
                self._sort_flat()

    def _sort_flat(self):
        # Reorder top-level rows alphabetically. takeTopLevelItem removes
        # WITHOUT deleting (clear() would destroy the items + their widgets).
        # But removing an item detaches its column-1 setItemWidget control, so
        # capture each widget first and re-apply it after re-adding — otherwise
        # the alphabetical view shows only the row names, no value controls.
        n = self.grid.topLevelItemCount()
        rows = [(self.grid.topLevelItem(i).text(0),
                 self.grid.itemWidget(self.grid.topLevelItem(i), 1))
                for i in range(n)]
        items = [self.grid.takeTopLevelItem(0) for _ in range(n)]
        for (name, w), it in sorted(zip(rows, items), key=lambda p: p[0][0]):
            self.grid.addTopLevelItem(it)
            if w is not None:
                self.grid.setItemWidget(it, 1, w)

    def _rebuild(self):
        b = self._binding_ref
        kind, kid = self.kind, self.id
        if b is None:
            return
        self.grid.clear()
        self._build()
        self._binding_ref = b
        self.kind, self.id = kind, kid

    # ---- public ----
    def show_key(self, kid: str, binding):
        self.clear()
        self.kind, self.id = "key", kid
        self.hint.hide()
        self._binding_ref = binding
        self.sub.setText(f"{kid} · key press")
        self._set_combo("key", kid)
        self._build()

    def show_encoder(self, eid: str, binding):
        self.clear()
        self.kind, self.id = "encoder", eid
        self.hint.hide()
        self._binding_ref = binding
        self.sub.setText(f"{eid} · encoder")
        self._set_combo("encoder", eid)
        self._build()

    def _set_combo(self, kind, cid):
        for i in range(self.obj_combo.count()):
            if self.obj_combo.itemData(i) == (kind, cid):
                self.obj_combo.blockSignals(True)
                self.obj_combo.setCurrentIndex(i)
                self.obj_combo.blockSignals(False)
                break

    def _help_update(self, cur, _prev):
        if cur is None:
            self.help_name.setText("")
            self.help_desc.setText("")
            return
        self.help_name.setText(cur.text(0))
        self.help_desc.setText(cur.data(0, Qt.UserRole + 2) or "")

    def _set_action(self, action):
        self._binding_ref.action = action
        self.binding_changed.emit()

    def _set_enc(self, attr, action):
        setattr(self._binding_ref, attr, action)
        self.binding_changed.emit()

    def current_label(self) -> str:
        return self.label_edit.text().strip() if self.label_edit else ""

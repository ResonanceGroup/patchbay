"""Interactive replica of the pad, built from real buttons.

Portrait layout matching the hardware: two encoders on top, 3x4 key grid,
layer button + LEDs to the right of the top row.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from ..core.profile import ENCODER_IDS, KEY_IDS, PHYSICAL_KEY_ORDER
from .theme import BORDER, DIM, FAINT, KEY_HOVER, PANEL, TEXT, key_qss


class KnobRow(QWidget):
    """Two painted encoder knobs with labels; clickable."""
    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile = None
        self.layer_idx = 0
        self.sel_id: str | None = None
        self.accent = "#007acc"
        self._knob_rects: dict[str, QRectF] = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(150)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        kr = min(w * 0.10, h * 0.34)
        kcy = h * 0.42
        # center each knob over the outer key columns of the grid below
        # (grid: 3 cols, 14px spacing, same side margins as this row's parent)
        colw = (w - 2 * 14) / 3
        self._knob_rects.clear()
        for i, eid in enumerate(ENCODER_IDS):
            kcx = colw * 0.5 if i == 0 else w - colw * 0.5
            rect = QRectF(kcx - kr, kcy - kr, 2 * kr, 2 * kr)
            self._knob_rects[eid] = rect
            self._paint_knob(p, eid, rect)
        p.end()

    def _paint_knob(self, p: QPainter, eid: str, rect: QRectF):
        c = rect.center()
        r = rect.width() / 2
        if self.sel_id == eid:
            p.setPen(QPen(QColor(self.accent), 2.5))
        else:
            p.setPen(QPen(QColor(BORDER), 1.5))
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, QColor(KEY_HOVER))
        grad.setColorAt(1, QColor("#26262a"))
        p.setBrush(QBrush(grad))
        p.drawEllipse(c, r, r)
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawEllipse(c, r * 0.72, r * 0.72)
        pen = QPen(QColor(TEXT), 3)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(c.x(), c.y() - r * 0.62), QPointF(c.x(), c.y() - r * 0.30))

        binding = None
        if self.profile:
            binding = self.profile.layer(self.layer_idx).encoder(eid)
        label = (binding.display_label() if binding else "") or eid
        f = QFont(self.font())
        f.setPointSizeF(12)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT if binding else FAINT))
        p.drawText(QRectF(c.x() - r - 30, rect.bottom() + 8, 2 * r + 60, 20),
                   Qt.AlignHCenter, label)
        if binding and (binding.cw or binding.ccw):
            fm = QFont("DejaVu Sans Mono")
            fm.setPointSizeF(8.5)
            p.setFont(fm)
            p.setPen(QColor(DIM))
            left = binding.ccw.summary() if binding.ccw else ""
            right = binding.cw.summary() if binding.cw else ""
            p.drawText(QRectF(c.x() - r - 60, rect.bottom() + 30, 2 * r + 120, 16),
                       Qt.AlignHCenter, f"↺ {left}   {right} ↻")

    def mousePressEvent(self, e):
        for eid, rect in self._knob_rects.items():
            if rect.adjusted(-6, -6, 6, 40).contains(e.position()):
                self.sel_id = eid
                self.selected.emit(eid)
                self.update()
                return


class LedRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layer_idx = 0
        self.accent = "#007acc"
        self.setFixedHeight(14)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for i in range(3):
            cx = self.width() - 10 - (2 - i) * 18
            on = i == self.layer_idx
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self.accent if on else "#3f3f46"))
            p.drawEllipse(QPointF(cx, 7), 5 if on else 3.5, 5 if on else 3.5)
            if on:
                p.setOpacity(0.25)
                p.drawEllipse(QPointF(cx, 7), 9, 9)
                p.setOpacity(1.0)
        p.end()


class KeypadWidget(QWidget):
    selected = Signal(str, str)  # ("key"|"encoder"), id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile = None
        self.layer_idx = 0
        self.sel: tuple[str, str] | None = None
        self.accent = "#007acc"

        # 4:3 landscape case: width expands, height stays at the layout's hint
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(14)

        self.knob_row = KnobRow()
        self.knob_row.selected.connect(lambda eid: self.selected.emit("encoder", eid))
        lay.addWidget(self.knob_row)

        # LEDs between the encoders and the keys, like the real pad
        self.leds = LedRow()
        self.leds.setFixedWidth(64)
        led_host = QHBoxLayout()
        led_host.setContentsMargins(0, 0, 0, 0)
        led_host.addStretch(1)
        led_host.addWidget(self.leds)
        led_host.addStretch(1)
        lay.addLayout(led_host)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.key_btns: dict[str, QPushButton] = {}
        self.key_lbls: dict[str, tuple[QLabel, QLabel]] = {}
        # Place ids in PHYSICAL pad order so the replica matches the hardware
        # (top-left cell = K04, etc.), not firmware reading order.
        for idx, kid in enumerate(PHYSICAL_KEY_ORDER):
            r, c = divmod(idx, 3)
            b = QPushButton()
            b.setCheckable(True)
            b.setMinimumHeight(52)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, k=kid: self._pick_key(k))
            inner = QVBoxLayout(b)
            inner.setContentsMargins(4, 8, 4, 8)
            inner.setSpacing(2)
            lbl = QLabel("")
            lbl.setAlignment(Qt.AlignCenter)
            f = QFont(b.font())
            f.setBold(True)
            f.setPointSizeF(11)
            lbl.setFont(f)
            code = QLabel("")
            code.setAlignment(Qt.AlignCenter)
            fm = QFont("DejaVu Sans Mono")
            fm.setPointSizeF(9)
            code.setFont(fm)
            code.setStyleSheet(f"color: {DIM}; background: transparent;")
            inner.addWidget(lbl)
            inner.addWidget(code)
            grid.addWidget(b, r, c)
            self.key_btns[kid] = b
            self.key_lbls[kid] = (lbl, code)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        lay.addStretch(1)

    # ---------- state ----------
    def set_accent(self, accent: str):
        self.accent = accent
        self.knob_row.accent = accent
        self.leds.accent = accent
        self.key_btns[KEY_IDS[0]].setStyleSheet(key_qss(accent))
        for b in self.key_btns.values():
            b.setStyleSheet(key_qss(accent))
        self.update()

    def set_profile(self, profile, layer_idx: int):
        self.profile = profile
        self.layer_idx = layer_idx
        self.refresh()

    def refresh(self):
        if not self.profile:
            return
        layer = self.profile.layer(self.layer_idx)
        for kid, b in self.key_btns.items():
            lbl, code = self.key_lbls[kid]
            binding = layer.binding(kid)
            label = binding.display_label()
            action = binding.action
            combo = action.summary() if action and action.summary() != label else ""
            lbl.setText(label or "—")
            lbl.setStyleSheet("" if label else f"color: {FAINT}; background: transparent;")
            code.setText(combo)
        self.knob_row.profile = self.profile
        self.knob_row.layer_idx = self.layer_idx
        self.leds.layer_idx = self.layer_idx
        self.knob_row.update()
        self.leds.update()
        self.update()

    def select(self, kind: str, ident: str):
        self.sel = (kind, ident)
        for kid, b in self.key_btns.items():
            b.setChecked(kind == "key" and kid == ident)
        self.knob_row.sel_id = ident if kind == "encoder" else None
        self.knob_row.update()

    def _pick_key(self, kid: str):
        self.select("key", kid)
        self.selected.emit("key", kid)

    # ---------- case ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(8, 8, -8, -8), 18, 18)
        p.fillPath(path, QColor(PANEL))
        p.setPen(QPen(QColor(BORDER), 1.5))
        p.drawPath(path)
        p.end()

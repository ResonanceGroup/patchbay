"""Interactive replica of the pad. The centerpiece of the editor."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import QWidget

from ..core.profile import ENCODER_IDS, KEY_IDS
from .theme import BORDER, DIM, FAINT, KEY, KEY_TOP, PANEL, TEXT


class KeypadWidget(QWidget):
    selected = Signal(str, str)  # kind ("key"|"encoder"), id
    layer_cycle = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile = None
        self.layer_idx = 0
        self.sel: tuple[str, str] | None = None
        self.accent = "#4a8fd4"
        self._key_rects: dict[str, QRectF] = {}
        self._knob_rects: dict[str, QRectF] = {}
        self.setMinimumSize(560, 520)
        self.setMouseTracking(True)
        self._hover: tuple[str, str] | None = None

    def set_profile(self, profile, layer_idx: int):
        self.profile = profile
        self.layer_idx = layer_idx
        self.accent = profile.accent
        self.update()

    def select(self, kind: str, ident: str):
        self.sel = (kind, ident)
        self.update()

    # ---------- layout ----------
    def _layout(self):
        w, h = self.width(), self.height()
        margin = 26
        # case aspect ~ 520:490 from the line diagram
        cw = min(w - 2 * margin, (h - 2 * margin) * 520 / 490)
        ch = cw * 490 / 520
        x0 = (w - cw) / 2
        y0 = (h - ch) / 2
        self._case = QRectF(x0, y0, cw, ch)
        self._key_rects.clear()
        self._knob_rects.clear()

        # knobs
        kr = cw * 0.085
        kcy = y0 + ch * 0.20
        for i, eid in enumerate(ENCODER_IDS):
            kcx = x0 + cw * (0.32 + 0.36 * i)
            self._knob_rects[eid] = QRectF(kcx - kr, kcy - kr, 2 * kr, 2 * kr)

        # key grid 3 x 4, centered
        cell = cw * 0.20
        kh = cell * 0.78
        gw = 2 * cell + kh
        gx = x0 + (cw - gw) / 2
        gy = y0 + ch * 0.42
        pitch_y = (ch * 0.50) / 4
        for idx, kid in enumerate(KEY_IDS):
            r, c = divmod(idx, 3)
            kx = gx + c * cell
            ky = gy + r * pitch_y
            self._key_rects[kid] = QRectF(kx, ky, kh, kh * 0.78)

        # hardware layer button + LEDs, right of the grid
        lbw, lbh = cw * 0.11, cw * 0.07
        self._layer_btn = QRectF(gx + gw + cw * 0.045, gy + kh * 0.10, lbw, lbh)
        self._leds = [QRectF(self._layer_btn.x() + i * lbw * 0.42 - 4,
                             self._layer_btn.bottom() + 14, 8, 8) for i in range(3)]

    # ---------- paint ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._layout()

        # case
        path = QPainterPath()
        path.addRoundedRect(self._case, 22, 22)
        p.fillPath(path, QColor(PANEL))
        p.setPen(QPen(QColor(BORDER), 1.5))
        p.drawPath(path)

        layer = self.profile.layer(self.layer_idx) if self.profile else None

        # knobs
        for eid, rect in self._knob_rects.items():
            self._paint_knob(p, eid, rect, layer)

        # keys
        for kid, rect in self._key_rects.items():
            self._paint_key(p, kid, rect, layer)

        # layer button + LEDs
        self._paint_layer_btn(p)

        p.end()

    def _paint_layer_btn(self, p: QPainter):
        r = self._layer_btn
        path = QPainterPath()
        path.addRoundedRect(r, 7, 7)
        p.fillPath(path, QColor(KEY))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawPath(path)
        f = QFont(self.font())
        f.setPointSizeF(9)
        p.setFont(f)
        p.setPen(QColor(DIM))
        p.drawText(r, Qt.AlignCenter, "layer")
        for i, lr in enumerate(self._leds):
            on = i == self.layer_idx
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self.accent if on else "#2a3750"))
            p.drawEllipse(lr.center(), lr.width() / 2 * (1.4 if on else 1.0),
                          lr.width() / 2 * (1.4 if on else 1.0))
            if on:
                p.setBrush(QColor(self.accent))
                p.setOpacity(0.25)
                p.drawEllipse(lr.center(), lr.width() * 1.4, lr.width() * 1.4)
                p.setOpacity(1.0)

    def _paint_key(self, p: QPainter, kid: str, rect: QRectF, layer):
        is_sel = self.sel == ("key", kid)
        is_hover = self._hover == ("key", kid)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, QColor(KEY_TOP if (is_sel or is_hover) else KEY))
        grad.setColorAt(1, QColor(KEY))
        p.fillPath(path, QBrush(grad))

        if is_sel:
            p.setPen(QPen(QColor(self.accent), 2.5))
        else:
            p.setPen(QPen(QColor(BORDER), 1))
        p.drawPath(path)

        binding = layer.binding(kid) if layer else None
        label = binding.display_label() if binding else ""
        action = binding.action if binding else None

        cx, cy = rect.center().x(), rect.center().y()
        if label:
            f = QFont(self.font())
            f.setPointSizeF(max(9.5, rect.height() * 0.16))
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(TEXT))
            combo = action.summary() if action and action.summary() != label else ""
            ty = cy - (6 if combo else -5)
            p.drawText(QRectF(rect.left(), ty - rect.height() * 0.3, rect.width(), rect.height() * 0.36),
                       Qt.AlignHCenter | Qt.AlignBottom, label)
            if combo:
                fm = QFont("DejaVu Sans Mono")
                fm.setPointSizeF(max(7.5, rect.height() * 0.12))
                p.setFont(fm)
                p.setPen(QColor(DIM))
                p.drawText(QRectF(rect.left(), ty + 2, rect.width(), rect.height() * 0.26),
                           Qt.AlignHCenter | Qt.AlignTop, combo)
        else:
            p.setPen(QColor(FAINT))
            f = QFont(self.font())
            f.setPointSizeF(max(8, rect.height() * 0.13))
            p.setFont(f)
            p.drawText(rect, Qt.AlignCenter, "—")

        # key id, top-left
        fi = QFont(self.font())
        fi.setPointSizeF(max(6.5, rect.height() * 0.10))
        p.setFont(fi)
        p.setPen(QColor(FAINT))
        p.drawText(QRectF(rect.left() + 6, rect.top() + 3, 40, 14),
                   Qt.AlignLeft | Qt.AlignTop, kid)

    def _paint_knob(self, p: QPainter, eid: str, rect: QRectF, layer):
        is_sel = self.sel == ("encoder", eid)
        c = rect.center()
        r = rect.width() / 2
        if is_sel:
            p.setPen(QPen(QColor(self.accent), 2.5))
        else:
            p.setPen(QPen(QColor(BORDER), 1.5))
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, QColor(KEY_TOP))
        grad.setColorAt(1, QColor(KEY))
        p.setBrush(QBrush(grad))
        p.drawEllipse(c, r, r)
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawEllipse(c, r * 0.72, r * 0.72)
        # indicator
        pen = QPen(QColor(TEXT), 3)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(c.x(), c.y() - r * 0.62), QPointF(c.x(), c.y() - r * 0.30))

        binding = layer.encoder(eid) if layer else None
        label = (binding.display_label() if binding else "") or eid
        f = QFont(self.font())
        f.setPointSizeF(12)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(TEXT if binding else FAINT))
        p.drawText(QRectF(c.x() - r - 20, rect.bottom() + 6, 2 * r + 40, 20),
                   Qt.AlignHCenter, label)
        if binding and binding.cw:
            fm = QFont("DejaVu Sans Mono")
            fm.setPointSizeF(8.5)
            p.setFont(fm)
            p.setPen(QColor(DIM))
            hint = f"↺ {binding.ccw.summary() if binding.ccw else ''}   {binding.cw.summary()} ↻"
            p.drawText(QRectF(c.x() - r - 30, rect.bottom() + 26, 2 * r + 60, 16),
                       Qt.AlignHCenter, hint.strip())

    # ---------- interaction ----------
    def _hit(self, pos: QPointF) -> tuple[str, str] | None:
        for eid, rect in self._knob_rects.items():
            if rect.adjusted(-6, -6, 6, 26).contains(pos):
                return ("encoder", eid)
        for kid, rect in self._key_rects.items():
            if rect.contains(pos):
                return ("key", kid)
        return None

    def mouseMoveEvent(self, e):
        hit = self._hit(e.position())
        if hit != self._hover:
            self._hover = hit
            self.setCursor(Qt.PointingHandCursor if hit else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, e):
        if hasattr(self, "_layer_btn") and self._layer_btn.contains(e.position()):
            self.layer_cycle.emit((self.layer_idx + 1) % 3)
            return
        hit = self._hit(e.position())
        if hit:
            self.select(*hit)
            self.selected.emit(*hit)

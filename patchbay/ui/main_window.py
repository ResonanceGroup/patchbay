"""Patchbay editor main window."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QColor, QPainter, QIcon
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QSizePolicy, QSplitter,
                               QSplitterHandle, QVBoxLayout, QWidget)

from ..core.profile import ProfileState, load_profiles
from ..core.window_rules import active_window, best_profile
from .binding_editor import BindingEditor
from .keypad_widget import KeypadWidget
from .profile_panel import ProfilePanel
from .theme import ACCENT_DEFAULT, QSS, PANEL, segmented_qss


class GripperHandle(QSplitterHandle):
    """Splitter handle with a raised gripper line; highlights on hover."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._painting = False
        self._hover = False
        self.setMouseTracking(True)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._pressed = True
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        # native drag moves the handle first, then the splitter snaps
        super().mouseMoveEvent(e)
        sp = self.parent()
        if isinstance(sp, SnapSplitter):
            sp._maybe_snap()

    def mouseReleaseEvent(self, e):
        self._pressed = False
        super().mouseReleaseEvent(e)
        sp = self.parent()
        if isinstance(sp, SnapSplitter):
            sp._snapped = None
            sp._maybe_snap()

    def paintEvent(self, e):
        if self._painting:
            return
        self._painting = True
        try:
            p = QPainter(self)
            p.fillRect(self.rect(), QColor("#1e1e1e"))
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            cx, cy = self.width() // 2, self.height() // 2
            if self._hover:
                p.setBrush(QColor("#2a2a2a"))
                p.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4,
                                 3, 3)
            # flat 2px line, same thickness for both splitters
            p.setBrush(QColor("#8a8a8a"))
            if self.orientation() == Qt.Orientation.Vertical:
                p.drawRoundedRect(cx - 18, cy - 1, 36, 2, 1, 1)
            else:
                p.drawRoundedRect(cx - 1, cy - 18, 2, 36, 1, 1)
        finally:
            self._painting = False


class SnapSplitter(QSplitter):
    """QSplitter with gripper handles that snaps to the extremes when the
    drag lands within ~5% of either end."""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(12)
        self._snapped = None
        self._dragging = False

    def createHandle(self):
        return GripperHandle(self.orientation(), self)

    def _extents(self):
        total = sum(self.sizes()) + self.handleWidth()
        horiz = self.orientation() == Qt.Orientation.Horizontal
        w0 = self.widget(0)
        w1 = self.widget(1)
        if self.childrenCollapsible():
            # panels may collapse to nothing, so the snap targets are the
            # true ends of the splitter, not the content minimums
            return total, 0, total - self.handleWidth()
        lo = (w0.minimumSizeHint().width() if horiz
              else w0.minimumSizeHint().height())
        hi = (total - self.handleWidth() -
              (w1.minimumSizeHint().width() if horiz
               else w1.minimumSizeHint().height()))
        return total, lo, hi

    def _maybe_snap(self):
        if len(self.sizes()) != 2:
            return
        total, lo, hi = self._extents()
        if total <= 0 or hi <= lo:
            return
        first = self.sizes()[0]
        # collapsible splitters travel the full range and only snap in the
        # last ~100px; non-collapsible ones snap near their content minimum
        edge = (min(120, int(total * 0.2)) if self.childrenCollapsible()
                else int(total * 0.05))
        target = None
        if first - lo <= edge:
            target = 0
        elif hi - first <= edge:
            target = 1
        # magnetic: while inside the zone keep pinning to the end so the
        # handle stays put as the mouse keeps moving; free outside it
        if target == 0:
            self._snapped = 0
            self.setSizes([lo, total - lo - self.handleWidth()])
        elif target == 1:
            self._snapped = 1
            self.setSizes([hi, total - hi - self.handleWidth()])
        else:
            self._snapped = None

    def _start_drag(self):
        """Begin a synthetic drag from the handle's current position."""
        h = self.handle(1)
        if h is None:
            return
        self._drag_pos = h.pos()
        self._dragging = True
        self._snapped = None

    def _step_drag(self, dx, dy):
        if not self._dragging:
            return
        self._drag_pos += QPoint(dx, dy)
        self.setSizes(self._sizes_for(self._drag_pos))
        self._maybe_snap()

    def _sizes_for(self, pos):
        total = sum(self.sizes()) + self.handleWidth()
        horiz = self.orientation() == Qt.Orientation.Horizontal
        first = (pos.x() if horiz else pos.y())
        first = max(0, min(total - self.handleWidth(), first))
        return [first, total - first - self.handleWidth()]

    def _end_drag(self):
        if not self._dragging:
            return
        self._dragging = False
        self._snapped = None


class MainWindow(QMainWindow):
    def __init__(self, profiles_dir: Path):
        super().__init__()
        self.profiles_dir = profiles_dir
        self.state = ProfileState(profiles_dir / "_state.json")
        self.profiles = load_profiles(profiles_dir)
        self.profile = self.profiles[0] if self.profiles else None
        self.layer_idx = 0

        self.setStyleSheet(QSS)
        self.setWindowTitle("Patchbay")
        self.setWindowIcon(QIcon(str(
            Path(__file__).parent.parent / "assets" / "patchbay.svg")))
        self.setMinimumSize(880, 540)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # ---- header ----
        head = QHBoxLayout()
        brand = QLabel("Patchbay")
        brand.setObjectName("brand")
        head.addWidget(brand)
        head.addSpacing(16)

        head.addStretch(1)

        self.layer_btns: list[QPushButton] = []
        for i in range(3):
            b = QPushButton(f"L{i + 1}")
            b.setCheckable(True)
            b.setStyleSheet(segmented_qss(self.accent()))
            b.clicked.connect(lambda _, idx=i: self._layer_changed(idx))
            self.layer_btns.append(b)
            head.addWidget(b)
        self.layer_btns[0].setChecked(True)
        root.addLayout(head)

        # ---- body: panel left, keypad right (draggable divider) ----
        body = QHBoxLayout()
        body.setSpacing(14)

        self.editor = BindingEditor(self.accent())
        self.editor.binding_changed.connect(self._binding_changed)
        self.editor.control_selected.connect(self.select)

        self.profile_panel = ProfilePanel(self)
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(12)
        self.left_split = SnapSplitter(Qt.Orientation.Vertical)
        self.left_split.addWidget(self.profile_panel)
        self.left_split.addWidget(self.editor)
        self.left_split.setStretchFactor(0, 0)
        self.left_split.setStretchFactor(1, 1)
        self.left_split.setCollapsible(0, True)
        self.left_split.setCollapsible(1, True)
        self.left_split.setChildrenCollapsible(True)
        # let both panels shrink gradually (not jump at their content min) so
        # the snap, not QSplitter's native collapse, decides where it closes
        for _wdg in (self.profile_panel, self.editor):
            _sp = _wdg.sizePolicy()
            _sp.setVerticalPolicy(QSizePolicy.Policy.Ignored)
            _wdg.setSizePolicy(_sp)
            _wdg.setMinimumHeight(0)
        self.left_split.setSizes([220, 480])
        left_lay.addWidget(self.left_split, 1)
        left_w.setMinimumWidth(240)

        self.keypad = KeypadWidget()
        self.keypad.setMaximumWidth(640)
        self.keypad.selected.connect(self._selected)
        kp_host = QWidget()
        kp_lay = QHBoxLayout(kp_host)
        kp_lay.setContentsMargins(0, 0, 0, 0)
        kp_lay.addStretch(1)
        kp_v = QVBoxLayout()
        kp_v.setContentsMargins(0, 0, 0, 0)
        kp_v.addStretch(1)
        kp_v.addWidget(self.keypad)
        kp_v.addStretch(1)
        kp_lay.addLayout(kp_v)
        kp_lay.addStretch(1)

        self.body_split = SnapSplitter(Qt.Orientation.Horizontal)
        self.body_split.addWidget(left_w)
        self.body_split.addWidget(kp_host)
        self.body_split.setStretchFactor(0, 0)
        self.body_split.setStretchFactor(1, 1)
        self.body_split.setCollapsible(0, False)
        self.body_split.setCollapsible(1, False)
        self.body_split.setChildrenCollapsible(False)
        self.body_split.setSizes([340, 700])
        body.addWidget(self.body_split, 1)
        root.addLayout(body, 1)

        # ---- status ----
        self.status = QLabel("")
        self.status.setObjectName("statusbar")
        root.addWidget(self.status)

        if self.profile:
            self._load_profile()

        # ---- auto-switch: watch the focused window ----
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(700)
        self._watch_timer.timeout.connect(self._check_focus)
        if self.state.auto_switch:
            self._watch_timer.start()

    def set_auto_switch(self, on: bool):
        if on:
            self._watch_timer.start()
        else:
            self._watch_timer.stop()

    def _check_focus(self):
        if not self.isVisible():
            return
        win = active_window()
        if win is None:
            return
        cls, title = win
        pr = best_profile(self.profiles, cls, title)
        if pr is not None and pr is not self.profile:
            self.select_profile(pr, from_auto=True)

    def select_profile(self, pr, from_list=False, from_auto=False):
        if pr.path is None or pr not in self.profiles:
            return
        self.profile = pr
        self.state.set_last_profile(pr.app, pr.name)
        self.editor.clear()
        self.keypad.sel = None
        self._load_profile()
        if not from_list:
            self.profile_panel.refresh()

    def accent(self) -> str:
        return self.profile.accent if self.profile else ACCENT_DEFAULT

    def _load_profile(self):
        self.keypad.set_accent(self.accent())
        self.keypad.set_profile(self.profile, self.layer_idx)
        self.editor.set_accent(self.accent())
        for b in self.layer_btns:
            b.setStyleSheet(segmented_qss(self.accent()))
        self.status.setText(
            f"profile: {self.profile.name}   ·   app: {self.profile.app}")

    def reload_profiles(self, select: str | None = None):
        cur_path = self.profile.path if self.profile else None
        self.profiles = load_profiles(self.profiles_dir)
        target = None
        if select:
            for pr in self.profiles:
                if pr.name == select:
                    target = pr
                    break
        if target is None:
            for pr in self.profiles:
                if pr.path == cur_path:
                    target = pr
                    break
        if target is None:
            target = self.profiles[0] if self.profiles else None
        self.profile = target
        self.editor.clear()
        self.keypad.sel = None
        if self.profile:
            self._load_profile()
        self.profile_panel.refresh()

    def _layer_changed(self, idx):
        self.layer_idx = idx
        for i, b in enumerate(self.layer_btns):
            b.setChecked(i == idx)
        self.keypad.layer_idx = idx
        self.keypad.refresh()
        self._reedit()

    def _selected(self, kind, ident):
        layer = self.profile.layer(self.layer_idx)
        if kind == "key":
            self.editor.show_key(ident, layer.binding(ident))
        else:
            self.editor.show_encoder(ident, layer.encoder(ident))

    def _reedit(self):
        if self.keypad.sel:
            self._selected(*self.keypad.sel)

    def _binding_changed(self):
        binding = self.editor._binding_ref
        binding.label = self.editor.current_label()
        self.keypad.refresh()
        self._save()

    def _save(self):
        self.profile.save()
        self.status.setText(
            f"profile: {self.profile.name}   ·   saved {self.profile.path.name}")

    # screenshot helper
    def select(self, spec: str):
        kind, ident = spec.split(":")
        self.keypad.select(kind, ident)
        self._selected(kind, ident)

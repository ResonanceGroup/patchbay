"""Patchbay editor main window."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QVBoxLayout, QWidget)

from ..core.profile import load_profiles
from .binding_editor import BindingEditor
from .keypad_widget import KeypadWidget
from .theme import ACCENT_DEFAULT, QSS, PANEL, segmented_qss


class MainWindow(QMainWindow):
    def __init__(self, profiles_dir: Path):
        super().__init__()
        self.profiles_dir = profiles_dir
        self.profiles = load_profiles(profiles_dir)
        self.profile = self.profiles[0] if self.profiles else None
        self.layer_idx = 0

        self.setStyleSheet(QSS)
        self.setWindowTitle("Patchbay")
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

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(180)
        for pr in self.profiles:
            self.profile_combo.addItem(pr.app)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        head.addWidget(self.profile_combo)

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

        # ---- body: panel left, keypad right ----
        body = QHBoxLayout()
        body.setSpacing(14)

        self.editor = BindingEditor(self.accent())
        self.editor.setFixedWidth(340)
        self.editor.binding_changed.connect(self._binding_changed)
        body.addWidget(self.editor, 0)

        self.keypad = KeypadWidget()
        self.keypad.setMaximumWidth(560)
        self.keypad.selected.connect(self._selected)
        kp_host = QHBoxLayout()
        kp_host.setContentsMargins(0, 0, 0, 0)
        kp_host.addStretch(1)
        kp_host.addWidget(self.keypad)
        kp_host.addStretch(1)
        body.addLayout(kp_host, 3)
        root.addLayout(body, 1)

        # ---- status ----
        self.status = QLabel("")
        self.status.setObjectName("statusbar")
        root.addWidget(self.status)

        if self.profile:
            self._load_profile()

    def accent(self) -> str:
        return self.profile.accent if self.profile else ACCENT_DEFAULT

    def _load_profile(self):
        self.keypad.set_accent(self.accent())
        self.keypad.set_profile(self.profile, self.layer_idx)
        self.editor.set_accent(self.accent())
        for b in self.layer_btns:
            b.setStyleSheet(segmented_qss(self.accent()))
        self.status.setText(f"profile: {self.profile.app}   ·   file: {self.profile.path.name}")

    def _profile_changed(self, idx):
        self.profile = self.profiles[idx]
        self.editor.clear()
        self.keypad.sel = None
        self._load_profile()

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
            f"profile: {self.profile.app}   ·   saved {self.profile.path.name}")

    # screenshot helper
    def select(self, spec: str):
        kind, ident = spec.split(":")
        self.keypad.select(kind, ident)
        self._selected(kind, ident)

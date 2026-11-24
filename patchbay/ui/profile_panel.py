"""Profile manager panel: pick the profile for an application, and
add / remove / rename profiles."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout)

from ..core.profile import Profile


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


class ProfilePanel(QFrame):
    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.win = win

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        title = QLabel("Profiles")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        lay.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.combo = QComboBox()
        self.combo.setMinimumWidth(140)
        self.combo.currentIndexChanged.connect(self._combo_changed)
        row.addWidget(self.combo, 1)
        for text, tip, slot in (("+", "Add profile", self._add),
                                ("–", "Remove profile", self._remove),
                                ("ren", "Rename profile", self._rename)):
            b = QPushButton(text)
            b.setFixedWidth(34)
            b.setStyleSheet("padding: 5px 0;")
            b.setToolTip(tip)
            b.clicked.connect(slot)
            row.addWidget(b)
        lay.addLayout(row)

        app_row = QHBoxLayout()
        app_row.setSpacing(6)
        lbl = QLabel("Application")
        lbl.setObjectName("dim")
        app_row.addWidget(lbl)
        self.app_edit = QLineEdit()
        self.app_edit.setPlaceholderText("window class / app to match")
        self.app_edit.textEdited.connect(self._app_edited)
        app_row.addWidget(self.app_edit, 1)
        lay.addLayout(app_row)

        self.refresh()

    def refresh(self):
        cur = self.win.profile.app if self.win.profile else None
        self.combo.blockSignals(True)
        self.combo.clear()
        for pr in self.win.profiles:
            self.combo.addItem(pr.app)
        if cur:
            i = self.combo.findText(cur)
            self.combo.setCurrentIndex(max(0, i))
        self.combo.blockSignals(False)
        self.app_edit.setText(
            " ".join(self.win.profile.match.get("wm_class", []))
            if self.win.profile else "")

    def _combo_changed(self, idx):
        if idx >= 0:
            self.win._profile_changed(idx)

    def _add(self):
        name, ok = QInputDialog.getText(self, "Add profile",
                                        "Application name:")
        if not ok or not name.strip():
            return
        p = Profile(app=name.strip())
        p.save(self.win.profiles_dir / f"{_slug(name)}.json")
        self.win.reload_profiles(select=name.strip())

    def _remove(self):
        pr = self.win.profile
        if pr is None:
            return
        if len(self.win.profiles) <= 1:
            self.win.status.setText("can't remove the last profile")
            return
        if QMessageBox.question(
                self, "Remove profile",
                f"Delete profile '{pr.app}' and its file {pr.path.name}?") \
                != QMessageBox.Yes:
            return
        pr.path.unlink(missing_ok=True)
        self.win.reload_profiles()

    def _rename(self):
        pr = self.win.profile
        if pr is None:
            return
        name, ok = QInputDialog.getText(self, "Rename profile",
                                        "New name:", text=pr.app)
        if not ok or not name.strip() or name.strip() == pr.app:
            return
        old_path = pr.path
        pr.app = name.strip()
        new_path = self.win.profiles_dir / f"{_slug(name)}.json"
        pr.save(new_path)
        if old_path and old_path != new_path:
            old_path.unlink(missing_ok=True)
        self.win.reload_profiles(select=pr.app)

    def _app_edited(self):
        pr = self.win.profile
        if pr is None:
            return
        words = self.app_edit.text().split()
        if words:
            pr.match = {"wm_class": words}
        else:
            pr.match = {}
        self.win._save()

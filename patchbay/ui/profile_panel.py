"""Profile manager: application dropdown + gear, toolbar, profile list.

Two levels: an application groups one or more profiles (e.g. KiCad →
PCB editor / Schematic editor). Selecting a row switches the keypad.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame,
                               QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QVBoxLayout)

from ..core.profile import Profile, app_groups
from ..core.window_rules import list_windows


class _AppCombo(QComboBox):
    """Application dropdown matching the grid combo look."""
    pass


class ProfilePanel(QFrame):
    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.win = win

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        # ---- application row ----
        arow = QHBoxLayout()
        arow.setSpacing(6)
        albl = QLabel("Application")
        albl.setObjectName("dim")
        arow.addWidget(albl)
        self.app_combo = _AppCombo()
        self.app_combo.setMinimumWidth(140)
        self.app_combo.currentIndexChanged.connect(self._app_changed)
        arow.addWidget(self.app_combo, 1)
        self.gear = QPushButton("⚙")
        self.gear.setFixedWidth(34)
        self.gear.setToolTip("Settings")
        self.gear.clicked.connect(self._settings)
        arow.addWidget(self.gear)
        lay.addLayout(arow)

        # ---- toolbar ----
        trow = QHBoxLayout()
        trow.setSpacing(6)
        for text, tip, slot in (("+", "Add profile", self._add),
                                ("⧉", "Duplicate profile", self._duplicate),
                                ("ren", "Rename profile", self._rename),
                                ("–", "Remove profile", self._remove)):
            b = QPushButton(text)
            b.setFixedWidth(34)
            b.setStyleSheet("padding: 5px 0;")
            b.setToolTip(tip)
            b.clicked.connect(slot)
            trow.addWidget(b)
        trow.addStretch(1)
        lay.addLayout(trow)

        # ---- profile list ----
        self.list = QListWidget()
        self.list.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.list.currentRowChanged.connect(self._row_changed)
        lay.addWidget(self.list, 1)

        self._loading = False
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self):
        self._loading = True
        cur_app = self.win.profile.app if self.win.profile else None
        cur_path = self.win.profile.path if self.win.profile else None

        self.app_combo.blockSignals(True)
        self.app_combo.clear()
        for app in app_groups(self.win.profiles):
            self.app_combo.addItem(app)
        if cur_app:
            i = self.app_combo.findText(cur_app)
            self.app_combo.setCurrentIndex(max(0, i))
        self.app_combo.blockSignals(False)

        self._fill_list(cur_app, cur_path)
        self._loading = False

    def _fill_list(self, app: str | None, select_path=None):
        self.list.blockSignals(True)
        self.list.clear()
        sel = -1
        for i, pr in enumerate(self.win.profiles):
            if app and pr.app != app:
                continue
            item = QListWidgetItem(pr.name or pr.app)
            item.setData(Qt.ItemDataRole.UserRole, i)
            rules = pr.match or {}
            tips = []
            if rules.get("wm_class"):
                tips.append("class: " + ", ".join(rules["wm_class"]))
            if rules.get("title"):
                tips.append("title: " + " + ".join(rules["title"]))
            if tips:
                item.setToolTip("  ·  ".join(tips))
            self.list.addItem(item)
            if select_path and pr.path == select_path:
                sel = self.list.count() - 1
        if sel < 0 and self.list.count():
            sel = 0
        self.list.setCurrentRow(sel)
        self.list.blockSignals(False)

    def _profiles_for_app(self, app: str) -> list[Profile]:
        return [pr for pr in self.win.profiles if pr.app == app]

    # ------------------------------------------------------------------
    def _app_changed(self, idx):
        if self._loading or idx < 0:
            return
        app = self.app_combo.itemText(idx)
        # per-app memory: land on the last profile used for this app
        want = self.win.state.last_profile(app)
        target = None
        for pr in self._profiles_for_app(app):
            if pr.name == want:
                target = pr
                break
        if target is None:
            target = self._profiles_for_app(app)[0]
        self.win.select_profile(target)

    def _row_changed(self, row):
        if self._loading or row < 0:
            return
        item = self.list.item(row)
        pr = self.win.profiles[item.data(Qt.ItemDataRole.UserRole)]
        self.win.select_profile(pr, from_list=True)

    # ------------------------------------------------------------------
    def _add(self):
        app = self.app_combo.currentText() or "General"
        name, ok = QInputDialog.getText(
            self, "Add profile", f"Profile name (app: {app}):",
            text=f"{app} 2")
        if not ok or not name.strip():
            return
        p = Profile(app=app, name=name.strip(), match={})
        p.save(self.win.profiles_dir / f"{_slug(name)}.json")
        self.win.reload_profiles(select=name.strip())

    def _duplicate(self):
        pr = self.win.profile
        if pr is None:
            return
        name, ok = QInputDialog.getText(
            self, "Duplicate profile", "New profile name:",
            text=f"{pr.name} copy")
        if not ok or not name.strip():
            return
        import copy
        p = copy.deepcopy(pr)
        p.name = name.strip()
        p.path = None
        p.save(self.win.profiles_dir / f"{_slug(name)}.json")
        self.win.reload_profiles(select=name.strip())

    def _rename(self):
        pr = self.win.profile
        if pr is None:
            return
        name, ok = QInputDialog.getText(self, "Rename profile",
                                        "New name:", text=pr.name)
        if not ok or not name.strip() or name.strip() == pr.name:
            return
        old_path = pr.path
        pr.name = name.strip()
        new_path = self.win.profiles_dir / f"{_slug(name)}.json"
        pr.save(new_path)
        if old_path and old_path != new_path:
            old_path.unlink(missing_ok=True)
        self.win.reload_profiles(select=pr.name)

    def _remove(self):
        pr = self.win.profile
        if pr is None:
            return
        if len(self.win.profiles) <= 1:
            self.win.status.setText("can't remove the last profile")
            return
        if QMessageBox.question(
                self, "Remove profile",
                f"Delete profile '{pr.name}' and its file {pr.path.name}?") \
                != QMessageBox.Yes:
            return
        pr.path.unlink(missing_ok=True)
        self.win.reload_profiles()

    def _settings(self):
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.win, parent=self)
        dlg.exec()


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")

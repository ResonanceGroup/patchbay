"""Settings dialog: auto-switch toggle, and per-profile window match
rules built by picking real windows — no regex, no typing of patterns."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..core.profile import (app_groups, create_app, delete_app, rename_app)
from ..core.window_rules import list_windows


class SettingsDialog(QDialog):
    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # ---- global: auto-switch ----
        self.auto = QCheckBox("Auto-switch profile with the focused window")
        self.auto.setChecked(self.win.state.auto_switch)
        self.auto.toggled.connect(self._auto_toggled)
        lay.addWidget(self.auto)

        # ---- current profile rules ----
        box = QFrame()
        box.setObjectName("panel")
        bl = QVBoxLayout(box)
        bl.setSpacing(6)

        head = QHBoxLayout()
        title = QLabel("Window rules")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        head.addWidget(title)
        head.addStretch(1)
        self.profile_lbl = QLabel("")
        self.profile_lbl.setObjectName("dim")
        head.addWidget(self.profile_lbl)
        bl.addLayout(head)

        self.class_lbl = QLabel("(no application rule)")
        self.class_lbl.setObjectName("dim")
        bl.addWidget(self.class_lbl)
        self.title_lbl = QLabel("(no title rule)")
        self.title_lbl.setObjectName("dim")
        bl.addWidget(self.title_lbl)

        prow = QHBoxLayout()
        self.pick_btn = QPushButton("Pick window…")
        self.pick_btn.clicked.connect(self._pick_window)
        prow.addWidget(self.pick_btn)
        self.clear_title_btn = QPushButton("Clear title rule")
        self.clear_title_btn.clicked.connect(self._clear_title)
        prow.addWidget(self.clear_title_btn)
        self.edit_title_btn = QPushButton("Edit title words…")
        self.edit_title_btn.clicked.connect(self._edit_title)
        prow.addWidget(self.edit_title_btn)
        prow.addStretch(1)
        bl.addLayout(prow)
        lay.addWidget(box)

        # ---- applications CRUD ----
        abox = QFrame()
        abox.setObjectName("panel")
        al = QVBoxLayout(abox)
        al.setSpacing(6)

        ahead = QHBoxLayout()
        atitle = QLabel("Applications")
        atitle.setStyleSheet("font-weight: 700; font-size: 14px;")
        ahead.addWidget(atitle)
        ahead.addStretch(1)
        al.addLayout(ahead)

        self.app_list = QListWidget()
        self.app_list.setStyleSheet(
            "QListWidget { background: #252526; border: 1px solid #3f3f46;"
            " border-radius: 2px; outline: 0; }"
            "QListWidget::item { padding: 4px 6px; }"
            "QListWidget::item:selected { background: #007acc; color: #fff; }")
        self.app_list.setMaximumHeight(140)
        al.addWidget(self.app_list, 1)

        arow = QHBoxLayout()
        arow.setSpacing(6)
        self.add_app_btn = QPushButton("Add")
        self.add_app_btn.clicked.connect(self._add_app)
        arow.addWidget(self.add_app_btn)
        self.rename_app_btn = QPushButton("Rename")
        self.rename_app_btn.clicked.connect(self._rename_app)
        arow.addWidget(self.rename_app_btn)
        self.delete_app_btn = QPushButton("Delete")
        self.delete_app_btn.clicked.connect(self._delete_app)
        arow.addWidget(self.delete_app_btn)
        arow.addStretch(1)
        al.addLayout(arow)
        lay.addWidget(abox)

        ahint = QLabel("An application groups one or more profiles. Add one to "
                       "start mapping a new program; Rename and Delete apply to "
                       "every profile under it.")
        ahint.setObjectName("faint")
        ahint.setWordWrap(True)
        lay.addWidget(ahint)

        hint = QLabel("Rules are built by picking real windows. Title words "
                      "are plain words that must all appear in the window "
                      "title.")
        hint.setObjectName("faint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)

        self._show_rules()
        self._refresh_apps()

    # ------------------------------------------------------------------
    def _auto_toggled(self, on):
        self.win.state.auto_switch = on
        self.win.set_auto_switch(on)

    def _show_rules(self):
        pr = self.win.profile
        if pr is None:
            return
        self.profile_lbl.setText(pr.name)
        m = pr.match or {}
        cls = m.get("wm_class") or []
        self.class_lbl.setText(
            "application: " + ", ".join(cls) if cls
            else "(no application rule)")
        words = m.get("title") or []
        self.title_lbl.setText(
            "title contains: " + " + ".join(words) if words
            else "(no title rule)")

    def _pick_window(self):
        wins = list_windows()
        dlg = _WindowPicker(wins, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.chosen is None:
            return
        wid, cls, title = dlg.chosen
        pr = self.win.profile
        if pr is None:
            return
        # class: take the second WM_CLASS token (the class name)
        tokens = [t.strip('"') for t in cls.split() if t.strip('",')]
        pick = tokens[-1].lower() if tokens else ""
        pr.match = dict(pr.match or {})
        if pick:
            pr.match["wm_class"] = [pick]
        # title: suggest the longest two words as plain substrings
        words = [w for w in title.split() if len(w) >= 4]
        words.sort(key=len, reverse=True)
        pr.match["title"] = words[:2]
        pr.save()
        self._show_rules()

    # ------------------------------------------------------------------
    # applications CRUD
    def _refresh_apps(self, select: str | None = None):
        self.app_list.blockSignals(True)
        self.app_list.clear()
        apps = app_groups(self.win.profiles)
        sel = -1
        for i, a in enumerate(apps):
            self.app_list.addItem(a)
            if select and a == select:
                sel = i
        if sel < 0 and self.win.profile:
            cur = self.win.profile.app
            for i, a in enumerate(apps):
                if a == cur:
                    sel = i
                    break
        if sel >= 0:
            self.app_list.setCurrentRow(sel)
        self.app_list.blockSignals(False)

    def _selected_app(self) -> str | None:
        it = self.app_list.currentItem()
        return it.text() if it else None

    def _add_app(self):
        name, ok = QInputDialog.getText(
            self, "New application", "Application name:")
        if not ok or not name.strip():
            return
        try:
            create_app(self.win.profiles_dir, name.strip())
        except FileExistsError:
            QMessageBox.warning(
                self, "Exists",
                f"An application named '{name.strip()}' already exists.")
            return
        self.win.reload_profiles(select=name.strip())
        self._refresh_apps(select=name.strip())
        self._show_rules()

    def _rename_app(self):
        old = self._selected_app()
        if not old:
            return
        new, ok = QInputDialog.getText(
            self, "Rename application", "New name:", text=old)
        if not ok or not new.strip() or new.strip() == old:
            return
        try:
            rename_app(self.win.profiles_dir, self.win.profiles, old, new.strip())
        except FileExistsError:
            QMessageBox.warning(
                self, "Exists",
                f"An application named '{new.strip()}' already exists.")
            return
        self.win.reload_profiles(select=new.strip())
        self._refresh_apps(select=new.strip())
        self._show_rules()

    def _delete_app(self):
        app = self._selected_app()
        if not app:
            return
        if len(app_groups(self.win.profiles)) <= 1:
            QMessageBox.information(
                self, "Can't delete", "This is the only application.")
            return
        if QMessageBox.question(
                self, "Delete application",
                f"Delete '{app}' and all of its profiles?") \
                != QMessageBox.Yes:
            return
        delete_app(self.win.profiles_dir, self.win.profiles, app)
        self.win.reload_profiles()
        self._refresh_apps()
        self._show_rules()

    def _clear_title(self):
        pr = self.win.profile
        if pr is None:
            return
        pr.match = dict(pr.match or {})
        pr.match.pop("title", None)
        pr.save()
        self._show_rules()

    def _edit_title(self):
        pr = self.win.profile
        if pr is None:
            return
        cur = " ".join((pr.match or {}).get("title", []))
        txt, ok = QInputDialog.getText(
            self, "Title words",
            "Words that must all appear in the window title:", text=cur)
        if not ok:
            return
        words = txt.split()
        pr.match = dict(pr.match or {})
        if words:
            pr.match["title"] = words
        else:
            pr.match.pop("title", None)
        pr.save()
        self._show_rules()


class _WindowPicker(QDialog):
    """List of open windows; click one to choose it."""

    def __init__(self, wins, parent=None):
        super().__init__(parent)
        self.wins = wins
        self.chosen = None
        self.setWindowTitle("Pick a window")
        self.setMinimumSize(420, 320)

        lay = QVBoxLayout(self)
        lbl = QLabel("Pick the window this profile should match:")
        lay.addWidget(lbl)
        self.list = QListWidget()
        for wid, cls, title in wins:
            item = QListWidgetItem(title or "(untitled)")
            item.setData(Qt.ItemDataRole.UserRole, (wid, cls, title))
            if cls:
                item.setToolTip(f"class: {cls}")
            self.list.addItem(item)
        self.list.itemDoubleClicked.connect(self._choose)
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton("Use this window")
        ok.clicked.connect(self._ok)
        row.addWidget(ok)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        lay.addLayout(row)

    def _ok(self):
        item = self.list.currentItem()
        if item is None:
            self.reject()
            return
        self.chosen = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _choose(self, item):
        self.list.setCurrentItem(item)
        self._ok()

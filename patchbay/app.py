"""Patchbay tray: an AppIndicator in the GNOME top bar that supervises the
pad daemon and opens the editor.

GNOME (with the ubuntu-appindicators extension) only shows StatusNotifierItem /
AppIndicator icons, not Qt's legacy XEmbed tray — so this tray is a native
Ayatana AppIndicator and runs under the SYSTEM python3 (which has GObject
introspection). It launches the daemon and the editor as separate processes
using the project venv, so the tray itself needs no evdev/Qt.

    python3 patchbay/app.py [--pin KiCad]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, AyatanaAppIndicator3 as AppIndicator3  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
VENV_PY = REPO / ".venv" / "bin" / "python"
PROFILES = REPO / "profiles"
ASSETS = REPO / "patchbay" / "assets"


class Tray:
    def __init__(self, pin: str | None) -> None:
        self.pin = pin
        self.daemon: subprocess.Popen | None = None
        self.ui: subprocess.Popen | None = None
        self.start_daemon()

        self.ind = AppIndicator3.Indicator.new(
            "patchbay", "patchbay",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.ind.set_icon_theme_path(str(ASSETS))
        self.ind.set_icon_full("patchbay", "Patchbay")  # finds patchbay.svg
        self.ind.set_menu(self._menu())

    # --- subprocess supervision -------------------------------------------
    def _spawn(self, module: str, *extra: str) -> subprocess.Popen:
        args = [str(VENV_PY), "-m", module, "--profiles", str(PROFILES)]
        if self.pin:
            args += [extra[0], self.pin] if extra else []
        return subprocess.Popen(args, cwd=str(REPO))

    def start_daemon(self) -> None:
        if self.daemon is not None and self.daemon.poll() is None:
            return
        self.daemon = self._spawn("patchbay.daemon", "--pin")

    def restart_daemon(self, *_a) -> None:
        if self.daemon is not None and self.daemon.poll() is None:
            self.daemon.terminate()
        self.start_daemon()

    def open_ui(self, *_a) -> None:
        if self.ui is not None and self.ui.poll() is None:
            return
        self.ui = self._spawn("patchbay.ui", "--profile")

    def quit(self, *_a) -> None:
        for p in (self.daemon, self.ui):
            if p is not None and p.poll() is None:
                p.terminate()
        Gtk.main_quit()

    # --- menu --------------------------------------------------------------
    def _menu(self) -> Gtk.Menu:
        m = Gtk.Menu()
        for label, cb in (("Open Patchbay", self.open_ui),
                          ("Restart pad", self.restart_daemon)):
            it = Gtk.MenuItem.new_with_label(label)
            it.connect("activate", cb)
            m.append(it)
        m.append(Gtk.SeparatorMenuItem())
        it = Gtk.MenuItem.new_with_label("Quit")
        it.connect("activate", self.quit)
        m.append(it)
        m.show_all()
        return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="patchbay-tray")
    ap.add_argument("--pin", default=None, help="pin a profile by name/app")
    args = ap.parse_args(argv)
    Tray(args.pin)
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

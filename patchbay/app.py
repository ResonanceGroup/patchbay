"""Patchbay tray: an AppIndicator in the GNOME top bar that supervises the
pad daemon and opens the editor.

GNOME (with the ubuntu-appindicators extension) only shows StatusNotifierItem /
AppIndicator icons, not Qt's legacy XEmbed tray — so this tray is a native
Ayatana AppIndicator and runs under the SYSTEM python3 (which has GObject
introspection). It launches the daemon and the editor as separate processes
using the project venv, so the tray itself needs no evdev/Qt.

Single-instance via Gtk.Application: launching again (e.g. from the launcher)
does not start a second tray — it activates the running one, which brings the
editor to the front.

    python3 patchbay/app.py [--pin KiCad] [--tray-only]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, Gio, AyatanaAppIndicator3 as AppIndicator3  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
VENV_PY = REPO / ".venv" / "bin" / "python"
PROFILES = REPO / "profiles"
ASSETS = REPO / "patchbay" / "assets"


class PatchbayApp(Gtk.Application):
    def __init__(self, pin: str | None, tray_only: bool) -> None:
        super().__init__(
            application_id="com.resonancegroup.Patchbay",
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.pin = pin
        self.tray_only = tray_only
        self.daemon: subprocess.Popen | None = None
        self.ui: subprocess.Popen | None = None
        self.ind: AppIndicator3.Indicator | None = None
        self._activated_once = False

    # ---- lifecycle --------------------------------------------------------
    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        # A tray has no windows; without an explicit hold GApplication would
        # quit as soon as startup/activate finish.
        self.hold()
        self.start_daemon()
        self.ind = AppIndicator3.Indicator.new(
            "patchbay", "patchbay-tray",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.ind.set_icon_theme_path(str(ASSETS))
        self.ind.set_icon_full("patchbay-tray", "Patchbay")
        self.ind.set_menu(self._menu())

    def do_activate(self) -> None:
        # First activate happens at our own launch; autostart passes
        # --tray-only so login shows only the tray, not the editor. Any later
        # activate (a launcher click) opens / raises the editor.
        first = not self._activated_once
        self._activated_once = True
        if first and self.tray_only:
            return
        self.open_ui()

    # ---- subprocess supervision -------------------------------------------
    def _spawn(self, module: str, flag: str) -> subprocess.Popen:
        args = [str(VENV_PY), "-m", module, "--profiles", str(PROFILES)]
        if self.pin:
            args += [flag, self.pin]
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
            self._raise_ui()
            return
        self.ui = self._spawn("patchbay.ui", "--profile")

    def _raise_ui(self) -> None:
        # Bring the existing editor to the front / un-minimize it.
        try:
            subprocess.run(
                ["xdotool", "search", "--name", "^Patchbay$",
                 "windowactivate", "--sync"],
                check=False, timeout=5)
        except Exception:
            pass

    def quit(self, *_a) -> None:
        for p in (self.daemon, self.ui):
            if p is not None and p.poll() is None:
                p.terminate()
        if self.ind is not None:
            self.ind.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
        self.release()
        self.quit_application()

    # ---- menu -------------------------------------------------------------
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
    ap.add_argument("--tray-only", action="store_true",
                    help="start tray + daemon without opening the editor "
                         "(used by autostart)")
    args = ap.parse_args(argv)
    app = PatchbayApp(args.pin, args.tray_only)
    # GApplication parses its own argv; hand it only the program name so our
    # --pin/--tray-only flags aren't mistaken for GApplication options.
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())

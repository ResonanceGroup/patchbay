"""Launch the Patchbay editor:  python -m patchbay.ui"""
import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow

PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"


def main():
    ap = argparse.ArgumentParser(prog="patchbay")
    ap.add_argument("--profiles", default=str(PROFILES_DIR))
    ap.add_argument("--screenshot", help="render one frame to this PNG and exit")
    ap.add_argument("--select", help="preselect a control, e.g. key:K03 or encoder:E1")
    ap.add_argument("--profile", help="profile app name to show")
    ap.add_argument("--layer", type=int, default=0)
    ap.add_argument("--size", help="window size WxH, e.g. 900x560")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("Patchbay")
    app.setDesktopFileName("patchbay")
    w = MainWindow(Path(args.profiles))
    if args.size:
        ww, hh = map(int, args.size.lower().split("x"))
        w.resize(ww, hh)
    else:
        w.resize(1180, 800)
    if args.profile:
        for pr in w.profiles:
            if pr.app == args.profile or pr.name == args.profile:
                w.select_profile(pr)
                break
    w._layer_changed(args.layer)
    w.show()
    if args.screenshot:
        if args.select:
            w.select(args.select)
        app.processEvents()
        w.grab().save(args.screenshot)
    else:
        sys.exit(app.exec())


if __name__ == "__main__":
    main()

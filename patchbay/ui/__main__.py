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
    w = MainWindow(Path(args.profiles))
    if args.size:
        ww, hh = map(int, args.size.lower().split("x"))
        w.resize(ww, hh)
    else:
        w.resize(1180, 800)
    if args.profile:
        for i, pr in enumerate(w.profiles):
            if pr.app == args.profile:
                w.profile_combo.setCurrentIndex(i)
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

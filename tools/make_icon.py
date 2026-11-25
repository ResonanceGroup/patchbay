"""Render patchbay/assets/patchbay.svg into PNGs for the tray icon and desktop
entry. The SVG is the single source of truth.

    python tools/make_icon.py
"""
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt

ASSETS = Path(__file__).resolve().parents[1] / "patchbay" / "assets"
SVG = ASSETS / "patchbay.svg"
SIZES = (16, 22, 24, 32, 48, 64, 128, 256)


def render(size: int) -> QImage:
    r = QSvgRenderer(str(SVG))
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    r.render(p)
    p.end()
    return img


def main() -> None:
    app = QGuiApplication([])
    for size in SIZES:
        render(size).save(str(ASSETS / f"patchbay-{size}.png"))
    render(256).save(str(ASSETS / "patchbay.png"))
    print("wrote", ", ".join(f"patchbay-{s}.png" for s in SIZES),
          "+ patchbay.png to", ASSETS)


if __name__ == "__main__":
    main()

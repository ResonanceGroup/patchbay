"""Render patchbay/assets/patchbay.svg into PNGs for the tray icon and desktop
entry. The SVG is the single source of truth.

    python tools/make_icon.py
"""
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt

ASSETS = Path(__file__).resolve().parents[1] / "patchbay" / "assets"
SIZES = (16, 22, 24, 32, 48, 64, 128, 256)
SOURCES = ("patchbay", "patchbay-tray")  # dark (window) + light (tray/launcher)


def render(svg: Path, size: int) -> QImage:
    r = QSvgRenderer(str(svg))
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    r.render(p)
    p.end()
    return img


def main() -> None:
    app = QGuiApplication([])
    for name in SOURCES:
        svg = ASSETS / f"{name}.svg"
        for size in SIZES:
            render(svg, size).save(str(ASSETS / f"{name}-{size}.png"))
        render(svg, 256).save(str(ASSETS / f"{name}.png"))
    print("rendered", ", ".join(SOURCES), "PNGs to", ASSETS)


if __name__ == "__main__":
    main()

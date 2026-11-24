"""Dark theme tokens + QSS — VS Code Dark+ palette. Accent comes from the active profile."""
from pathlib import Path

_ASSETS = str(Path(__file__).parent / "assets")

# VS Code Dark+
BG = "#1e1e1e"
PANEL = "#252526"
CARD = "#2d2d30"
KEY = "#2d2d30"
KEY_HOVER = "#38383c"
KEY_SEL = "#33333a"
BORDER = "#3f3f46"
TEXT = "#d4d4d4"
DIM = "#9d9d9d"
FAINT = "#6e6e6e"
ACCENT_DEFAULT = "#007acc"
STATUS_BG = "#007acc"

MONO = "Consolas, DejaVu Sans Mono"

QSS = f"""
QMainWindow, QWidget {{ background: {BG}; color: {TEXT};
    font-family: 'Segoe UI', 'DejaVu Sans', sans-serif; font-size: 14px; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}
QLabel#brand {{ font-size: 19px; font-weight: 700; }}
QLabel#dim {{ color: {DIM}; }}
QLabel#faint {{ color: {FAINT}; }}
QLabel#statusbar {{ background: {STATUS_BG}; color: #ffffff; padding: 4px 12px;
    border-radius: 4px; }}
QComboBox, QLineEdit, QPlainTextEdit {{
    background: #3c3c3c; border: 1px solid #3c3c3c; border-radius: 2px;
    padding: 5px 8px; color: {TEXT}; selection-background-color: {ACCENT_DEFAULT}; }}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid #007acc; }}
QComboBox::drop-down {{ border: none; width: 20px; margin-right: 6px; }}
QComboBox::down-arrow {{ image: url({_ASSETS}/down_arrow.png);
    width: 12px; height: 8px; }}
QComboBox[open="true"]::down-arrow {{ image: url({_ASSETS}/up_arrow.png); }}
QComboBox QAbstractItemView {{ background: #3c3c3c; border: 1px solid {BORDER};
    selection-background-color: #37373d; }}
QPushButton {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 4px;
    padding: 7px 14px; color: {TEXT}; }}
QPushButton:hover {{ background: {KEY_HOVER}; }}
QStatusBar {{ background: {PANEL}; color: {DIM}; }}
QSplitter::handle {{ background: {BG}; }}
QSplitter::handle:vertical {{ height: 8px; }}
QSplitter::handle:vertical:hover {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 10px; }}
QSplitter::handle:horizontal:hover {{ background: {BORDER}; }}
"""


def segmented_qss(accent: str) -> str:
    return f"""
    QPushButton {{ background: {CARD}; border: 1px solid {BORDER};
        padding: 6px 14px; color: {DIM}; border-radius: 4px; }}
    QPushButton:hover {{ background: {KEY_HOVER}; }}
    QPushButton:checked {{ background: {KEY_SEL}; color: #ffffff;
        border: 1px solid {accent}; }}
    """


def key_qss(accent: str) -> str:
    return f"""
    QPushButton {{ background: {KEY}; border: 1px solid {BORDER};
        border-radius: 8px; color: {TEXT}; }}
    QPushButton:hover {{ background: {KEY_HOVER}; border-color: #5a5a5f; }}
    QPushButton:checked {{ background: {KEY_SEL};
        border: 2px solid {accent}; }}
    """

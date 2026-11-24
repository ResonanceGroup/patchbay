"""Dark theme tokens + QSS. Accent comes from the active profile."""

BG = "#0f141c"
PANEL = "#151d29"
CARD = "#1b2432"
KEY = "#232e40"
KEY_TOP = "#2a3750"
BORDER = "#2c3950"
TEXT = "#e6edf6"
DIM = "#93a7c4"
FAINT = "#5d6f8c"
ACCENT_DEFAULT = "#4a8fd4"

MONO = "DejaVu Sans Mono"

QSS = f"""
QMainWindow, QWidget {{ background: {BG}; color: {TEXT};
    font-family: 'Segoe UI', 'DejaVu Sans', sans-serif; font-size: 14px; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; }}
QLabel#brand {{ font-size: 19px; font-weight: 700; }}
QLabel#dim {{ color: {DIM}; }}
QLabel#faint {{ color: {FAINT}; }}
QLabel#mono {{ font-family: '{MONO}'; }}
QComboBox, QLineEdit, QPlainTextEdit {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 6px 8px; color: {TEXT}; selection-background-color: {ACCENT_DEFAULT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {BORDER};
    selection-background-color: {KEY_TOP}; }}
QPushButton {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 7px 14px; color: {TEXT}; }}
QPushButton:hover {{ background: {KEY_TOP}; }}
QPushButton:checkable {{ border: 1px solid {BORDER}; }}
QStatusBar {{ background: {PANEL}; color: {DIM}; }}
"""


def segmented_qss(accent: str) -> str:
    return f"""
    QPushButton {{ background: {CARD}; border: 1px solid {BORDER};
        padding: 6px 14px; color: {DIM}; border-radius: 6px; }}
    QPushButton:checked {{ background: {KEY_TOP}; color: {TEXT};
        border: 1px solid {accent}; }}
    """

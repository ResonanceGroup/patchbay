"""Window matching rules + desktop window enumeration (X11).

A profile's match dict:
  {"wm_class": ["pcbnew", ...], "title": ["pcb", ...]}
wm_class entries match case-insensitively against the window's class
(instance or class name). title entries are plain substrings, all of
which must appear in the window title (case-insensitive) — no regex,
the GUI builds them by picking real windows.
"""
from __future__ import annotations

import subprocess


def matches(profile_match: dict, wm_class: str, title: str) -> int:
    """Match score for one profile against one window. 0 = no match,
    higher = more specific."""
    if not profile_match:
        return 0
    cls = (wm_class or "").lower()
    classes = [c.lower() for c in profile_match.get("wm_class", [])]
    if not any(c in cls or cls in c for c in classes):
        return 0
    score = 1
    words = [w.lower() for w in profile_match.get("title", [])]
    if words:
        t = (title or "").lower()
        if not all(w in t for w in words):
            return 0
        score += 1
    return score


def best_profile(profiles, wm_class: str, title: str):
    """Most specific profile matching the window, or None."""
    best, best_score = None, 0
    for pr in profiles:
        s = matches(pr.match, wm_class, title)
        if s > best_score:
            best, best_score = pr, s
    return best


def _xprop(win_id: int, prop: str) -> str:
    try:
        out = subprocess.run(
            ["xprop", "-id", str(win_id), prop],
            capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if "=" not in out:
        return ""
    val = out.split("=", 1)[1].strip()
    if val.startswith('"'):
        return val.strip('"')
    # WM_CLASS renders as: "instance", "class"
    parts = [p.strip().strip('"') for p in val.split(",")]
    return " ".join(parts).lower()


def list_windows() -> list[tuple[int, str, str]]:
    """Open windows on the current X display: (id, wm_class, title)."""
    try:
        out = subprocess.run(
            ["xdotool", "search", "."], capture_output=True, text=True,
            timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    wins = []
    for line in out.split():
        try:
            wid = int(line)
        except ValueError:
            continue
        cls = _xprop(wid, "WM_CLASS")
        title = _xprop(wid, "_NET_WM_NAME") or _xprop(wid, "WM_NAME")
        if not cls and not title:
            continue
        wins.append((wid, cls, title))
    return wins


def active_window() -> tuple[str, str] | None:
    """(wm_class, title) of the focused window, or None."""
    try:
        out = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    if "window id" not in out:
        return None
    try:
        wid = int(out.split("window id =")[1].strip(), 0)
    except (ValueError, IndexError):
        return None
    if wid == 0:
        return None
    cls = _xprop(wid, "WM_CLASS")
    title = _xprop(wid, "_NET_WM_NAME") or _xprop(wid, "WM_NAME")
    return cls, title

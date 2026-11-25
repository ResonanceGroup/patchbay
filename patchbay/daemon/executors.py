"""Action executors: turn a resolved Patchbay action into real input.

Uses python-evdev UInput to synthesize a virtual keyboard (chords, text,
media, macros) and subprocess for exec actions. This is the half that makes a
press actually *do* something.
"""
from __future__ import annotations

import string
import subprocess
import time
from typing import Any

from evdev import ecodes, InputEvent, UInput

from ..core.actions import (
    KeysAction, TextAction, MediaAction, MacroAction, NoneAction,
)

MOD_KEYS = {
    "ctrl": ecodes.KEY_LEFTCTRL, "rctrl": ecodes.KEY_RIGHTCTRL,
    "shift": ecodes.KEY_LEFTSHIFT, "rshift": ecodes.KEY_RIGHTSHIFT,
    "alt": ecodes.KEY_LEFTALT, "opt": ecodes.KEY_LEFTALT,
    "ralt": ecodes.KEY_RIGHTALT, "win": ecodes.KEY_LEFTMETA,
    "cmd": ecodes.KEY_LEFTMETA, "rwin": ecodes.KEY_RIGHTMETA,
    "rcmd": ecodes.KEY_RIGHTMETA,
}

MEDIA_KEYS = {
    "play_pause": ecodes.KEY_PLAYPAUSE, "play": ecodes.KEY_PLAYPAUSE,
    "next": ecodes.KEY_NEXTSONG, "prev": ecodes.KEY_PREVIOUSSONG,
    "previous": ecodes.KEY_PREVIOUSSONG, "stop": ecodes.KEY_STOPCD,
    "mute": ecodes.KEY_MUTE, "vol_up": ecodes.KEY_VOLUMEUP,
    "vol_down": ecodes.KEY_VOLUMEDOWN,
}

_NAMED = {
    "enter": ecodes.KEY_ENTER, "return": ecodes.KEY_ENTER,
    "esc": ecodes.KEY_ESC, "escape": ecodes.KEY_ESC,
    "space": ecodes.KEY_SPACE, "tab": ecodes.KEY_TAB,
    "backspace": ecodes.KEY_BACKSPACE, "delete": ecodes.KEY_DELETE,
    "del": ecodes.KEY_DELETE, "insert": ecodes.KEY_INSERT,
    "home": ecodes.KEY_HOME, "end": ecodes.KEY_END,
    "pageup": ecodes.KEY_PAGEUP, "pgup": ecodes.KEY_PAGEUP,
    "pagedown": ecodes.KEY_PAGEDOWN, "pgdn": ecodes.KEY_PAGEDOWN,
    "up": ecodes.KEY_UP, "down": ecodes.KEY_DOWN,
    "left": ecodes.KEY_LEFT, "right": ecodes.KEY_RIGHT,
    "plus": ecodes.KEY_KPPLUS, "minus": ecodes.KEY_KPMINUS,
    "print": ecodes.KEY_PRINT,
}

_LETTERS = {c: getattr(ecodes, f"KEY_{c.upper()}") for c in string.ascii_lowercase}
_DIGITS = {c: getattr(ecodes, f"KEY_{c}") for c in string.digits}
_FKEYS = {f"f{n}": getattr(ecodes, f"KEY_F{n}") for n in range(1, 13)}

# char -> (keycode, needs_shift) for typing text
_CHARS: dict[str, tuple[int, bool]] = {}
for c in string.ascii_lowercase:
    _CHARS[c] = (_LETTERS[c], False)
for c in string.ascii_uppercase:
    _CHARS[c] = (_LETTERS[c.lower()], True)
for c in string.digits:
    _CHARS[c] = (_DIGITS[c], False)
_SHIFTED = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", ":": ";", '"': "'",
}
_PUNCT = {
    "-": ecodes.KEY_MINUS, "=": ecodes.KEY_EQUAL, "[": ecodes.KEY_LEFTBRACE,
    "]": ecodes.KEY_RIGHTBRACE, "\\": ecodes.KEY_BACKSLASH,
    ";": ecodes.KEY_SEMICOLON, "'": ecodes.KEY_APOSTROPHE,
    ",": ecodes.KEY_COMMA, ".": ecodes.KEY_DOT, "/": ecodes.KEY_SLASH,
    "`": ecodes.KEY_GRAVE,
}
for c in _PUNCT:
    _CHARS[c] = (_PUNCT[c], False)
for c, base in _SHIFTED.items():
    _CHARS[c] = (_DIGITS[base] if base in _DIGITS else _PUNCT.get(base, 0), True)


def resolve_key(name: str) -> int | None:
    n = name.lower()
    if n in MOD_KEYS:
        return MOD_KEYS[n]
    if n in _NAMED:
        return _NAMED[n]
    if n in _FKEYS:
        return _FKEYS[n]
    if len(n) == 1 and n in _CHARS:
        return _CHARS[n][0]
    return getattr(ecodes, f"KEY_{n.upper()}", None)


def holdable_modifier(action: Any) -> int | None:
    """A key action that is a *single* modifier (e.g. ["shift"], ["ctrl"]) is
    held while the pad key is down and released when it comes up, so it can
    modify mouse moves and other keys (KiCad hold-Shift). Multi-key chords stay
    momentary taps. Returns the modifier ecode, or None."""
    if isinstance(action, KeysAction) and len(action.keys) == 1:
        return MOD_KEYS.get(action.keys[0].lower())
    return None


class Injector:
    """Owns one virtual keyboard and injects actions onto it."""

    def __init__(self):
        keys = sorted(set(
            list(range(0, 0x2FF))  # broad: standard + consumer keys
        ))
        self.ui = UInput({ecodes.EV_KEY: keys}, name="patchbay")
        # surrogate pad code -> modifier ecode currently held down
        self._held: dict[int, int] = {}

    def close(self):
        self.ui.close()

    def _tap(self, ecode: int, hold: float = 0.012):
        self.ui.write(ecodes.EV_KEY, ecode, 1)
        self.ui.syn()
        time.sleep(hold)
        self.ui.write(ecodes.EV_KEY, ecode, 0)
        self.ui.syn()

    def press_chord(self, keys: list[str]):
        codes = []
        for k in keys:
            c = resolve_key(k)
            if c is not None:
                codes.append(c)
        for c in codes:
            self.ui.write(ecodes.EV_KEY, c, 1)
        self.ui.syn()
        time.sleep(0.012)
        for c in reversed(codes):
            self.ui.write(ecodes.EV_KEY, c, 0)
        self.ui.syn()

    # ---- held modifiers (single-modifier key actions) ----
    def _release_code(self, ecode: int):
        self.ui.write(ecodes.EV_KEY, ecode, 0)
        self.ui.syn()

    def toggle_hold(self, surrogate: int, mod: int):
        """Press-and-hold the modifier. If it is already held for this pad key,
        release it instead — so a second press always clears it even if the pad
        never sends a key-up, guarding against a stuck modifier."""
        if surrogate in self._held:
            self._release_code(self._held.pop(surrogate))
        else:
            self.ui.write(ecodes.EV_KEY, mod, 1)
            self.ui.syn()
            self._held[surrogate] = mod

    def release_hold(self, surrogate: int):
        c = self._held.pop(surrogate, None)
        if c is not None:
            self._release_code(c)

    def is_held(self, surrogate: int) -> bool:
        return surrogate in self._held

    def release_all(self):
        for c in list(self._held.values()):
            self._release_code(c)
        self._held.clear()

    def tap_media(self, key: str):
        self._tap(MEDIA_KEYS.get(key, ecodes.KEY_PLAYPAUSE))

    def type_text(self, text: str):
        for ch in text:
            spec = _CHARS.get(ch)
            if not spec:
                continue
            code, shift = spec
            if shift:
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                self.ui.syn()
            self._tap(code)
            if shift:
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                self.ui.syn()

    def run_macro(self, steps: list[dict]):
        from ..core.actions import action_from_dict
        for step in steps:
            delay = step.get("delay")
            if delay:
                time.sleep(delay / 1000.0)
            self.execute(action_from_dict(step))

    def execute(self, action: Any):
        if action is None or isinstance(action, NoneAction):
            return
        if isinstance(action, KeysAction):
            self.press_chord(action.keys)
        elif isinstance(action, MediaAction):
            self.tap_media(action.key)
        elif isinstance(action, TextAction):
            self.type_text(action.text)
        elif isinstance(action, MacroAction):
            self.run_macro(action.steps)

"""Bluetooth raw-HID transport for the pad.

Over Bluetooth the kernel's uhid layer creates input devices that advertise
**zero** keys and emit no events, so the evdev path (discovery.find_pads) sees
nothing. The pad *does* transmit — the raw HID reports are on its `hidraw`
node. This module opens that node, parses the reports, and yields the same
`evdev.InputEvent(type, code, value)` objects the USB path produces, so
`daemon.main.handle()` works unchanged.

Report layout (from the pad's report descriptor, hidraw compound interface):
  report 01  mouse:      [01, buttons, X(16 LE), Y(16 LE), wheel]   (ignored)
  report 02  keyboard:   [02, modifiers, reserved, k1..k6]          (decoded)
  report 03  consumer:   [03, usage(16 LE)]                        (decoded)

Keyboard/consumer reports are *state* reports: a key is down while its usage
appears in the report and up when it disappears. We diff consecutive reports to
emit press(1)/release(0) events.
"""
from __future__ import annotations

import os
import glob
from pathlib import Path

from evdev import ecodes, InputEvent

# --- HID usage tables -------------------------------------------------------
# Keyboard/Keypad usage IDs (HID Usage Tables sec.10) for the surrogate names
# the firmware emits. Mirrors firmware/compile.py KEY_SURROGATES names.
KEYBOARD_USAGE: dict[str, int] = {
    **{f"f{n}": 0x3a + (n - 1) for n in range(1, 13)},     # F1..F12
    **{f"f{n}": 0x68 + (n - 13) for n in range(13, 25)},   # F13..F24
    "insert":         0x49,
    "printscreen":    0x46,
    "application":    0x65,
    "numlock":        0x53,
    "numpadslash":    0x54,
    "numpadasterisk": 0x55,
    "numpadminus":    0x56,
    "numpadplus":     0x57,
    "numpadenter":    0x58,
    "numpadequal":    0x67,
    "numpaddot":      0x63,
}

# Modifier byte (report 02 byte 1) bit -> evdev keycode.
MODIFIER_BITS: list[int] = [
    ecodes.KEY_LEFTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_LEFTALT,
    ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTCTRL, ecodes.KEY_RIGHTSHIFT,
    ecodes.KEY_RIGHTALT, ecodes.KEY_RIGHTMETA,
]

# Consumer page usage -> evdev keycode (the surrogate names the firmware uses
# for encoders + layer-3 media keys). Verified against the live capture.
CONSUMER_USAGE: dict[str, int] = {
    "play":       0x00CD,
    "next":       0x00B7,   # firmware maps "next" to Stop slot? see note
    "prev":       0x00B6,
    "stop":       0x00B7,
    "mute":       0x00E2,
    "calculator": 0x0192,
    "favorites":  0x0182,
}


def _name_to_ecode() -> dict[str, int]:
    from .surrogates import _NAME_TO_ECODE
    return _NAME_TO_ECODE


# HID usage -> evdev keycode, for keyboard + consumer surrogate names.
_USAGE_TO_ECODE: dict[int, int] = {}
_N2E = _name_to_ecode()
for _name, _u in KEYBOARD_USAGE.items():
    _USAGE_TO_ECODE[_u] = _N2E[_name]
for _name, _u in CONSUMER_USAGE.items():
    _USAGE_TO_ECODE[_u] = _N2E[_name]


# --- node identification ----------------------------------------------------
def _read_descriptor(path: str) -> bytes:
    """Read a hidraw node's report descriptor from sysfs (best-effort)."""
    dev = Path(path).name  # hidrawN
    p = Path("/sys/class/hidraw") / dev / "device" / "report_descriptor"
    try:
        return p.read_bytes()
    except OSError:
        return b""


def is_pad_keyboard(desc: bytes) -> bool:
    """The pad's compound interface carries a Keyboard collection (usage 0x06)
    AND a Consumer collection (usage page 0x0C). No other BT device does."""
    return (b"\x05\x01\x09\x06" in desc and b"\x05\x0c\x09\x01" in desc)


def find_pad_hidraw() -> str | None:
    """Path of the pad's keyboard/consumer hidraw node, or None."""
    for path in sorted(glob.glob("/dev/hidraw*")):
        desc = _read_descriptor(path)
        if desc and is_pad_keyboard(desc):
            return path
    return None


# --- the transport ----------------------------------------------------------
class HidrawPad:
    """Reads the pad's hidraw node and yields InputEvent objects."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.name = "raw-HID"
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self._keys: set[int] = set()      # currently-down keyboard usages
        self._mods: int = 0               # currently-down modifier bitmask
        self._consumer: int = 0           # currently-down consumer usage (0=none)

    def _diff_keys(self, usages: set[int]) -> list[InputEvent]:
        evs: list[InputEvent] = []
        for u in usages - self._keys:
            code = _USAGE_TO_ECODE.get(u)
            if code is not None:
                evs.append(InputEvent(0, 0, ecodes.EV_KEY, code, 1))
        for u in self._keys - usages:
            code = _USAGE_TO_ECODE.get(u)
            if code is not None:
                evs.append(InputEvent(0, 0, ecodes.EV_KEY, code, 0))
        self._keys = usages
        return evs

    def _diff_mods(self, mods: int) -> list[InputEvent]:
        evs: list[InputEvent] = []
        for bit, code in enumerate(MODIFIER_BITS):
            was = (self._mods >> bit) & 1
            now = (mods >> bit) & 1
            if now and not was:
                evs.append(InputEvent(0, 0, ecodes.EV_KEY, code, 1))
            elif was and not now:
                evs.append(InputEvent(0, 0, ecodes.EV_KEY, code, 0))
        self._mods = mods
        return evs

    def _diff_consumer(self, usage: int) -> list[InputEvent]:
        evs: list[InputEvent] = []
        if self._consumer and self._consumer != usage:
            code = _USAGE_TO_ECODE.get(self._consumer)
            if code is not None:
                evs.append(InputEvent(0, 0, ecodes.EV_KEY, code, 0))
        if usage and usage != self._consumer:
            code = _USAGE_TO_ECODE.get(usage)
            if code is not None:
                evs.append(InputEvent(0, 0, ecodes.EV_KEY, code, 1))
        self._consumer = usage
        return evs

    def _parse(self, report: bytes) -> list[InputEvent]:
        if not report:
            return []
        rid = report[0]
        if rid == 0x02 and len(report) >= 9:
            mods = report[1]
            usages = {u for u in report[3:9] if u}
            return self._diff_mods(mods) + self._diff_keys(usages)
        if rid == 0x03 and len(report) >= 3:
            usage = report[1] | (report[2] << 8)
            return self._diff_consumer(usage)
        return []   # report 01 (mouse) ignored

    def read(self) -> list[InputEvent]:
        """Drain all available reports, return decoded events."""
        out: list[InputEvent] = []
        while True:
            try:
                report = os.read(self.fd, 64)
            except BlockingIOError:
                break
            except OSError:
                raise
            if not report:
                break
            out.extend(self._parse(report))
        return out

    def grab(self) -> None:
        """No-op: hidraw is read-only and doesn't need an exclusive grab.
        Present so HidrawPad slots into the daemon's evdev-style read loop."""

    def ungrab(self) -> None:
        """No-op counterpart of grab()."""

    def close(self) -> None:
        try:
            os.close(self.fd)
        except OSError:
            pass

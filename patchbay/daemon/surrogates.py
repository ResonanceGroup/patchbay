"""Surrogate keycode <-> pad control mapping (daemon side).

Mirrors firmware/compile.py: the pad is programmed so each control emits a
unique F-key. The daemon grabs the pad, sees that F-key, and knows exactly
which control (and which encoder gesture) was used. Layers are software.
"""
from __future__ import annotations

from evdev import ecodes

from ..firmware.compile import (
    KEY_SURROGATES, ENCODER_SURROGATES, LAYER_DOWN_KEY, LAYER_UP_KEY,
)

# "f13" -> ecodes.KEY_F13
_NAME_TO_ECODE = {
    f"f{n}": getattr(ecodes, f"KEY_F{n}") for n in range(1, 25)
}

# evdev keycode -> ("key", key_id) or ("encoder", enc_id, gesture)
DECODE: dict[int, tuple] = {}
for kid, name in KEY_SURROGATES.items():
    DECODE[_NAME_TO_ECODE[name]] = ("key", kid)
for eid, gestures in ENCODER_SURROGATES.items():
    for gesture, name in gestures.items():
        DECODE[_NAME_TO_ECODE[name]] = ("encoder", eid, gesture)

# layer-switch surrogates (K11/K12 by default)
LAYER_DOWN_ECODE = _NAME_TO_ECODE[KEY_SURROGATES[LAYER_DOWN_KEY]]
LAYER_UP_ECODE = _NAME_TO_ECODE[KEY_SURROGATES[LAYER_UP_KEY]]

# The set of keycodes the daemon claims from the pad.
SURROGATE_ECODES = set(DECODE) | {LAYER_DOWN_ECODE, LAYER_UP_ECODE}

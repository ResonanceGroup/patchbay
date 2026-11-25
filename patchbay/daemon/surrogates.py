"""Surrogate keycode <-> pad control mapping (daemon side).

Mirrors firmware/compile.py: every control on every hardware layer emits its
own key code. The daemon grabs the pad, sees that code, and knows exactly which
control on which layer was used — the pad's side button cycles the hardware
layer, and the layer is read straight off the code. No modifiers are used for
layer tagging, so real chords stay free; no buttons are reserved.
"""
from __future__ import annotations

from evdev import ecodes

from ..firmware.compile import KEY_SURROGATES, ENCODER_SURROGATES

# surrogate name -> evdev keycode
_NAME_TO_ECODE: dict[str, int] = {
    f"f{n}": getattr(ecodes, f"KEY_F{n}") for n in range(1, 25)
}
_NAME_TO_ECODE.update({
    "numpadslash":    ecodes.KEY_KPSLASH,
    "numpadasterisk": ecodes.KEY_KPASTERISK,
    "numpadminus":    ecodes.KEY_KPMINUS,
    "numpadplus":     ecodes.KEY_KPPLUS,
    "numpadenter":    ecodes.KEY_KPENTER,
    "numpadequal":    ecodes.KEY_KPEQUAL,
    "numpaddot":      ecodes.KEY_KPDOT,
    "printscreen":    ecodes.KEY_SYSRQ,
    "application":    ecodes.KEY_MENU,
    "numlock":        ecodes.KEY_NUMLOCK,
    "play":           ecodes.KEY_PLAYPAUSE,
    "next":           ecodes.KEY_NEXTSONG,
    "prev":           ecodes.KEY_PREVIOUSSONG,
    "stop":           ecodes.KEY_STOPCD,
    "mute":           ecodes.KEY_MUTE,
    "calculator":     ecodes.KEY_CALC,
    "favorites":      ecodes.KEY_FAVORITES,
    "insert":         ecodes.KEY_INSERT,
})

# evdev keycode -> ("key", key_id, layer) or ("encoder", enc_id, gesture)
DECODE: dict[int, tuple] = {}
for layer, keys in KEY_SURROGATES.items():
    for kid, name in keys.items():
        DECODE[_NAME_TO_ECODE[name]] = ("key", kid, layer)
for eid, gestures in ENCODER_SURROGATES.items():
    for gesture, name in gestures.items():
        DECODE[_NAME_TO_ECODE[name]] = ("encoder", eid, gesture)

# The set of keycodes the daemon claims from the pad.
SURROGATE_ECODES = set(DECODE)

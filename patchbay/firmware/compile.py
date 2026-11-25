"""Compile Patchbay data into ch57x-keyboard-tool YAML.

Two modes:

* **surrogate** (daemon mode) — every physical control is mapped to a unique,
  rarely-used key code (F1..F24). The firmware is therefore *fixed* and does
  not depend on any profile: it just tells the host "control X on the pad was
  used". The daemon decodes those codes, resolves the active profile + layer,
  and injects the real action. Layers are handled in software by the daemon.

* **direct** (standalone) — a single profile's actions are compiled straight
  into the firmware, so the pad works with no daemon running. Per-app
  switching then requires re-uploading. Text/macro actions are limited by the
  tool's 5-step sequence cap; the daemon has no such limit.

The YAML schema (kriomant/ch57x-keyboard-tool):
    model: ch57x-2
    orientation: normal
    rows: 3
    columns: 4
    knobs: 2
    layers:
      - buttons: [[a, b, c, d], [e, f, g, h], [i, j, k, l]]
        knobs:
          - {ccw: ..., press: ..., cw: ...}
          - {ccw: ..., press: ..., cw: ...}
Buttons are listed row-major (3 rows x 4 cols) in normal orientation; knobs
left-to-right. See doc/actions.md for the action-string grammar.
"""
from __future__ import annotations

from typing import Any

import yaml

from ..core.profile import KEY_IDS, ENCODER_IDS, LAYER_COUNT, Profile
from ..core.actions import (
    KeysAction, TextAction, MediaAction, MacroAction, NoneAction,
)

MODEL = "ch57x-2"
ROWS, COLS, KNOBS = 3, 4, 2

# --- surrogate allocation (daemon mode) -------------------------------------
# Fixed, profile-independent. Every control on every hardware layer gets its
# own key code, so the daemon knows exactly which control on which layer was
# used: the pad's side button cycles the hardware layer and the daemon reads
# the layer straight off the code. No modifiers (those stay free for real
# chords), no reserved buttons.
#
# Codes: layer-1 buttons use F13..F24, layer-2 buttons use F1..F12, layer-3
# buttons use other rarely-used keys (numpad operators, media, nav). The knobs
# are identical on every layer, so each carries one global code. The daemon
# grabs the pad, so none of these codes reach the OS while it is running.
_BUTTON_NAMES: dict[int, list[str]] = {
    0: [f"f{13 + i}" for i in range(12)],   # layer 1 buttons
    1: [f"f{1 + i}" for i in range(12)],    # layer 2 buttons
    2: ["numpadslash", "numpadasterisk", "numpadminus", "numpadplus",
        "numpadenter", "numpadequal", "numpaddot", "printscreen",
        "application", "numlock", "play", "next"],  # layer 3 buttons
}
# hardware layer -> (key_id -> surrogate name)
KEY_SURROGATES: dict[int, dict[str, str]] = {
    layer: {kid: names[i] for i, kid in enumerate(KEY_IDS)}
    for layer, names in _BUTTON_NAMES.items()
}
# Knobs are global (same action on every layer): one code per gesture.
ENCODER_SURROGATES: dict[str, dict[str, str]] = {
    "E1": {"press": "prev", "cw": "stop", "ccw": "mute"},
    "E2": {"press": "calculator", "cw": "favorites", "ccw": "insert"},
}

# --- action-string compiler (direct mode) -----------------------------------
MODIFIERS = {"ctrl", "rctrl", "shift", "rshift", "alt", "opt", "ralt",
             "win", "cmd", "rwin", "rcmd"}
MEDIA_MAP = {
    "play_pause": "play", "play": "play", "next": "next", "prev": "prev",
    "previous": "prev", "stop": "stop", "mute": "mute",
    "vol_up": "volumeup", "vol_down": "volumedown",
}
# Patchbay key name -> kriomant key name (verified against `show-keys`).
KEYNAME = {
    "+": "plus", "-": "minus", "pageup": "pageup", "pagedown": "pagedown",
    "pgup": "pageup", "pgdn": "pagedown", "del": "delete", "return": "enter",
    "escape": "esc", "space": "space", "tab": "tab", "up": "up",
    "down": "down", "left": "left", "right": "right", "home": "home",
    "end": "end", "insert": "insert",
}


def _keyname(k: str) -> str:
    k = k.lower()
    return KEYNAME.get(k, k)


def action_to_string(action: Any) -> str:
    """Compile one Patchbay action into a kriomant action string.

    Raises ValueError for actions the firmware cannot express (long text,
    complex macros) so direct mode fails loudly rather than silently.
    """
    if action is None or isinstance(action, NoneAction):
        return ""
    if isinstance(action, KeysAction):
        if not action.keys:
            return ""
        return "-".join(_keyname(k) for k in action.keys)
    if isinstance(action, MediaAction):
        return MEDIA_MAP.get(action.key, "")
    if isinstance(action, TextAction):
        chars = [_keyname(c) if len(c) == 1 else c for c in action.text]
        if len(chars) > 5:
            raise ValueError(
                f"direct firmware mode caps text at 5 chars "
                f"({action.text!r}); use the daemon for longer text")
        return ",".join(chars)
    if isinstance(action, MacroAction):
        parts = []
        for step in action.steps:
            sub = action_from_step(step)
            if sub:
                parts.append(sub)
        if len(parts) > 5:
            raise ValueError(
                f"direct firmware mode caps macros at 5 steps "
                f"({len(parts)}); use the daemon")
        return ",".join(parts)
    return ""


def action_from_step(step: dict) -> str:
    from ..core.actions import action_from_dict
    return action_to_string(action_from_dict(step))


# --- YAML builders ----------------------------------------------------------
def _empty_button_grid() -> list[list[str]]:
    return [[""] * COLS for _ in range(ROWS)]


def _grid_from_keys(keys: dict[str, str]) -> list[list[str]]:
    """Place key_id->action strings into the row-major 3x4 grid.

    KEY_IDS are K01..K12 laid out as the README pad diagram:
        K01 K02 K03 K04
        K05 K06 K07 K08
        K09 K10 K11 K12
    """
    grid = _empty_button_grid()
    for i, kid in enumerate(KEY_IDS):
        r, c = divmod(i, COLS)
        grid[r][c] = keys.get(kid, "")
    return grid


def build_surrogate_config() -> dict[str, Any]:
    """Fixed firmware config: every control on every hardware layer -> its own
    surrogate code. The side button cycles the hardware layer; the daemon reads
    the layer off the code. The firmware stays profile-independent — it only
    reports "control X on layer N was used"."""
    layers = []
    for layer in range(LAYER_COUNT):
        keys = {kid: KEY_SURROGATES[layer][kid] for kid in KEY_IDS}
        knobs = [
            {"ccw": ENCODER_SURROGATES["E1"]["ccw"],
             "press": ENCODER_SURROGATES["E1"]["press"],
             "cw": ENCODER_SURROGATES["E1"]["cw"]},
            {"ccw": ENCODER_SURROGATES["E2"]["ccw"],
             "press": ENCODER_SURROGATES["E2"]["press"],
             "cw": ENCODER_SURROGATES["E2"]["cw"]},
        ]
        layers.append({"buttons": _grid_from_keys(keys), "knobs": knobs})
    return {
        "model": MODEL,
        "orientation": "normal",
        "rows": ROWS,
        "columns": COLS,
        "knobs": KNOBS,
        "layers": layers,
    }


def build_direct_config(profile: Profile) -> dict[str, Any]:
    """Per-profile firmware config: each layer's actions compiled in."""
    layers = []
    for layer in profile.layers:
        keys: dict[str, str] = {}
        for kid, binding in layer.keys.items():
            keys[kid] = action_to_string(binding.action)
        knobs = []
        for eid in ENCODER_IDS:
            eb = layer.encoders.get(eid)
            knobs.append({
                "ccw": action_to_string(eb.ccw) if eb else "",
                "press": action_to_string(eb.press) if eb else "",
                "cw": action_to_string(eb.cw) if eb else "",
            })
        layers.append({"buttons": _grid_from_keys(keys), "knobs": knobs})
    return {
        "model": MODEL,
        "orientation": "normal",
        "rows": ROWS,
        "columns": COLS,
        "knobs": KNOBS,
        "layers": layers,
    }


def to_yaml(config: dict[str, Any]) -> str:
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False)

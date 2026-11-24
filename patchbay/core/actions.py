"""Action types a binding can perform.

Every action serializes to a plain JSON dict with a "type" key, so profiles
stay human-editable and diff-friendly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NoneAction:
    """Key does nothing (explicitly unbound)."""
    type: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "none"}

    def summary(self) -> str:
        return ""


@dataclass
class KeysAction:
    """A key chord, e.g. ["ctrl", "z"]."""
    keys: list[str] = field(default_factory=list)
    type: str = "keys"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "keys", "keys": self.keys}

    def summary(self) -> str:
        return "+".join(k.capitalize() if len(k) > 1 else k.upper() for k in self.keys)


@dataclass
class TextAction:
    """Type a literal string."""
    text: str = ""
    type: str = "text"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "text", "text": self.text}

    def summary(self) -> str:
        return f'"{self.text}"'


@dataclass
class MediaAction:
    """A consumer-IR media key: play_pause, next, prev, mute, vol_up, vol_down."""
    key: str = "play_pause"
    type: str = "media"

    MEDIA_KEYS = ["play_pause", "next", "prev", "stop", "mute", "vol_up", "vol_down"]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "media", "key": self.key}

    def summary(self) -> str:
        return self.key.replace("_", " ")


@dataclass
class MacroAction:
    """A timed sequence of steps. Each step is a keys/text action with an
    optional delay (ms) applied *before* the step."""
    steps: list[dict[str, Any]] = field(default_factory=list)
    type: str = "macro"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "macro", "steps": self.steps}

    def summary(self) -> str:
        return f"{len(self.steps)} steps"


ACTION_CLASSES = {
    "none": NoneAction,
    "keys": KeysAction,
    "text": TextAction,
    "media": MediaAction,
    "macro": MacroAction,
}


def action_from_dict(d: dict[str, Any]):
    cls = ACTION_CLASSES.get(d.get("type", "none"), NoneAction)
    if cls is KeysAction:
        return KeysAction(keys=list(d.get("keys", [])))
    if cls is TextAction:
        return TextAction(text=d.get("text", ""))
    if cls is MediaAction:
        return MediaAction(key=d.get("key", "play_pause"))
    if cls is MacroAction:
        return MacroAction(steps=list(d.get("steps", [])))
    return NoneAction()

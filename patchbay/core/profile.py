"""Profile model: one file per application, three layers each.

KEY_IDS (K01..K12) are the firmware's surrogate slots — the daemon decodes a
physical control to a Kxx id, and profiles bind actions to those ids. The
physical arrangement of those ids on the pad is NOT reading order: measured
empirically (pressing each button and logging the decoded id), the pad is a
4-row x 3-col grid laid out as:

  E1        E2           two clickable encoders (left, right)
  K04 K08 K12
  K03 K07 K11
  K02 K06 K10
  K01 K05 K09

PHYSICAL_KEY_ORDER lists the ids in the order they appear on the pad, row by
row, so the GUI can draw a truthful replica. The firmware grid itself is 3x4
(see firmware/compile.py); the pad's physical orientation rotates it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .actions import action_from_dict

KEY_IDS = [f"K{i:02d}" for i in range(1, 13)]
ENCODER_IDS = ["E1", "E2"]
LAYER_COUNT = 3

# Ids in physical pad order (4 rows x 3 cols), measured 2026-11-25.
PHYSICAL_KEY_ORDER = [
    "K04", "K08", "K12",
    "K03", "K07", "K11",
    "K02", "K06", "K10",
    "K01", "K05", "K09",
]


@dataclass
class Binding:
    """One key press -> one action, with an optional human label."""
    action: Any = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.action is not None:
            d["action"] = self.action.to_dict()
        if self.label:
            d["label"] = self.label
        return d

    def display_label(self) -> str:
        return self.label or (self.action.summary() if self.action else "")


@dataclass
class EncoderBinding:
    """One encoder -> turn-cw / turn-ccw / press actions."""
    cw: Any = None
    ccw: Any = None
    press: Any = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.label:
            d["label"] = self.label
        for name, act in (("cw", self.cw), ("ccw", self.ccw), ("press", self.press)):
            if act is not None:
                d[name] = act.to_dict()
        return d

    def display_label(self) -> str:
        return self.label or (self.cw.summary() if self.cw else "")


@dataclass
class Layer:
    name: str = ""
    keys: dict[str, Binding] = field(default_factory=dict)
    encoders: dict[str, EncoderBinding] = field(default_factory=dict)

    def binding(self, key_id: str) -> Binding:
        return self.keys.setdefault(key_id, Binding())

    def encoder(self, enc_id: str) -> EncoderBinding:
        return self.encoders.setdefault(enc_id, EncoderBinding())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "keys": {k: b.to_dict() for k, b in self.keys.items() if b.to_dict()},
            "encoders": {k: b.to_dict() for k, b in self.encoders.items() if b.to_dict()},
        }


@dataclass
class Profile:
    """One keymap profile, grouped under an application."""
    app: str = "General"
    name: str = ""
    match: dict[str, Any] = field(default_factory=dict)  # {"wm_class": [...], "title": [...]}
    accent: str = "#4a8fd4"
    layers: list[Layer] = field(default_factory=list)
    path: Path | None = None

    def __post_init__(self):
        if not self.name:
            self.name = self.app
        if not self.layers:
            self.layers = [Layer(name=f"L{i}") for i in range(1, LAYER_COUNT + 1)]

    def layer(self, idx: int) -> Layer:
        return self.layers[idx]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"app": self.app}
        if self.name and self.name != self.app:
            d["name"] = self.name
        if self.match:
            d["match"] = self.match
        if self.accent != "#4a8fd4":
            d["accent"] = self.accent
        d["layers"] = [l.to_dict() for l in self.layers]
        return d

    def save(self, path: Path | None = None) -> Path:
        p = path or self.path
        if p is None:
            raise ValueError("no path for profile")
        p.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        self.path = p
        return p


def _binding_from_dict(d: dict[str, Any]) -> Binding:
    return Binding(
        action=action_from_dict(d["action"]) if "action" in d else None,
        label=d.get("label", ""),
    )


def _encoder_from_dict(d: dict[str, Any]) -> EncoderBinding:
    return EncoderBinding(
        cw=action_from_dict(d["cw"]) if "cw" in d else None,
        ccw=action_from_dict(d["ccw"]) if "ccw" in d else None,
        press=action_from_dict(d["press"]) if "press" in d else None,
        label=d.get("label", ""),
    )


def load_profile(path: Path) -> Profile:
    data = json.loads(path.read_text())
    layers = []
    for ld in data.get("layers", []):
        layers.append(Layer(
            name=ld.get("name", ""),
            keys={k: _binding_from_dict(bd) for k, bd in ld.get("keys", {}).items()},
            encoders={k: _encoder_from_dict(bd) for k, bd in ld.get("encoders", {}).items()},
        ))
    while len(layers) < LAYER_COUNT:
        layers.append(Layer(name=f"L{len(layers) + 1}"))
    return Profile(
        app=data.get("app", path.stem),
        name=data.get("name", data.get("app", path.stem)),
        match=data.get("match", {}),
        accent=data.get("accent", "#4a8fd4"),
        layers=layers,
        path=path,
    )


def load_profiles(directory: Path) -> list[Profile]:
    return sorted(
        (load_profile(p) for p in directory.glob("*.json")),
        key=lambda pr: (pr.app != "General", pr.app.lower()),
    )


def app_groups(profiles: list[Profile]) -> list[str]:
    """Distinct application names, in list order."""
    seen: list[str] = []
    for pr in profiles:
        if pr.app not in seen:
            seen.append(pr.app)
    return seen


class ProfileState:
    """Persisted UI state: last profile selected per application, and the
    auto-switch toggle. Stored as _state.json inside the profiles dir."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                self.data = {}

    def last_profile(self, app: str) -> str | None:
        return self.data.get("last", {}).get(app)

    def set_last_profile(self, app: str, name: str):
        self.data.setdefault("last", {})[app] = name
        self._save()

    @property
    def auto_switch(self) -> bool:
        return bool(self.data.get("auto_switch", False))

    @auto_switch.setter
    def auto_switch(self, on: bool):
        self.data["auto_switch"] = bool(on)
        self._save()

    def _save(self):
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")

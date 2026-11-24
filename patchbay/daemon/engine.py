"""Daemon engine: resolve a decoded pad control into an action.

State: the current software layer (0..2) and the active profile (follows the
focused window, or a pinned profile). On each press we look up the binding for
that control on the active profile's current layer.
"""
from __future__ import annotations

from pathlib import Path

from ..core.profile import load_profiles, Profile, LAYER_COUNT
from ..core import window_rules


class Engine:
    def __init__(self, profiles_dir: Path, pinned: Profile | None = None):
        self.profiles_dir = Path(profiles_dir)
        self.profiles = load_profiles(self.profiles_dir)
        self.pinned = pinned
        self.layer = 0

    def reload(self):
        self.profiles = load_profiles(self.profiles_dir)

    def cycle_layer(self, delta: int):
        self.layer = (self.layer + delta) % LAYER_COUNT

    def active_profile(self) -> Profile | None:
        if self.pinned:
            return self.pinned
        win = window_rules.active_window()
        if not win:
            return None
        return window_rules.best_profile(self.profiles, win[0], win[1])

    def _layer_obj(self, profile: Profile):
        if self.layer < len(profile.layers):
            return profile.layers[self.layer]
        return None

    def action_for_key(self, key_id: str):
        p = self.active_profile()
        if not p:
            return None
        layer = self._layer_obj(p)
        if not layer:
            return None
        b = layer.keys.get(key_id)
        return b.action if b else None

    def action_for_encoder(self, enc_id: str, gesture: str):
        p = self.active_profile()
        if not p:
            return None
        layer = self._layer_obj(p)
        if not layer:
            return None
        eb = layer.encoders.get(enc_id)
        if not eb:
            return None
        return getattr(eb, gesture, None)

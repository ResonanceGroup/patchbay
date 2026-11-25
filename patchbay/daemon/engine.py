"""Daemon engine: resolve a decoded pad control into an action.

State: the current layer (read from the surrogate code the pad emits — the
side button cycles it) and the active profile (follows the focused window, or a
pinned profile). On each press we look up the binding for that control on the
active profile's current layer.
"""
from __future__ import annotations

from pathlib import Path

from ..core.profile import load_profiles, Profile
from ..core import window_rules


class Engine:
    def __init__(self, profiles_dir: Path, pinned: Profile | None = None):
        self.profiles_dir = Path(profiles_dir)
        self.profiles = load_profiles(self.profiles_dir)
        self.pinned = pinned
        self.pin_key: str | None = None
        if pinned is not None:
            self.pin_key = pinned.name or pinned.app
        self.layer = 0

    def set_pin(self, key: str) -> bool:
        """Pin by profile name or app name. Returns True if found."""
        self.pin_key = key
        for p in self.profiles:
            if p.name == key or p.app == key:
                self.pinned = p
                return True
        self.pinned = None
        return False

    def reload(self):
        """Reload profiles from disk, re-resolving the pinned one by name."""
        self.profiles = load_profiles(self.profiles_dir)
        if self.pin_key is not None:
            for p in self.profiles:
                if p.name == self.pin_key or p.app == self.pin_key:
                    self.pinned = p
                    break
            else:
                self.pinned = None

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

"""Pad identity + transport configuration.

The CH57x pad connects over USB (idVendor:idProduct 1189:8890) or Bluetooth
(a HID Keyboard with a fixed MAC). The daemon matches the pad by identity so
it works over either transport, and prefers USB when both are connected.

Persisted at ~/.config/patchbay/config.json so the GUI and daemon share it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "patchbay" / "config.json"

# Defaults for the WCH CH57x pad.
DEFAULT_USB_VID = 0x1189
DEFAULT_USB_PID = 0x8890


@dataclass
class PadConfig:
    usb_vid: int = DEFAULT_USB_VID
    usb_pid: int = DEFAULT_USB_PID
    bt_mac: str | None = None          # e.g. "D0:54:7B:17:95:A0"
    transport: str = "auto"            # auto | usb | bluetooth

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "PadConfig":
        try:
            data = json.loads(path.read_text())
            return cls(**{k: v for k, v in data.items()
                          if k in cls.__dataclass_fields__})
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return cls()

    def save(self, path: Path = CONFIG_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

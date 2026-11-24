"""Transport-aware pad discovery.

The same pad appears as a USB HID keyboard (idVendor:idProduct) or a Bluetooth
HID Keyboard (MAC). Both surface as evdev devices; we match by identity and
prefer USB when both are connected. The firmware (and therefore the surrogate
keys) is stored on the device, so a pad programmed over USB emits the same
surrogates over Bluetooth — the daemon works over either transport.
"""
from __future__ import annotations

from dataclasses import dataclass

from evdev import InputDevice, list_devices, ecodes

from ..core.device_config import PadConfig

USB = "usb"
BT = "bluetooth"


@dataclass
class Candidate:
    path: str
    name: str
    transport: str
    vid: int | None
    pid: int | None
    mac: str | None

    @property
    def label(self) -> str:
        if self.transport == USB:
            return f"USB {self.vid:04x}:{self.pid:04x}"
        return f"Bluetooth {self.mac or '?'}"


def _mac_of(dev: InputDevice) -> str | None:
    for src in (dev.uniq, dev.phys):
        if src and ":" in src and len(src.split(":")) == 6:
            return src.upper()
    return None


def classify(dev: InputDevice) -> Candidate:
    info = dev.info
    bt = info.bustype == ecodes.EV_BUS_BLUETOOTH
    usb = info.bustype == ecodes.EV_BUS_USB
    transport = BT if bt else (USB if usb else "other")
    return Candidate(
        path=dev.path, name=dev.name, transport=transport,
        vid=info.vendor if usb else None,
        pid=info.product if usb else None,
        mac=_mac_of(dev),
    )


def matches(c: Candidate, cfg: PadConfig) -> bool:
    if c.transport == USB:
        return c.vid == cfg.usb_vid and c.pid == c.pid
    if c.transport == BT:
        if cfg.bt_mac and c.mac:
            return c.mac == cfg.bt_mac.upper()
        return False
    return False


def scan(cfg: PadConfig | None = None) -> list[Candidate]:
    """All input devices, classified — for the settings 'detect' picker."""
    out = []
    for path in list_devices():
        try:
            out.append(classify(InputDevice(path)))
        except OSError:
            continue
    return out


def find_pad(cfg: PadConfig) -> InputDevice | None:
    """Best pad device: USB preferred over Bluetooth when both present."""
    usb = bt = None
    for c in scan(cfg):
        if not matches(c, cfg):
            continue
        if c.transport == USB and usb is None:
            usb = c
        elif c.transport == BT and bt is None:
            bt = c
    chosen = usb or bt
    return InputDevice(chosen.path) if chosen else None

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

# Kernel input bus-type numbers (linux/input.h). evdev does not always expose
# these as named constants, so use the stable numeric values.
BUS_USB = 3
BUS_BLUETOOTH = 5


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
    bt = info.bustype == BUS_BLUETOOTH
    usb = info.bustype == BUS_USB
    transport = BT if bt else (USB if usb else "other")
    return Candidate(
        path=dev.path, name=dev.name, transport=transport,
        vid=info.vendor if usb else None,
        pid=info.product if usb else None,
        mac=_mac_of(dev),
    )


def matches(c: Candidate, cfg: PadConfig) -> bool:
    if c.transport == USB:
        return c.vid == cfg.usb_vid and c.pid == cfg.usb_pid
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


def find_pads(cfg: PadConfig) -> list[InputDevice]:
    """All interfaces of the pad, USB preferred over Bluetooth.

    The pad exposes several HID interfaces (keyboard / keyboard / mouse) and
    the surrogate F-keys are not reliably emitted on the interface that
    advertises them. So we grab every interface of the chosen transport and
    read from all of them; the decoder ignores anything that isn't a surrogate.
    """
    matched = [c for c in scan(cfg) if matches(c, cfg)]
    for transport in (USB, BT):
        group = [c for c in matched if c.transport == transport]
        if group:
            devs = []
            for c in group:
                try:
                    devs.append(InputDevice(c.path))
                except OSError:
                    continue
            return devs
    return []


def find_usb_pads(cfg: PadConfig) -> list[InputDevice]:
    """Only the pad's USB evdev interfaces.

    Over Bluetooth the kernel's uhid layer creates evdev devices that advertise
    no keys and emit no events, so the evdev path is useless there — Bluetooth
    is served by the raw-HID (hidraw) transport instead. This returns just the
    USB interfaces so the caller can fall back to hidraw for Bluetooth."""
    return [InputDevice(c.path)
            for c in scan(cfg)
            if c.transport == USB and matches(c, cfg)]


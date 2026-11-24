"""Patchbay daemon: grab the CH57x pad, decode surrogate keys, resolve the
active profile + layer, and inject the mapped action.

    python -m patchbay.daemon --profiles profiles/ [--device CH57] [--pin KiCad]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evdev import InputDevice, ecodes, list_devices

from .surrogates import (
    DECODE, LAYER_DOWN_ECODE, LAYER_UP_ECODE, SURROGATE_ECODES,
)
from .engine import Engine
from .executors import Injector
from ..core.profile import load_profiles


def find_device(name_filter: str | None) -> InputDevice | None:
    """Pick the pad. Prefer a name match; otherwise the first device that
    advertises our surrogate F-keys (only the programmed pad does)."""
    for path in list_devices():
        dev = InputDevice(path)
        if name_filter and name_filter.lower() not in dev.name.lower():
            continue
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if SURROGATE_ECODES.issubset(set(caps)):
            return dev
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="patchbay-daemon")
    ap.add_argument("--profiles", default="profiles", type=Path)
    ap.add_argument("--device", default=None,
                    help="substring of the pad device name to grab")
    ap.add_argument("--pin", default=None,
                    help="pin a profile by name instead of following windows")
    ap.add_argument("--list", action="store_true", help="list candidate devices")
    args = ap.parse_args(argv)

    if args.list:
        for path in list_devices():
            print(f"{path}\t{InputDevice(path).name}")
        return 0

    dev = find_device(args.device)
    if dev is None:
        print("no programmed pad found (is it plugged in and uploaded?)",
              file=sys.stderr)
        return 1

    pinned = None
    if args.pin:
        for p in load_profiles(args.profiles):
            if p.name == args.pin or p.app == args.pin:
                pinned = p
                break

    engine = Engine(args.profiles, pinned=pinned)
    injector = Injector()
    print(f"grabbing {dev.path} ({dev.name}); layer {engine.layer + 1}")

    dev.grab()
    try:
        for ev in dev.read_loop():
            if ev.type != ecodes.EV_KEY or ev.value == 0:
                continue  # act on key-press edges only
            if ev.code == LAYER_DOWN_ECODE:
                engine.cycle_layer(-1)
                print(f"layer -> {engine.layer + 1}")
                continue
            if ev.code == LAYER_UP_ECODE:
                engine.cycle_layer(+1)
                print(f"layer -> {engine.layer + 1}")
                continue
            target = DECODE.get(ev.code)
            if not target:
                continue
            if target[0] == "key":
                action = engine.action_for_key(target[1])
            else:
                action = engine.action_for_encoder(target[1], target[2])
            if action is not None:
                injector.execute(action)
    except KeyboardInterrupt:
        pass
    finally:
        injector.close()
        dev.ungrab()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Patchbay daemon: grab the CH57x pad (USB or Bluetooth), decode surrogate
keys, resolve the active profile + layer, and inject the mapped action.

    python -m patchbay.daemon --profiles profiles/ [--detect] [--pin KiCad]

The daemon supervises the connection: if the pad is unplugged or switches
transport (USB -> Bluetooth), it re-acquires automatically.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from evdev import ecodes

from .surrogates import DECODE, LAYER_DOWN_ECODE, LAYER_UP_ECODE
from .engine import Engine
from .executors import Injector
from .discovery import find_pad, scan
from ..core.device_config import PadConfig
from ..core.profile import load_profiles


def detect() -> int:
    print("input devices:")
    for c in scan():
        print(f"  {c.path:24} {c.transport:10} {c.label:22} {c.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="patchbay-daemon")
    ap.add_argument("--profiles", default="profiles", type=Path)
    ap.add_argument("--pin", default=None, help="pin a profile by name/app")
    ap.add_argument("--detect", action="store_true",
                    help="list candidate devices and exit")
    args = ap.parse_args(argv)

    if args.detect:
        return detect()

    cfg = PadConfig.load()
    engine = Engine(args.profiles)
    if args.pin:
        for p in engine.profiles:
            if p.name == args.pin or p.app == args.pin:
                engine.pinned = p
                break
    injector = Injector()

    try:
        while True:
            dev = find_pad(cfg)
            if dev is None:
                print("pad not connected (USB or Bluetooth); waiting...",
                      file=sys.stderr)
                time.sleep(1.0)
                continue
            print(f"connected: {dev.path} ({dev.name})")
            try:
                dev.grab()
                for ev in dev.read_loop():
                    if ev.type != ecodes.EV_KEY or ev.value == 0:
                        continue
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
            except (OSError, IOError):
                print("pad disconnected; re-scanning...", file=sys.stderr)
                try:
                    dev.ungrab()
                except Exception:
                    pass
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        injector.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

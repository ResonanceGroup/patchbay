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

import selectors

from evdev import ecodes

from .surrogates import DECODE, LAYER_DOWN_ECODE, LAYER_UP_ECODE
from .engine import Engine
from .executors import Injector
from .discovery import find_pads, scan
from ..core.device_config import PadConfig
from ..core.profile import load_profiles


def handle(ev, engine: Engine, injector: Injector) -> None:
    """Decode one surrogate event and inject the mapped action."""
    if ev.type != ecodes.EV_KEY or ev.value == 0:
        return
    if ev.code in (LAYER_DOWN_ECODE, LAYER_UP_ECODE):
        # These two surrogate slots double as layer switches, but only when the
        # active profile leaves them unbound. If the profile assigns them a real
        # action (e.g. a diagram that uses all 12 buttons), the action wins.
        kid = DECODE[ev.code][1]
        action = engine.action_for_key(kid)
        if action is not None:
            prof = engine.active_profile()
            pname = prof.name if prof else "(no profile)"
            print(f"[{pname} L{engine.layer + 1}] {kid} -> {action.summary()}")
            injector.execute(action)
            return
        engine.cycle_layer(-1 if ev.code == LAYER_DOWN_ECODE else +1)
        print(f"layer -> {engine.layer + 1}")
        return
    target = DECODE.get(ev.code)
    if not target:
        return
    if target[0] == "key":
        action = engine.action_for_key(target[1])
    else:
        action = engine.action_for_encoder(target[1], target[2])
    prof = engine.active_profile()
    pname = prof.name if prof else "(no profile)"
    if action is not None:
        print(f"[{pname} L{engine.layer + 1}] "
              f"{'/'.join(target[1:])} -> {action.summary()}")
        injector.execute(action)
    else:
        print(f"[{pname} L{engine.layer + 1}] "
              f"{'/'.join(target[1:])} -> (unbound)")


def detect() -> int:
    print("input devices:")
    for c in scan():
        print(f"  {c.path:24} {c.transport:10} {c.label:22} {c.name}")
    return 0


def _profiles_sig(d: Path) -> float:
    """Newest mtime across profile files (ignoring UI state), for hot-reload."""
    try:
        return max(
            (f.stat().st_mtime for f in d.glob("*.json") if f.name != "_state.json"),
            default=0.0,
        )
    except OSError:
        return 0.0


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
        if not engine.set_pin(args.pin):
            print(f"warning: no profile matches --pin {args.pin!r}",
                  file=sys.stderr)
    injector = Injector()

    try:
        while True:
            devs = find_pads(cfg)
            if not devs:
                print("pad not connected (USB or Bluetooth); waiting...",
                      file=sys.stderr)
                time.sleep(1.0)
                continue
            print("connected: " + ", ".join(
                f"{d.path} ({d.name})" for d in devs))
            sel = selectors.DefaultSelector()
            grabbed: list = []
            try:
                for d in devs:
                    try:
                        d.grab()
                        grabbed.append(d)
                        sel.register(d.fd, selectors.EVENT_READ, d)
                    except OSError as e:
                        print(f"grab failed on {d.path}: {e}",
                              file=sys.stderr)
                last_sig = _profiles_sig(args.profiles)
                while True:
                    for key, _ in sel.select(timeout=1.0):
                        dev = key.data
                        for ev in dev.read():
                            handle(ev, engine, injector)
                    sig = _profiles_sig(args.profiles)
                    if sig != last_sig:
                        last_sig = sig
                        engine.reload()
                        print("profiles reloaded (file changed)")
            except (OSError, IOError):
                print("pad disconnected; re-scanning...", file=sys.stderr)
                time.sleep(0.5)
            finally:
                sel.close()
                for d in grabbed:
                    try:
                        d.ungrab()
                    except Exception:
                        pass
    except KeyboardInterrupt:
        pass
    finally:
        injector.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

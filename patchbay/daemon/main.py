"""Patchbay daemon: grab the CH57x pad (USB or Bluetooth), decode surrogate
keys, resolve the active profile + layer, and inject the mapped action.

    python -m patchbay.daemon --profiles profiles/ [--detect] [--pin KiCad]

The daemon supervises the connection: if the pad is unplugged or switches
transport (USB -> Bluetooth), it re-acquires automatically.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

import selectors

from evdev import ecodes

from .surrogates import DECODE
from .engine import Engine
from .executors import Injector
from .discovery import find_pads, scan
from ..core.device_config import PadConfig
from ..core.profile import load_profiles


def handle(ev, engine: Engine, injector: Injector) -> None:
    """Decode one surrogate event and inject the mapped action.

    Each surrogate code already encodes the control AND the hardware layer (the
    pad's side button cycles the layer), so the layer is read off the code —
    no modifier tracking, no reserved buttons, no software layer cycling."""
    if ev.type != ecodes.EV_KEY or ev.value == 0:
        return
    target = DECODE.get(ev.code)
    if not target:
        return
    if target[0] == "key":
        _, kid, layer = target
        engine.layer = layer
        action = engine.action_for_key(kid)
        label = kid
    else:
        _, eid, gesture = target
        action = engine.action_for_encoder(eid, gesture)
        label = f"{eid}/{gesture}"
    prof = engine.active_profile()
    pname = prof.name if prof else "(no profile)"
    if action is not None:
        print(f"[{pname} L{engine.layer + 1}] {label} -> {action.summary()}")
        injector.execute(action)
    else:
        print(f"[{pname} L{engine.layer + 1}] {label} -> (unbound)")


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


class Daemon:
    """The pad-reading loop, runnable in the main thread (CLI) or a background
    thread (tray app). `stop()` ends it cleanly; the read loop polls every 1s
    so it notices the stop flag promptly."""

    def __init__(self, profiles_dir: Path | str = "profiles",
                 pin: str | None = None) -> None:
        self.profiles_dir = Path(profiles_dir)
        self.pin = pin
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.engine: Engine | None = None
        self.injector: Injector | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run,
                                        name="patchbay-daemon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def run(self) -> None:
        cfg = PadConfig.load()
        engine = Engine(self.profiles_dir)
        if self.pin and not engine.set_pin(self.pin):
            print(f"warning: no profile matches --pin {self.pin!r}",
                  file=sys.stderr)
        injector = Injector()
        self.engine, self.injector = engine, injector
        try:
            while not self._stop.is_set():
                devs = find_pads(cfg)
                if not devs:
                    print("pad not connected (USB or Bluetooth); waiting...",
                          file=sys.stderr)
                    self._stop.wait(1.0)
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
                    last_sig = _profiles_sig(self.profiles_dir)
                    while not self._stop.is_set():
                        for key, _ in sel.select(timeout=1.0):
                            dev = key.data
                            for ev in dev.read():
                                handle(ev, engine, injector)
                        sig = _profiles_sig(self.profiles_dir)
                        if sig != last_sig:
                            last_sig = sig
                            engine.reload()
                            print("profiles reloaded (file changed)")
                except (OSError, IOError):
                    print("pad disconnected; re-scanning...", file=sys.stderr)
                    self._stop.wait(0.5)
                finally:
                    sel.close()
                    for d in grabbed:
                        try:
                            d.ungrab()
                        except Exception:
                            pass
        finally:
            injector.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="patchbay-daemon")
    ap.add_argument("--profiles", default="profiles", type=Path)
    ap.add_argument("--pin", default=None, help="pin a profile by name/app")
    ap.add_argument("--detect", action="store_true",
                    help="list candidate devices and exit")
    args = ap.parse_args(argv)

    if args.detect:
        return detect()

    d = Daemon(args.profiles, args.pin)
    try:
        d.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

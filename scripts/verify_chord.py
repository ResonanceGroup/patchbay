#!/usr/bin/env python3
"""Prove the daemon's injection path: synthesize a modifier chord on a uinput
virtual keyboard and read the events back off the kernel, so we can see the
modifiers held down and released around the key. Run as root (uinput)."""
import time
from evdev import ecodes, InputDevice, categorize, list_devices

from patchbay.daemon.executors import Injector

CHORD = ["ctrl", "alt", "shift", "z"]


def find_loopback(name, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        for path in list_devices():
            try:
                d = InputDevice(path)
            except OSError:
                continue
            if d.name == name:
                return d
        time.sleep(0.1)
    return None


def main():
    inj = Injector()
    dev = find_loopback("patchbay")
    if dev is None:
        print("loopback device not found"); return 1
    print(f"virtual keyboard: {dev.path} ({dev.name})")

    dev.grab()  # so our own reader sees the events first
    inj.press_chord(CHORD)
    time.sleep(0.05)
    events = list(dev.read())
    dev.ungrab()

    print("\nkernel event stream for", "+".join(CHORD), ":")
    for e in events:
        if e.type == ecodes.EV_KEY:
            c = categorize(e)
            state = "DOWN" if e.value == 1 else "UP"
            print(f"  {state:4}  {c.scancode}")
    inj.close()

    downs = [e for e in events if e.type == ecodes.EV_KEY and e.value == 1]
    ups = [e for e in events if e.type == ecodes.EV_KEY and e.value == 0]
    print(f"\n{len(downs)} key-downs, {len(ups)} key-ups "
          f"(balanced: {len(downs) == len(ups)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

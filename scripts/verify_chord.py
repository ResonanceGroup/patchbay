#!/usr/bin/env python3
"""Prove the daemon's injection path: synthesize a modifier chord on a uinput
virtual keyboard and read the events back off the kernel, so we can see the
modifiers held down and released around the key. Run as root (uinput)."""
import sys
from evdev import ecodes, InputDevice, categorize

from patchbay.daemon.executors import Injector

CHORD = ["ctrl", "alt", "shift", "z"]

def main():
    inj = Injector()
    # the uinput device loops back as a real /dev/input node we can read
    dev = InputDevice(inj.ui.devnode)
    print(f"virtual keyboard: {inj.ui.devnode} ({dev.name})")

    inj.press_chord(CHORD)
    inj.tap_media("play_pause")

    events = list(dev.read())
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

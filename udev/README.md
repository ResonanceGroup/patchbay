# udev rules

`99-patchbay-pad.rules` grants the `input` group read/write on the pad's
Bluetooth raw-HID (hidraw) node so the daemon can read surrogate reports as a
normal user (no root). Install with:

    sudo cp udev/99-patchbay-pad.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=hidraw --action=add

The user running the daemon must be in the `input` group. A companion rule for
uinput (the injector) and the USB pad lives in `/etc/udev/rules.d/99-patchbay.rules`.

"""Firmware CLI.

    python -m patchbay.firmware surrogate            # write fixed daemon config
    python -m patchbay.firmware direct KiCad         # write one profile's config
    python -m patchbay.firmware validate <file.yaml> # offline schema check
    python -m patchbay.firmware upload <file.yaml>   # write to the pad
    python -m patchbay.firmware show-keys            # key names the tool accepts
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compile import build_surrogate_config, build_direct_config, to_yaml
from . import tool
from ..core.profile import load_profiles

OUT_DIR = Path("firmware_out")


def _write(config: dict, name: str) -> Path:
    OUT_DIR.mkdir(exist_ok=True)
    p = OUT_DIR / f"{name}.yaml"
    p.write_text(to_yaml(config))
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="patchbay-firmware")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("surrogate")
    d = sub.add_parser("direct")
    d.add_argument("profile", help="profile name or app")
    d.add_argument("--profiles", default="profiles", type=Path)
    v = sub.add_parser("validate"); v.add_argument("file", type=Path)
    u = sub.add_parser("upload"); u.add_argument("file", type=Path)
    sub.add_parser("show-keys")
    args = ap.parse_args(argv)

    if args.cmd == "surrogate":
        p = _write(build_surrogate_config(), "surrogate")
        print(f"wrote {p}")
        return 0
    if args.cmd == "direct":
        for pr in load_profiles(args.profiles):
            if pr.name == args.profile or pr.app == args.profile:
                p = _write(build_direct_config(pr), pr.name.lower().replace(" ", "-"))
                print(f"wrote {p}")
                return 0
        print(f"no profile named {args.profile!r}", file=sys.stderr)
        return 1
    if args.cmd == "validate":
        r = tool.validate(args.file)
        print(r.message or ("valid" if r.ok else "invalid"))
        return 0 if r.ok else 1
    if args.cmd == "upload":
        r = tool.upload(args.file)
        print(r.message or ("uploaded" if r.ok else "upload failed"))
        return 0 if r.ok else 1
    if args.cmd == "show-keys":
        r = tool.show_keys()
        print(r.message)
        return 0 if r.ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Drive the external ch57x-keyboard-tool (kriomant) for validate/upload.

The tool is a separate Rust binary; Patchbay never talks to the device's
programming protocol directly. We only shell out to it. USB id 1189:8890.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BIN = "ch57x-keyboard-tool"


def find_binary(explicit: str | None = None) -> str | None:
    """Resolve the tool binary: explicit path, $PATCHBAY_CH57X_TOOL, or PATH."""
    for cand in (explicit, os.environ.get("PATCHBAY_CH57X_TOOL")):
        if cand and Path(cand).exists():
            return cand
    return shutil.which(DEFAULT_BIN)


@dataclass
class ToolResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int

    @property
    def message(self) -> str:
        return (self.stdout or self.stderr).strip()


def _run(binary: str, args: list[str], timeout: int = 30) -> ToolResult:
    try:
        p = subprocess.run([binary, *args], capture_output=True, text=True,
                           timeout=timeout)
        return ToolResult(p.returncode == 0, p.stdout, p.stderr, p.returncode)
    except FileNotFoundError:
        return ToolResult(False, "", f"tool not found: {binary}", 127)
    except subprocess.TimeoutExpired:
        return ToolResult(False, "", f"tool timed out after {timeout}s", 124)


def validate(config_path: Path, binary: str | None = None) -> ToolResult:
    """Offline schema check — needs no device."""
    b = find_binary(binary)
    if not b:
        return ToolResult(False, "", "ch57x-keyboard-tool not installed", 127)
    return _run(b, ["validate", str(config_path)])


def upload(config_path: Path, binary: str | None = None) -> ToolResult:
    """Write the config to the connected pad. Requires the device plugged in.

    The tool reads the config from a file argument on newer versions and from
    stdin on older ones; try the file form, fall back to stdin."""
    b = find_binary(binary)
    if not b:
        return ToolResult(False, "", "ch57x-keyboard-tool not installed", 127)
    res = _run(b, ["upload", str(config_path)], timeout=60)
    if not res.ok and "usage" in (res.stderr or "").lower():
        text = config_path.read_text()
        try:
            p = subprocess.run([b, "upload"], input=text, capture_output=True,
                               text=True, timeout=60)
            return ToolResult(p.returncode == 0, p.stdout, p.stderr,
                              p.returncode)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return ToolResult(False, "", str(e), 124)
    return res


def show_keys(binary: str | None = None) -> ToolResult:
    """List the key names the installed tool accepts (ground truth for the
    action compiler)."""
    b = find_binary(binary)
    if not b:
        return ToolResult(False, "", "ch57x-keyboard-tool not installed", 127)
    return _run(b, ["show-keys"])

"""Show whether the launch agent is loaded and running."""

from __future__ import annotations

import os
import re
import subprocess

from ._paths import LABEL, require_macos

_FIELDS = re.compile(r"^\s*(state|pid|path|program)\s")


def run() -> int:
    require_macos()

    target = f"gui/{os.getuid()}/{LABEL}"
    p = subprocess.run(
        ["launchctl", "print", target],
        check=False, capture_output=True, text=True,
    )
    combined = (p.stdout or "") + (p.stderr or "")
    matched = [line for line in combined.splitlines() if _FIELDS.match(line)]
    if not matched:
        print("not loaded")
        return 0
    print("\n".join(matched))
    return 0

"""Tail the launch agent's combined stdout/stderr log."""

from __future__ import annotations

import os
import sys

from ._paths import LOG_PATH, require_macos


def run() -> int:
    require_macos()

    if not LOG_PATH.exists():
        print(f"{LOG_PATH} does not exist yet; install the agent first.", file=sys.stderr)
        return 1
    os.execvp("tail", ["tail", "-f", str(LOG_PATH)])

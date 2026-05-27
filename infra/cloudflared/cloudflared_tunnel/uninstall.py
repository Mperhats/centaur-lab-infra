"""Boot out the launch agent and remove its plist."""

from __future__ import annotations

import os
import subprocess

from ._paths import LABEL, LAUNCH_AGENT_PLIST, require_macos


def run(*, yes: bool = False) -> int:
    require_macos()

    if not yes:
        reply = input(
            f"Uninstall the {LABEL} launch agent? [y/N] "
        ).strip().lower()
        if reply not in ("y", "yes"):
            print("aborted.")
            return 1

    target = f"gui/{os.getuid()}/{LABEL}"
    subprocess.run(
        ["launchctl", "bootout", target],
        check=False, capture_output=True, text=True,
    )
    LAUNCH_AGENT_PLIST.unlink(missing_ok=True)
    print(f"uninstalled {LABEL}")
    return 0

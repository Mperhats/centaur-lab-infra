"""Foreground run for debugging.

Uninstall the launch agent first to avoid a connector race
(`uv run tunnel uninstall --yes`).
"""

from __future__ import annotations

import os
import shutil
import sys

from ._paths import CONFIG_PATH, TUNNEL_NAME


def run() -> int:
    cloudflared_bin = shutil.which("cloudflared")
    if not cloudflared_bin:
        print(
            "cloudflared not on PATH; run 'brew install cloudflared' first.",
            file=sys.stderr,
        )
        return 1
    os.execvp(
        cloudflared_bin,
        [
            "cloudflared", "tunnel",
            "--config", str(CONFIG_PATH),
            "run", TUNNEL_NAME,
        ],
    )

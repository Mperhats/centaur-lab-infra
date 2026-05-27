"""Filesystem locations + shared constants for the tunnel agent commands.

Workspace members are installed editable, so `__file__` resolves into the
checked-out repo and we can locate `config.yml` / the plist template by
walking one level up from this module's package.
"""

from __future__ import annotations

import sys
from pathlib import Path

LABEL = "com.local-labs.centaur-tunnel"
TUNNEL_NAME = "centaur-dev"

ASSETS_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ASSETS_DIR / "config.yml"
PLIST_TEMPLATE = ASSETS_DIR / f"{LABEL}.plist"

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCH_AGENT_PLIST = LAUNCH_AGENTS_DIR / f"{LABEL}.plist"
LOG_DIR = Path.home() / "Library" / "Logs"
LOG_PATH = LOG_DIR / "centaur-tunnel.log"


def require_macos() -> None:
    """Exit early on non-macOS — launchd is the only supported supervisor."""
    if sys.platform != "darwin":
        print(
            "tunnel: launchd commands only run on macOS; "
            "write a [linux] systemd-user-unit sibling when needed.",
            file=sys.stderr,
        )
        sys.exit(2)

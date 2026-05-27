"""Install the Cloudflare Tunnel as a launchd user agent that auto-starts on login."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from ._paths import (
    CONFIG_PATH,
    LABEL,
    LAUNCH_AGENT_PLIST,
    LAUNCH_AGENTS_DIR,
    LOG_DIR,
    LOG_PATH,
    PLIST_TEMPLATE,
    require_macos,
)


def run() -> int:
    require_macos()

    cloudflared_bin = shutil.which("cloudflared")
    if not cloudflared_bin:
        print(
            "cloudflared not on PATH; run 'brew install cloudflared' first.",
            file=sys.stderr,
        )
        return 1
    if not CONFIG_PATH.is_file():
        print(
            f"missing {CONFIG_PATH}; see infra/cloudflared/README.md "
            "for one-time setup.",
            file=sys.stderr,
        )
        return 1

    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    rendered = (
        PLIST_TEMPLATE.read_text()
        .replace("__TUNNEL_BIN__", cloudflared_bin)
        .replace("__CONFIG_PATH__", str(CONFIG_PATH))
        .replace("__LOG_PATH__", str(LOG_PATH))
    )
    LAUNCH_AGENT_PLIST.write_text(rendered)

    target = f"gui/{os.getuid()}/{LABEL}"
    subprocess.run(
        ["launchctl", "bootout", target],
        check=False, capture_output=True, text=True,
    )
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(LAUNCH_AGENT_PLIST)],
        check=True,
    )
    print(f"installed {LABEL}; logs at {LOG_PATH}")
    return 0

"""Manage the Cloudflare Tunnel launchd agent for centaur-lab.

Single console-script entry point (`tunnel`) that fans out to the
per-action subcommands. Mirrors the verb-based UX of the rest of the
repo (`uv run up`, `uv run sync`, ...) — `uv run tunnel install`,
`uv run tunnel status`, etc.
"""

from __future__ import annotations

import argparse
import sys

from . import install, logs, run, status, uninstall


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tunnel", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    sub.add_parser("install", help="install/re-install the launchd agent")

    p_uninstall = sub.add_parser(
        "uninstall", help="boot out the launch agent and remove its plist",
    )
    p_uninstall.add_argument(
        "-y", "--yes", action="store_true",
        help="skip the confirmation prompt",
    )

    sub.add_parser("status", help="show whether the agent is loaded and running")
    sub.add_parser("logs", help="tail ~/Library/Logs/centaur-tunnel.log")
    sub.add_parser("run", help="foreground run for debugging (uninstall first)")

    args = parser.parse_args(argv)

    if args.cmd == "install":
        return install.run()
    if args.cmd == "uninstall":
        return uninstall.run(yes=args.yes)
    if args.cmd == "status":
        return status.run()
    if args.cmd == "logs":
        return logs.run()
    if args.cmd == "run":
        return run.run()
    return 1


if __name__ == "__main__":
    sys.exit(main())

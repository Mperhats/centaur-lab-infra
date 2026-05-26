"""Apply local Application changes, hard-refresh Argo CD, wait for rollout.

Use after editing bootstrap/centaur.yaml or values/centaur.yaml.

Snapshots .status.reconciledAt before refresh so we don't return on a
stale Synced/Healthy from the previous reconcile.
"""

from __future__ import annotations

import argparse
import sys

from ._common import BOOTSTRAP_DIR, argo_status, kubectl, wait_for_sync

APP_FILE = BOOTSTRAP_DIR / "centaur.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sync", description=__doc__)
    parser.add_argument(
        "--no-apply", action="store_true",
        help="skip kubectl apply (refresh + wait only)",
    )
    args = parser.parse_args(argv)

    _, _, prev_reconciled = argo_status()

    if not args.no_apply:
        kubectl("apply", "-f", str(APP_FILE))

    kubectl(
        "-n", "argocd", "annotate", "application/centaur",
        "argocd.argoproj.io/refresh=hard", "--overwrite",
        capture=True,
    )

    return wait_for_sync(prev_reconciled)


if __name__ == "__main__":
    sys.exit(main())

"""Tear down centaur. Argo CD itself is preserved.

`--hard` also drops the namespace + cluster Secrets. Postgres data
(PVC) is destroyed. .env on disk is untouched.
"""

from __future__ import annotations

import argparse
import sys

from ._common import NAMESPACE, kubectl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="down", description=__doc__)
    parser.add_argument(
        "--hard", action="store_true",
        help="also delete the centaur namespace + PVCs",
    )
    args = parser.parse_args(argv)

    rc = kubectl(
        "-n", "argocd", "delete", "application", "centaur",
        "--ignore-not-found", "--timeout=2m",
        check=False,
    ).returncode
    if rc != 0:
        print(
            "Application delete timed out — check finalizers", file=sys.stderr,
        )

    if args.hard:
        kubectl(
            "delete", "namespace", NAMESPACE,
            "--ignore-not-found", "--timeout=2m",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

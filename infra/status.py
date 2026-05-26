"""Quick at-a-glance view of cluster + centaur health."""

from __future__ import annotations

import sys

from ._common import NAMESPACE, argo_status, kubectl


def main() -> int:
    print("=== Argo CD Application ===")
    sync, health, reconciled = argo_status()
    if sync:
        print(f"Sync: {sync}    Health: {health}    ReconciledAt: {reconciled}")
    else:
        print("(application not found — run `uv run up`)")

    print()
    print(f"=== Pods in {NAMESPACE} ===")
    kubectl("-n", NAMESPACE, "get", "pods", check=False)

    print()
    print(f"=== Sandboxes in {NAMESPACE} ===")
    kubectl("-n", NAMESPACE, "get", "sandboxes", check=False)

    print()
    print("=== API health ===")
    rc = kubectl(
        "-n", NAMESPACE, "exec", "deploy/centaur-centaur-api", "--",
        "curl", "-fsS", "--max-time", "5", "http://localhost:8000/health",
        check=False,
    ).returncode
    if rc != 0:
        print("(api unreachable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

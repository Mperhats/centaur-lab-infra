"""Garbage-collect leaked pods + sandboxes from the centaur namespace.

Default behaviour:
- Pods in phase Failed or Succeeded (terminal phases)
- Pods stuck Terminating > 60s (force-deleted with grace=0)
- Sandboxes whose underlying Pod no longer exists (orphaned)

The agent-sandbox CRD doesn't expose a `.status.phase`; the heuristic
"sandbox name == pod name, pod is gone" matches the upstream controller's
naming today. `--all-sandboxes` is the escape hatch.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

from ._common import NAMESPACE, kubectl, kubectl_json


def _terminating_for_too_long(pods: list[dict], now: dt.datetime, threshold_s: int = 60) -> list[str]:
    out = []
    for p in pods:
        ts = p["metadata"].get("deletionTimestamp")
        if not ts:
            continue
        deleted_at = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if (now - deleted_at).total_seconds() > threshold_s:
            out.append(p["metadata"]["name"])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="clean", description=__doc__)
    parser.add_argument(
        "--all-sandboxes", action="store_true",
        help="delete every sandbox (incl. Running) — use after a stuck agent run",
    )
    args = parser.parse_args(argv)

    print("=== Pods (Failed / Succeeded) ===")
    kubectl(
        "-n", NAMESPACE, "delete", "pods",
        "--field-selector=status.phase=Failed", "--ignore-not-found",
    )
    kubectl(
        "-n", NAMESPACE, "delete", "pods",
        "--field-selector=status.phase=Succeeded", "--ignore-not-found",
    )

    print()
    print("=== Pods stuck Terminating > 60s ===")
    pods = kubectl_json("-n", NAMESPACE, "get", "pods").get("items", [])
    for name in _terminating_for_too_long(pods, dt.datetime.now(dt.timezone.utc)):
        kubectl(
            "-n", NAMESPACE, "delete", "pod", name,
            "--force", "--grace-period=0", check=False,
        )

    print()
    print("=== Sandboxes ===")
    if args.all_sandboxes:
        kubectl(
            "-n", NAMESPACE, "delete", "sandboxes", "--all", "--ignore-not-found",
        )
    else:
        alive = {p["metadata"]["name"] for p in pods}
        sandboxes = kubectl_json("-n", NAMESPACE, "get", "sandboxes").get("items", [])
        for s in sandboxes:
            name = s["metadata"]["name"]
            if name not in alive:
                kubectl(
                    "-n", NAMESPACE, "delete", "sandbox", name, check=False,
                )

    print()
    print("=== Result ===")
    kubectl("-n", NAMESPACE, "get", "pods,sandboxes", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())

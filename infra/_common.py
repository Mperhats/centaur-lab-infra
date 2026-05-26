"""Shared helpers used by every infra command."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = os.environ.get("CENTAUR_NAMESPACE", "centaur-system")
BOOTSTRAP_DIR = REPO_ROOT / "clusters/centaur-lab/argocd/bootstrap"


def run(*args: str, check: bool = True, capture: bool = False, **kwargs) -> subprocess.CompletedProcess[str]:
    """subprocess.run with sane defaults: text=True, list-of-args.

    Flushes stdout/stderr first so our prints stay in order with the
    subprocess's own output (which writes directly to the tty).
    """
    sys.stdout.flush()
    sys.stderr.flush()
    return subprocess.run(
        list(args), check=check, text=True, capture_output=capture, **kwargs
    )


def kubectl(*args: str, **kwargs) -> subprocess.CompletedProcess[str]:
    """Run `kubectl ...` with the same defaults as `run`."""
    return run("kubectl", *args, **kwargs)


def ensure_namespace(name: str) -> None:
    """Idempotently create a namespace via dry-run + apply (server-managed)."""
    yaml = kubectl(
        "create", "namespace", name,
        "--dry-run=client", "-o", "yaml", capture=True,
    ).stdout
    kubectl("apply", "-f", "-", input=yaml, capture=True)


def kubectl_json(*args: str) -> dict:
    """`kubectl get ... -o json` -> parsed dict ({} if the resource is missing).

    Pass everything after `kubectl`, e.g. `kubectl_json("-n", ns, "get", "pods")`.
    """
    out = kubectl(*args, "-o", "json", check=False, capture=True).stdout
    return json.loads(out) if out else {}


def argo_status() -> tuple[str, str, str]:
    """Return (sync, health, reconciledAt) for the centaur Application.

    Empty strings if the App doesn't exist yet (pre-bootstrap).
    """
    p = kubectl(
        "-n", "argocd", "get", "application", "centaur",
        "-o", "jsonpath={.status.sync.status}|{.status.health.status}|{.status.reconciledAt}",
        check=False, capture=True,
    )
    parts = (p.stdout or "").split("|")
    while len(parts) < 3:
        parts.append("")
    return parts[0], parts[1], parts[2]


def wait_for_sync(prev_reconciled: str, timeout_s: int = 600, interval_s: int = 5) -> int:
    """Poll until reconciledAt advances past `prev_reconciled` AND status is Synced/Healthy.

    Avoids the stale-status race: a fresh `kubectl apply` doesn't change
    `.status` immediately, so checking sync/health on the first poll can
    return a stale Synced/Healthy from the previous reconcile.

    Returns 0 on success, 1 on timeout.
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        sync, health, reconciled = argo_status()
        elapsed = int(time.monotonic() - start) or interval_s
        print(f"  [{elapsed:3d}s] {sync}/{health}  reconciledAt={reconciled or '?'}")
        if (
            reconciled
            and reconciled != prev_reconciled
            and sync == "Synced"
            and health == "Healthy"
        ):
            return 0
        time.sleep(interval_s)

    print(
        f"Timed out after {timeout_s // 60}m waiting for Synced/Healthy with fresh reconcile",
        file=sys.stderr,
    )
    kubectl(
        "-n", "argocd", "get", "application", "centaur",
        "-o", "jsonpath={.status.conditions}",
        check=False,
    )
    return 1

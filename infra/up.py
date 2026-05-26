"""One-shot cluster bring-up: Argo CD + cm patches + secrets + centaur App.

Idempotent — safe to re-run after partial bootstraps.
"""

from __future__ import annotations

import sys

from . import secrets as secrets_cmd
from . import sync as sync_cmd
from ._common import BOOTSTRAP_DIR, ensure_namespace, kubectl

ARGOCD_INSTALL_URL = (
    "https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"
)


def main() -> int:
    # 1. Argo CD itself
    argocd_present = kubectl(
        "-n", "argocd", "get", "deploy", "argocd-server",
        check=False, capture=True,
    ).returncode == 0
    if not argocd_present:
        ensure_namespace("argocd")
        kubectl(
            "apply", "-n", "argocd", "--server-side", "--force-conflicts",
            "-f", ARGOCD_INSTALL_URL,
        )
    kubectl("-n", "argocd", "rollout", "status", "deploy/argocd-server", "--timeout=5m")

    # 2. argocd-cm patches FIRST — required so postgres StatefulSet doesn't
    #    drift-loop the moment the centaur App lands.
    kubectl("apply", "-f", str(BOOTSTRAP_DIR / "argocd-cm-patches.yaml"))
    kubectl(
        "-n", "argocd", "rollout", "restart",
        "sts/argocd-application-controller", "deploy/argocd-server",
        capture=True,
    )
    kubectl(
        "-n", "argocd", "rollout", "status",
        "sts/argocd-application-controller", "--timeout=2m",
    )
    kubectl("-n", "argocd", "rollout", "status", "deploy/argocd-server", "--timeout=2m")

    # 3. Cluster secrets from .env
    rc = secrets_cmd.main()
    if rc:
        return rc

    # 4. Application
    kubectl("apply", "-f", str(BOOTSTRAP_DIR / "00-namespaces.yaml"))
    kubectl("apply", "-f", str(BOOTSTRAP_DIR / "centaur.yaml"))

    # 5. Wait for the App to converge using the same logic as `sync`.
    print("Waiting for centaur Application to become Synced/Healthy...")
    return sync_cmd.main(["--no-apply"])


if __name__ == "__main__":
    sys.exit(main())

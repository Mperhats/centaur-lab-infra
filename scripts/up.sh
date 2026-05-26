#!/usr/bin/env bash
# One-shot cluster bring-up: Argo CD + cm patches + secrets + centaur App.
# Idempotent — safe to re-run after partial bootstraps.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP="$REPO_ROOT/clusters/centaur-lab/argocd/bootstrap"

# 1. Argo CD
if ! kubectl -n argocd get deploy argocd-server >/dev/null 2>&1; then
  kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
  kubectl apply -n argocd --server-side --force-conflicts \
    -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
fi
kubectl -n argocd rollout status deploy/argocd-server --timeout=5m

# 2. argocd-cm patches (must precede App so postgres StatefulSet doesn't drift-loop)
kubectl apply -f "$BOOTSTRAP/argocd-cm-patches.yaml"
kubectl -n argocd rollout restart sts/argocd-application-controller deploy/argocd-server >/dev/null
kubectl -n argocd rollout status sts/argocd-application-controller --timeout=2m
kubectl -n argocd rollout status deploy/argocd-server --timeout=2m

# 3. Cluster secrets from .env
"$REPO_ROOT/scripts/bootstrap-secrets.sh"

# 4. Application
kubectl apply -f "$BOOTSTRAP/00-namespaces.yaml"
kubectl apply -f "$BOOTSTRAP/centaur.yaml"

# 5. Wait for Synced + Healthy
echo "Waiting for centaur Application to become Synced/Healthy..."
"$REPO_ROOT/scripts/sync.sh" --no-apply

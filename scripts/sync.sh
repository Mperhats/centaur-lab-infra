#!/usr/bin/env bash
# Apply local Application changes, hard-refresh Argo CD, wait for rollout.
# Use after editing bootstrap/centaur.yaml or values/centaur.yaml.
#
# Avoids the stale-status race by snapshotting `.status.reconciledAt`
# before refresh and waiting until it advances AND Sync/Health are good.
#
# Flags:
#   --no-apply   skip the kubectl apply step (just refresh + wait)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_FILE="$REPO_ROOT/clusters/centaur-lab/argocd/bootstrap/centaur.yaml"

prev_reconciled=$(kubectl -n argocd get application centaur \
  -o jsonpath='{.status.reconciledAt}' 2>/dev/null || true)

if [[ "${1:-}" != "--no-apply" ]]; then
  kubectl apply -f "$APP_FILE"
fi
kubectl -n argocd annotate application/centaur \
  argocd.argoproj.io/refresh=hard --overwrite >/dev/null

for i in $(seq 1 120); do
  cur=$(kubectl -n argocd get application centaur \
    -o jsonpath='{.status.reconciledAt}' 2>/dev/null || true)
  s=$(kubectl -n argocd get application centaur \
    -o jsonpath='{.status.sync.status}/{.status.health.status}' 2>/dev/null || true)
  printf '  [%3ds] %s  reconciledAt=%s\n' "$((i*5))" "$s" "${cur:-?}"
  if [[ "$cur" != "$prev_reconciled" && "$s" == "Synced/Healthy" ]]; then
    exit 0
  fi
  sleep 5
done

echo "Timed out after 10m waiting for Synced/Healthy with fresh reconcile" >&2
kubectl -n argocd get application centaur \
  -o jsonpath='{.status.conditions}{"\n"}' >&2
exit 1

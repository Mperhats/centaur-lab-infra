#!/usr/bin/env bash
# Quick at-a-glance view of cluster + centaur health.
set -euo pipefail

NS="${CENTAUR_NAMESPACE:-centaur-system}"

echo "=== Argo CD Application ==="
kubectl -n argocd get application centaur \
  -o jsonpath='Sync: {.status.sync.status}    Health: {.status.health.status}    Revision: {.status.sync.revision}{"\n"}' \
  2>/dev/null || echo "(application not found — run scripts/up.sh)"

echo
echo "=== Pods in $NS ==="
kubectl -n "$NS" get pods 2>/dev/null || echo "(namespace missing)"

echo
echo "=== Sandboxes in $NS ==="
kubectl -n "$NS" get sandboxes 2>/dev/null || echo "(none)"

echo
echo "=== API health ==="
kubectl -n "$NS" exec deploy/centaur-centaur-api -- \
  curl -fsS --max-time 5 http://localhost:8000/health 2>/dev/null \
  || echo "(api unreachable)"

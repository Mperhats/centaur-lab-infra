#!/usr/bin/env bash
# Tear down centaur. Argo CD itself is preserved.
#
# Flags:
#   --hard   also delete the centaur namespace + cluster Secrets.
#            Postgres data (PVC) is destroyed. .env on disk is untouched.
set -euo pipefail

NS="${CENTAUR_NAMESPACE:-centaur-system}"

kubectl -n argocd delete application centaur --ignore-not-found --timeout=2m \
  || echo "Application delete timed out — check finalizers" >&2

if [[ "${1:-}" == "--hard" ]]; then
  kubectl delete namespace "$NS" --ignore-not-found --timeout=2m
fi

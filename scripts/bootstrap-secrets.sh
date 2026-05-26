#!/usr/bin/env bash
# Reads .env and creates centaur-infra-env + firewall CA secrets.
# .env IS the schema — every `export KEY=` line becomes a Secret entry,
# except keys in SKIP_KEYS (tooling-only, not part of the cluster Secret).
# Idempotent (uses kubectl apply).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
[[ -f "$ENV_FILE" ]] || { echo "FATAL: $ENV_FILE not found. cp .env.example .env, then edit." >&2; exit 1; }

set -a; source "$ENV_FILE"; set +a

NAMESPACE="${CENTAUR_NAMESPACE:-centaur-system}"
SKIP_KEYS=(CENTAUR_NAMESPACE)

literal_args=()
while IFS= read -r line; do
  [[ "$line" =~ ^export[[:space:]]+([A-Z_][A-Z0-9_]*)= ]] || continue
  key="${BASH_REMATCH[1]}"
  for skip in "${SKIP_KEYS[@]}"; do
    [[ "$key" == "$skip" ]] && continue 2
  done
  literal_args+=(--from-literal="$key=${!key:-}")
done < "$ENV_FILE"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl -n "$NAMESPACE" create secret generic centaur-infra-env \
  "${literal_args[@]}" \
  --dry-run=client -o yaml | kubectl apply -f -

# Self-signed firewall CA — created only if missing (long-lived, do NOT
# regenerate casually; iron-proxy clients will reject the new cert).
if ! kubectl -n "$NAMESPACE" get secret centaur-firewall-ca >/dev/null 2>&1; then
  d=$(mktemp -d) && trap 'rm -rf "$d"' EXIT
  openssl req -x509 -newkey rsa:4096 -nodes -days 3650 \
    -keyout "$d/ca-key.pem" -out "$d/ca-cert.pem" \
    -subj "/CN=centaur-firewall-ca/O=centaur-lab" 2>/dev/null
  kubectl -n "$NAMESPACE" create secret generic centaur-firewall-ca \
    --from-file=ca-cert.pem="$d/ca-cert.pem"
  kubectl -n "$NAMESPACE" create secret generic centaur-firewall-ca-key \
    --from-file=ca-cert.pem="$d/ca-cert.pem" \
    --from-file=ca-key.pem="$d/ca-key.pem"
fi

echo "Done. Secrets in $NAMESPACE:"
kubectl -n "$NAMESPACE" get secret centaur-infra-env centaur-firewall-ca centaur-firewall-ca-key

#!/usr/bin/env bash
# bootstrap-secrets.sh — create the cluster-side Secrets the Centaur Helm
# chart expects in env mode (`ironProxy.secretSource: env`).
#
# Reads .env from the repo root for credentials, generates random hex for
# keys that don't need to be human-provided, and writes:
#   - centaur-infra-env       (api/iron-proxy/slackbot envFrom source)
#   - centaur-firewall-ca     (self-signed CA cert for iron-proxy MITM)
#   - centaur-firewall-ca-key (matching private key)
#
# Idempotent: skips Secrets that already exist. Pass --force to recreate.
# Self-contained — no dependency on the upstream centaur monorepo.
#
# Usage:
#   ./scripts/bootstrap-secrets.sh                 # safe: creates only what's missing
#   ./scripts/bootstrap-secrets.sh --force         # recreate ALL three secrets
#   ENV_FILE=other.env ./scripts/bootstrap-secrets.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="${CENTAUR_NAMESPACE:-centaur-system}"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --namespace|-n) NAMESPACE="${2:?--namespace requires a value}"; shift 2 ;;
    --help|-h)
      sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed 's/^# \?//; /^set/d'
      exit 0
      ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "FATAL: required command not found: $1" >&2
    exit 1
  fi
}
require_cmd kubectl
require_cmd openssl

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "WARN: $ENV_FILE not found; relying on already-exported shell env" >&2
fi

require_env() {
  local key="$1"
  if [[ -z "${!key:-}" ]]; then
    echo "FATAL: $key is not set. Add it to $ENV_FILE and re-source." >&2
    exit 1
  fi
}
require_env ANTHROPIC_API_KEY
require_env SLACK_BOT_TOKEN
require_env SLACK_SIGNING_SECRET
require_env SLACKBOT_API_KEY
require_env GITHUB_TOKEN

# Auto-generate where reasonable. Caller can pre-set any of these in .env to
# override (useful for cluster rebuilds where you want stable values).
IRON_MANAGEMENT_API_KEY="${IRON_MANAGEMENT_API_KEY:-$(openssl rand -hex 32)}"
SANDBOX_SIGNING_KEY="${SANDBOX_SIGNING_KEY:-$(openssl rand -hex 32)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 32)}"
DATABASE_URL="${DATABASE_URL:-postgresql://tempo:${POSTGRES_PASSWORD}@centaur-centaur-postgres:5432/ai_v2}"

# Optional fields — pass through whatever the user set, default to empty so
# kubectl create secret doesn't choke on unbound vars.
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
SLACK_ETL_TOKEN="${SLACK_ETL_TOKEN:-}"
LOCAL_DEV_API_KEY="${LOCAL_DEV_API_KEY:-}"
SEMANTIC_SCHOLAR_API_KEY="${SEMANTIC_SCHOLAR_API_KEY:-}"
# Vestigial in env mode but the chart's secret-key projection logic still
# expects them to exist; default to random hex if user didn't set them.
OP_SERVICE_ACCOUNT_TOKEN="${OP_SERVICE_ACCOUNT_TOKEN:-$(openssl rand -hex 32)}"
OP_VAULT="${OP_VAULT:-$(openssl rand -hex 32)}"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# === centaur-infra-env =====================================================
if kubectl -n "$NAMESPACE" get secret centaur-infra-env >/dev/null 2>&1 && [[ "$FORCE" != "1" ]]; then
  echo "✓ Secret centaur-infra-env already exists in $NAMESPACE (use --force to recreate)"
else
  kubectl -n "$NAMESPACE" delete secret centaur-infra-env --ignore-not-found >/dev/null
  kubectl -n "$NAMESPACE" create secret generic centaur-infra-env \
    --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" \
    --from-literal=SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN" \
    --from-literal=SLACK_SIGNING_SECRET="$SLACK_SIGNING_SECRET" \
    --from-literal=SLACK_ETL_TOKEN="$SLACK_ETL_TOKEN" \
    --from-literal=SLACKBOT_API_KEY="$SLACKBOT_API_KEY" \
    --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
    --from-literal=LOCAL_DEV_API_KEY="$LOCAL_DEV_API_KEY" \
    --from-literal=SEMANTIC_SCHOLAR_API_KEY="$SEMANTIC_SCHOLAR_API_KEY" \
    --from-literal=OP_SERVICE_ACCOUNT_TOKEN="$OP_SERVICE_ACCOUNT_TOKEN" \
    --from-literal=OP_VAULT="$OP_VAULT" \
    --from-literal=IRON_MANAGEMENT_API_KEY="$IRON_MANAGEMENT_API_KEY" \
    --from-literal=SANDBOX_SIGNING_KEY="$SANDBOX_SIGNING_KEY" \
    --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    --from-literal=DATABASE_URL="$DATABASE_URL" >/dev/null
  echo "✓ Created Secret centaur-infra-env in $NAMESPACE (15 keys)"
fi

# === centaur-firewall-ca + centaur-firewall-ca-key =========================
ca_present() {
  kubectl -n "$NAMESPACE" get secret centaur-firewall-ca >/dev/null 2>&1 \
    && kubectl -n "$NAMESPACE" get secret centaur-firewall-ca-key >/dev/null 2>&1
}

if ca_present && [[ "$FORCE" != "1" ]]; then
  echo "✓ Firewall CA Secrets already exist in $NAMESPACE (use --force to recreate)"
else
  kubectl -n "$NAMESPACE" delete secret centaur-firewall-ca centaur-firewall-ca-key --ignore-not-found >/dev/null
  TMPDIR=$(mktemp -d)
  trap 'rm -rf "$TMPDIR"' EXIT

  openssl genrsa -out "$TMPDIR/ca-key.pem" 4096 2>/dev/null
  openssl req -x509 -new -nodes \
    -key "$TMPDIR/ca-key.pem" \
    -sha256 -days 3650 \
    -subj "/CN=centaur-firewall-ca/O=centaur-lab" \
    -out "$TMPDIR/ca-cert.pem" 2>/dev/null

  # The chart consumes ca-cert.pem from BOTH secrets and ca-key.pem from the
  # *-key secret. Mirror that layout so the iron-proxy CA-bundle init works.
  kubectl -n "$NAMESPACE" create secret generic centaur-firewall-ca \
    --from-file=ca-cert.pem="$TMPDIR/ca-cert.pem" >/dev/null
  kubectl -n "$NAMESPACE" create secret generic centaur-firewall-ca-key \
    --from-file=ca-cert.pem="$TMPDIR/ca-cert.pem" \
    --from-file=ca-key.pem="$TMPDIR/ca-key.pem" >/dev/null
  echo "✓ Created Secrets centaur-firewall-ca + centaur-firewall-ca-key in $NAMESPACE"
fi

cat <<EOF

Bootstrap complete. Continue with Argo CD bootstrap:

  kubectl apply -f clusters/centaur-lab/argocd/bootstrap/argocd-cm-patches.yaml
  kubectl -n argocd rollout restart sts/argocd-application-controller deploy/argocd-server
  kubectl apply -f clusters/centaur-lab/argocd/bootstrap/00-namespaces.yaml
  kubectl apply -f clusters/centaur-lab/argocd/bootstrap/centaur.yaml

EOF

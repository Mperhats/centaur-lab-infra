#!/usr/bin/env bash
# Garbage-collect leaked pods + sandboxes from $NS.
#
# What gets cleaned by default:
#   - Pods in phase Failed or Succeeded (terminal phases)
#   - Pods stuck Terminating > 60s (force-deleted with grace=0)
#   - Sandboxes whose underlying Pod no longer exists (orphaned)
#
# Sandboxes have no `.status.phase` field; the upstream agent-sandbox
# CRD only exposes conditions + service/pod refs. So our "is this
# sandbox finished" heuristic is "the pod backing it is gone".
#
# Flags:
#   --all-sandboxes   also delete sandboxes whose pod is still alive —
#                     use after a stuck agent run; the API will recreate
#                     them as needed.
set -euo pipefail

NS="${CENTAUR_NAMESPACE:-centaur-system}"

echo "=== Pods (Failed / Succeeded) ==="
kubectl -n "$NS" delete pods --field-selector=status.phase=Failed --ignore-not-found
kubectl -n "$NS" delete pods --field-selector=status.phase=Succeeded --ignore-not-found

echo
echo "=== Pods stuck Terminating > 60s ==="
kubectl -n "$NS" get pods -o json 2>/dev/null \
  | python3 -c '
import json, sys, datetime
now = datetime.datetime.now(datetime.timezone.utc)
for p in json.load(sys.stdin).get("items", []):
    ts = p["metadata"].get("deletionTimestamp")
    if not ts:
        continue
    age = (now - datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds()
    if age > 60:
        print(p["metadata"]["name"])' \
  | xargs -r -n1 kubectl -n "$NS" delete pod --force --grace-period=0

echo
echo "=== Sandboxes ==="
if [[ "${1:-}" == "--all-sandboxes" ]]; then
  kubectl -n "$NS" delete sandboxes --all --ignore-not-found
else
  pods=$(kubectl -n "$NS" get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null)
  kubectl -n "$NS" get sandboxes -o json 2>/dev/null \
    | python3 -c "
import json, sys
alive_pods = set(filter(None, '''$pods'''.splitlines()))
for s in json.load(sys.stdin).get('items', []):
    name = s['metadata']['name']
    # Sandbox names match their pod name in agent-sandbox; fall back to
    # checking selector if a future controller version diverges.
    if name not in alive_pods:
        print(name)" \
    | xargs -r -n1 kubectl -n "$NS" delete sandbox
fi

echo
echo "=== Result ==="
kubectl -n "$NS" get pods,sandboxes 2>/dev/null

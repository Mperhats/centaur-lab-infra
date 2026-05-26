# centaur-lab-infra

GitOps for the Centaur deployment in `centaur-system`. Argo CD installs the
upstream chart from `paradigmxyz/centaur` (pinned SHA), reads values from
this repo, and mounts the `centaur-lab` overlay image.

## Bootstrap

```bash
# 1. Apple Silicon only — toggle Rosetta:
#    Docker Desktop → Settings → General → "Use Rosetta for x86_64/amd64
#    emulation on Apple Silicon"

# 2. Install Argo CD
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server --timeout=5m

# 3. Create cluster Secrets from .env
cp .env.example .env       # edit .env, replace each <PLACEHOLDER>
./scripts/bootstrap-secrets.sh

# 4. Apply Argo CD bootstrap (cm patches FIRST — required for postgres
#    StatefulSet to converge without drift looping)
kubectl apply -f clusters/centaur-lab/argocd/bootstrap/argocd-cm-patches.yaml
kubectl -n argocd rollout restart sts/argocd-application-controller deploy/argocd-server
kubectl apply -f clusters/centaur-lab/argocd/bootstrap/00-namespaces.yaml
kubectl apply -f clusters/centaur-lab/argocd/bootstrap/centaur.yaml
```

## Verify

```bash
kubectl -n argocd get application centaur          # SYNC=Synced  HEALTH=Healthy
kubectl -n centaur-system exec deploy/centaur-centaur-api -- \
  curl -sS http://localhost:8000/health            # {"status":"ok"}
```

## Layout

```
.env.example                        secret schema — cp to .env and fill in
scripts/bootstrap-secrets.sh        creates centaur-infra-env + firewall CAs
clusters/centaur-lab/argocd/
  bootstrap/                        Argo CD Application + cm patches
  values/centaur.yaml               Helm values layered on chart defaults
  apps/                             raw manifests alongside the chart
```

## Notes

- **Apple Silicon**: chart pulls upstream amd64-only images via digest pins
  in `values/centaur.yaml`; Rosetta runs them. See that file's header for
  the digest-refresh one-liner.
- **Secrets**: `.env` is gitignored; schema lives in `.env.example`. Lose
  `.env` and you lose your credentials — back it up.

## License

[Apache-2.0 OR MIT](LICENSE).

<h4 align="center">
    GitOps infrastructure for Centaur with the centaur-lab overlay.
</h4>

<p align="center">
  Deploy the Centaur chart, the centaur-lab overlay image, and cluster-specific
  Helm values to Kubernetes via Argo CD.
</p>

## Prerequisites

- A Kubernetes cluster with `kubectl` context configured
- **Apple Silicon only** — enable Docker Desktop's amd64 emulation:
  *Docker Desktop → Settings → General → "Use Rosetta for x86_64/amd64
  emulation on Apple Silicon"*. Required because the upstream Centaur
  service images are amd64-only (see [Notes](#notes-for-local-dev-clusters-docker-desktop-on-apple-silicon)).
- Argo CD installed in the `argocd` namespace:
  ```bash
  kubectl create namespace argocd
  kubectl apply -n argocd --server-side --force-conflicts \
    -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  kubectl -n argocd rollout status deploy/argocd-server --timeout=5m
  ```
- Secrets bootstrapped in `centaur-system` (see [Bootstrapping
  secrets](#bootstrapping-secrets) below):
  - `centaur-infra-env` — model + Slack + GitHub + platform credentials,
    consumed via `envFrom` on the api/iron-proxy/slackbot pods.
  - `centaur-firewall-ca`, `centaur-firewall-ca-key` — self-signed CA for
    iron-proxy HTTPS interception.

## Bootstrapping secrets

The Helm chart references three Kubernetes Secrets but never *creates* them
— that's intentional. Real credential values stay out of git; only the
*schema* of expected keys is committed (in `.env.example`).

```bash
cp .env.example .env
# Edit .env and replace each <PLACEHOLDER> with a real value.
# (At minimum: ANTHROPIC_API_KEY, SLACK_*, SLACKBOT_API_KEY, GITHUB_TOKEN.)

source .env
./scripts/bootstrap-secrets.sh
```

The script is idempotent — it skips Secrets that already exist. Pass
`--force` to recreate them. Auto-generates random hex for keys that don't
need to be human-provided (`IRON_MANAGEMENT_API_KEY`, `SANDBOX_SIGNING_KEY`,
`POSTGRES_PASSWORD`, the firewall CA, etc.) so the only thing you actually
maintain in `.env` is real third-party credentials.

If you ever lose `.env`, you lose the source of truth for those credentials
— back it up to a password manager.

## Bootstrap

Apply in this order — the cm patches need to be in place before the Centaur
Application reconciles, otherwise the postgres StatefulSet will drift loop:

```bash
kubectl apply -f clusters/centaur-lab/argocd/bootstrap/argocd-cm-patches.yaml
kubectl -n argocd rollout restart sts/argocd-application-controller deploy/argocd-server
kubectl -n argocd rollout status sts/argocd-application-controller --timeout=2m

kubectl apply -f clusters/centaur-lab/argocd/bootstrap/00-namespaces.yaml
kubectl apply -f clusters/centaur-lab/argocd/bootstrap/centaur.yaml
```

Argo CD installs the Centaur Helm chart from `paradigmxyz/centaur` (pinned to a
commit SHA in `bootstrap/centaur.yaml`), reads Helm values from this repo at
`clusters/centaur-lab/argocd/values/centaur.yaml`, and mounts the
`ghcr.io/mperhats/centaur-lab/centaur-overlay` image into the api and sandbox
pods.

Verify:

```bash
kubectl -n argocd get application centaur
# expected: SYNC=Synced, HEALTH=Healthy

kubectl -n centaur-system exec deploy/centaur-centaur-api -- \
  curl -sS http://localhost:8000/health
# {"status":"ok"}
```

## Repository map

```text
clusters/centaur-lab/argocd/
  bootstrap/   # Argo CD Application, namespace bootstrap, argocd-cm patches
  values/      # Helm values for the Centaur Application
  apps/        # optional raw manifests managed alongside the chart
```

## Notes for local dev clusters (Docker Desktop on Apple Silicon)

`paradigmxyz/centaur` publishes amd64-only images at
`ghcr.io/paradigmxyz/centaur/centaur-*` — the workflow in
`paradigmxyz/centaur/.github/workflows/publish-images.yml` lacks a
`platforms: linux/amd64,linux/arm64` build directive, so the manifest list
contains only `linux/amd64`. On Apple Silicon, kubelet negotiates pulls as
`linux/arm64/v8` and would fall through to `ImagePullBackOff` — even with
Rosetta enabled, because Rosetta only changes runtime execution, not the
arch kubelet *requests* during pull.

**Two pieces are required**:

1. **Docker Desktop's Rosetta toggle** (see Prerequisites) — lets the host
   actually *run* the amd64 binaries once they're on disk. Trade-off:
   ~2-4× CPU overhead vs native arm64 for compute-heavy pods. Acceptable
   for a single-host lab; revisit if the agent pods feel slow.
2. **Digest-pinned image refs in `values/centaur.yaml`** — each base
   service references `tag: latest@sha256:<amd64-digest>`. Pulling by
   digest skips arch negotiation entirely; kubelet pulls exactly the
   amd64 manifest the digest points at, and Rosetta runs it.

When upstream rebuilds the images, the digests need refreshing. The
values file has the bash one-liner inline.

The overlay image is unaffected — `Mperhats/centaur-lab`'s overlay workflow
publishes `linux/amd64,linux/arm64`, so it pulls natively on both platforms
without digest pinning.

For amd64 production clusters, drop the `@sha256:...` portion of each tag
in `values/centaur.yaml`. Plain `:latest` (or a pinned `:sha-XXXXXXX`) is
sufficient when the host arch matches the manifest.

## License

[Apache-2.0 OR MIT](LICENSE).

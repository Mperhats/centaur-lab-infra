<img width="1500" height="500" alt="Centaur banner" src="https://github.com/user-attachments/assets/cc85cdb1-5a72-4eb2-ba1b-2e0a8fbbf691" />

<h4 align="center">
    GitOps infrastructure for deploying Centaur with the centaur-lab overlay.
</h4>

<p align="center">
  Bring the Centaur chart, the centaur-lab overlay image, and cluster-specific
  values together through Argo CD.
</p>

<p align="center">
  <a href="#repositories">Repositories</a> •
  <a href="#bootstrap">Bootstrap</a> •
  <a href="#configure-images">Configure Images</a> •
  <a href="#configure-secrets">Configure Secrets</a>
</p>

## Overview

`centaur-lab-infra` is the GitOps deployment repo for running
[Centaur](https://github.com/paradigmxyz/centaur) with the `centaur-lab`
organization overlay.

It was bootstrapped from
[`paradigmxyz/centaur-acme-infra`](https://github.com/paradigmxyz/centaur-acme-infra)
and adapted for the `Mperhats/centaur-lab-infra` repository, the
`ghcr.io/Mperhats/centaur-lab` overlay image, and the `clusters/centaur-lab`
cluster path.

```text
centaur-lab-infra
    |
    +-- Argo CD application
    +-- Helm values
    +-- optional raw manifests
    |
    v
Centaur in your Kubernetes cluster
```

## Repositories

- Centaur chart: `https://github.com/paradigmxyz/centaur`
- Overlay repo: `https://github.com/Mperhats/centaur-lab` (replace if you use a
  different overlay repo)
- Overlay image: `ghcr.io/Mperhats/centaur-lab`

## Bootstrap

1. Create or choose a Kubernetes cluster.
2. Install Argo CD.
3. Create the required Centaur infrastructure Secret in the target namespace
   (see [Configure secrets](#configure-secrets)).
4. Apply the bootstrap manifests:

```bash
kubectl apply -f clusters/centaur-lab/argocd/bootstrap/00-namespaces.yaml
kubectl apply -f clusters/centaur-lab/argocd/bootstrap/centaur.yaml
```

Argo CD then installs the Centaur Helm chart and mounts the centaur-lab
overlay image.

## Configure images

Edit `clusters/centaur-lab/argocd/bootstrap/centaur.yaml` and replace:

- `sha-0000000` image tags with concrete tags from your image builds
- `ghcr.io/paradigmxyz/*` base service images if you mirror them elsewhere
- `ghcr.io/Mperhats/centaur-lab` if your overlay image lives in another
  registry

The repo tracks the Centaur chart from `main` by default. Pin
`targetRevision` to a commit SHA for production.

## Configure secrets

Centaur expects an existing Kubernetes Secret named `centaur-infra-env` by
default. The minimum keys are documented in the main Centaur docs. For model
access, store provider keys with the names Centaur expects:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `AMP_API_KEY`

With iron-proxy and 1Password, those names refer to 1Password item names rather
than raw environment variables in agent sandboxes.

## Layout

```text
clusters/
  centaur-lab/
    argocd/
      bootstrap/   # Argo CD applications and namespaces
      values/      # Helm values for the Centaur app
      apps/        # optional raw manifests managed with the app
```

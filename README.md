# centaur-lab-infra

GitOps for the Centaur deployment in `centaur-system`. Argo CD installs the
upstream chart from `paradigmxyz/centaur` (pinned SHA), reads values from
this repo, and mounts the `centaur-lab` overlay image.

Lifecycle commands are exposed as `uv run` entry points (see `pyproject.toml`).

## Bootstrap

```bash
# Apple Silicon only — toggle Rosetta:
#   Docker Desktop → Settings → General → "Use Rosetta for x86_64/amd64"

cp .env.example .env        # edit .env, replace each <PLACEHOLDER>
uv run up                   # installs Argo CD, applies cm patches,
                            # creates Secrets, syncs the centaur App
uv run status               # confirm Synced/Healthy + API /health
```

## Day-to-day

```bash
uv run bump                 # resolve the newest published overlay sha
                            # from the source repo + GHCR, edit the App,
                            # and sync. --dry-run / --no-sync / --tag X
uv run sync                 # apply edits to bootstrap/centaur.yaml
                            # + hard-refresh Argo CD + wait for rollout
                            #   --no-apply       just refresh + wait
uv run status               # at-a-glance app + pod + sandbox health
uv run clean                # GC failed/succeeded pods + leaked sandboxes
                            #   --all-sandboxes  also remove Running ones
uv run down                 # delete the centaur App (Argo CD stays up)
                            #   --hard           also drop namespace + PVCs
uv run secrets              # re-apply centaur-infra-env from .env
uv run forward              # kubectl port-forwards backing the
                            # cloudflared tunnel: api:8000 + slackbot:3001
                            # (auto-restarts on disconnect; Ctrl-C stops)
                            #   --only api | --only slackbot
```

## Public ingress (Slack / GitHub webhooks)

Cloudflare Tunnel exposes `https://centaur.local-labs.xyz` and routes:

```
/api/webhooks/slack  →  slackbot pod (via localhost:3001)
everything else      →  api pod      (via localhost:8000)
```

The tunnel daemon runs as a launchd user agent (auto-starts on login,
auto-restarts on crash) — see `infra/cloudflared/README.md` for one-time
setup. Day-to-day all you need is `uv run forward` to keep the local
side of the tunnel alive.

## Layout

```
.env.example                        secret schema — cp to .env and fill in
pyproject.toml                      uv project + console-script entry points
infra/                              Python package backing the uv commands
infra/cloudflared/                  Cloudflare Tunnel routing + launchd agent
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
- **Overlay layout**: each `tools/*/pyproject.toml` in the centaur-lab
  overlay must keep `[project].dependencies` populated; upstream's
  `/entrypoint.sh` in the API image scans those at pod startup and
  silently crashloops (pipefail + `grep`) if every list is empty.

## License

[Apache-2.0 OR MIT](LICENSE).

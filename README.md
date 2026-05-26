# centaur-lab-infra

GitOps for the Centaur deployment in `centaur-system`. Argo CD installs the
upstream chart from `paradigmxyz/centaur` (pinned SHA), reads values from
this repo, and mounts the `centaur-lab` overlay image.

## Bootstrap

```bash
# Apple Silicon only — toggle Rosetta:
#   Docker Desktop → Settings → General → "Use Rosetta for x86_64/amd64"

cp .env.example .env        # edit .env, replace each <PLACEHOLDER>
./scripts/up.sh             # installs Argo CD, applies cm patches,
                            # creates Secrets, syncs the centaur App
./scripts/status.sh         # confirm Synced/Healthy + API /health
```

## Day-to-day

```bash
./scripts/sync.sh           # apply edits to bootstrap/centaur.yaml
                            # + hard-refresh Argo CD + wait for rollout
./scripts/status.sh         # at-a-glance app + pod + sandbox health
./scripts/clean.sh          # GC failed/succeeded pods + terminal sandboxes
                            #   --all-sandboxes  also remove Running ones
./scripts/down.sh           # delete the centaur App (Argo CD stays up)
                            #   --hard           also drop namespace + PVCs
```

## Layout

```
.env.example                        secret schema — cp to .env and fill in
scripts/                            up / sync / status / clean / down
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

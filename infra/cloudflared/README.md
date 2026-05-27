# Cloudflare Tunnel

Stable public URL for the local Centaur stack so Slack and workflow webhook
providers (GitHub, etc.) can deliver events to your laptop.

- **Public URL:** `https://centaur.local-labs.xyz`
- **Routing (single hostname, two backends via path):**
  - `/api/webhooks/slack` → Slackbot (`localhost:3001`)
  - everything else (workflow webhooks, `/workflows/runs`, `/agent/*`, `/healthz`) → Centaur API (`localhost:8000`)

## Day-to-day

The tunnel runs as a launchd user agent (`com.local-labs.centaur-tunnel`),
auto-starts on login, and auto-restarts on crash. You don't manage it
per-session. The only per-session thing is the two `kubectl port-forward`s
backing the tunnel's local targets — owned by `uv run forward` (port 8000
for the Centaur API, 3001 for the Slackbot).

## Managing the tunnel agent

This directory is a uv workspace member (`cloudflared-tunnel`) exposing a
single `tunnel` console script with subcommands. Run them from anywhere in
the repo:

```bash
uv run tunnel status                # is the agent loaded? running? pid?
uv run tunnel logs                  # tail ~/Library/Logs/centaur-tunnel.log
uv run tunnel install               # idempotent install / re-install
uv run tunnel uninstall             # remove the agent (confirms)
uv run tunnel uninstall --yes       # skip the confirm prompt
uv run tunnel run                   # foreground run for debugging (uninstall first)
```

The launchd-only commands (`install`, `uninstall`, `status`, `logs`) refuse
to run on non-macOS — write a sibling systemd-user-unit module on Linux
when needed.

## One-time setup on a fresh machine

The repo holds the tunnel's *routing* (`config.yml`) and *launch agent
template* (`com.local-labs.centaur-tunnel.plist`). The tunnel's *identity*
(UUID + credentials JSON) is per-Cloudflare-account and per-machine. You need
both.

1. Install cloudflared: `brew install cloudflared`.
2. Authenticate to the Cloudflare zone that owns `local-labs.xyz`:

   ```bash
   cloudflared tunnel login
   ```

   Pick the `local-labs.xyz` zone in the browser. Writes
   `~/.cloudflared/cert.pem`.

3. Either **create a new tunnel** (if this is the first machine) or **reuse
   the existing one**:

   - First machine ever:

     ```bash
     cloudflared tunnel create centaur-dev
     cloudflared tunnel route dns centaur-dev centaur.local-labs.xyz
     ```

     This writes `~/.cloudflared/<UUID>.json` (the credentials) and
     auto-creates the DNS record.

   - Additional machine, reusing the same tunnel: copy the existing
     `~/.cloudflared/<UUID>.json` from the original machine into the same
     path on the new one. (Don't run the tunnel from two machines at the
     same time unless you want Cloudflare to round-robin between them.)

4. Confirm the routing config is valid:

   ```bash
   cloudflared tunnel --config infra/cloudflared/config.yml ingress validate
   ```

5. Install the launch agent (one-time per machine):

   ```bash
   uv run tunnel install
   ```

6. Verify it's connected:

   ```bash
   uv run tunnel status   # should show state = running, pid = N
   uv run tunnel logs     # should show "Registered tunnel connection" lines
   ```

## Why a hand-rolled plist instead of `cloudflared service install`?

`cloudflared service install` is broken for locally-managed (config-file)
tunnels: it writes bare `cloudflared` into `ProgramArguments` (no subcommand),
the daemon exits immediately, and the workarounds (symlink config + `plutil`
patch) end up bigger than just writing the plist ourselves.

The template uses absolute paths everywhere so the daemon doesn't depend on
launchd's minimal environment; `tunnel install` substitutes the cloudflared
binary path, the repo config path, and the log path before loading.

## How it routes

```
Slack Events                              GitHub / arbitrary workflow webhooks
  POST /api/webhooks/slack                  POST /api/webhooks/<workflow-slug>
  └─> https://centaur.local-labs.xyz/...
        └─> Cloudflare edge
              └─> cloudflared (launchd agent, single hostname)
                    │
                    ├── path /api/webhooks/slack ──> localhost:3001 ──> Slackbot pod
                    │
                    └── all other paths          ──> localhost:8000 ──> Centaur API pod
                                                                          ├─ /api/webhooks/<workflow-slug>
                                                                          ├─ /workflows/runs
                                                                          ├─ /agent/*
                                                                          └─ /healthz
```

Reorder the path rules in `config.yml` carefully — cloudflared matches in
declaration order, and a hostname-only rule above the `/api/webhooks/slack`
rule would shadow the Slackbot route.

After editing `config.yml`, reload the agent:

```bash
uv run tunnel uninstall --yes && uv run tunnel install
```

## Tearing it down

To stop the tunnel agent: `uv run tunnel uninstall`.

To delete the tunnel entirely (e.g. rotating it):

```bash
uv run tunnel uninstall --yes
cloudflared tunnel delete centaur-dev
```

This removes the launch agent, the tunnel, and its DNS record. You'd need to
redo the one-time setup if you want to use it again.

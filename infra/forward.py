"""Run the kubectl port-forwards that back the Cloudflare Tunnel.

Centaur API on localhost:8000 and Slackbot on localhost:3001 — the same
local endpoints the cloudflared agent (`infra/cloudflared/`) routes
`https://centaur.local-labs.xyz` traffic to.

Auto-restarts each forward if it disconnects (kube-api blip, pod
re-roll, network change). Streams both processes' output line-by-line
with a service prefix. Ctrl-C terminates both cleanly.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

from ._common import NAMESPACE

RESTART_DELAY_S = 3

# (name, kubectl target, port mapping). Names must match the Cloudflare
# Tunnel routes in infra/cloudflared/config.yml.
TARGETS: list[tuple[str, str, str]] = [
    ("api",      "deploy/centaur-centaur-api",   "8000:8000"),
    ("slackbot", "svc/centaur-centaur-slackbot", "3001:3001"),
]

_shutting_down = threading.Event()


@dataclass
class Forward:
    name: str
    target: str
    ports: str
    proc: subprocess.Popen[str] | None = None

    def run(self) -> None:
        while not _shutting_down.is_set():
            self.proc = subprocess.Popen(
                ["kubectl", "-n", NAMESPACE, "port-forward", self.target, self.ports],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert self.proc.stdout is not None
            for line in iter(self.proc.stdout.readline, ""):
                print(f"[{self.name}] {line.rstrip()}", flush=True)
            rc = self.proc.wait()
            if _shutting_down.is_set():
                return
            print(
                f"[{self.name}] exited rc={rc}; restarting in {RESTART_DELAY_S}s",
                file=sys.stderr, flush=True,
            )
            time.sleep(RESTART_DELAY_S)

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forward", description=__doc__)
    parser.add_argument(
        "--only",
        choices=[name for name, *_ in TARGETS],
        help="forward only one of the services (default: both)",
    )
    args = parser.parse_args(argv)

    selected = [t for t in TARGETS if not args.only or t[0] == args.only]
    forwards = [Forward(*t) for t in selected]
    threads = [
        threading.Thread(target=f.run, name=f.name, daemon=True) for f in forwards
    ]
    for t in threads:
        t.start()

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping port-forwards...", flush=True)
    finally:
        _shutting_down.set()
        for f in forwards:
            f.stop()
        for t in threads:
            t.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Read .env and create centaur-infra-env + firewall CA secrets.

.env IS the schema — every `export KEY=VALUE` line becomes a Secret entry,
except keys in SKIP_KEYS (tooling-only, not part of the cluster Secret).
Idempotent: uses `kubectl apply`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template

from ._common import REPO_ROOT, kubectl, run

ENV_FILE = Path(os.environ.get("ENV_FILE", REPO_ROOT / ".env"))
NAMESPACE = os.environ.get("CENTAUR_NAMESPACE", "centaur-system")
SKIP_KEYS = {"CENTAUR_NAMESPACE"}
EXPORT_RE = re.compile(r"^export\s+([A-Z_][A-Z0-9_]*)=(.*)$")


def parse_env(path: Path) -> dict[str, str]:
    """Parse `export KEY=VALUE` lines, expanding $VAR / ${VAR} against earlier entries.

    Mirrors the bash behaviour of `set -a; source .env; set +a` without
    leaking variables into the caller's environment.
    """
    raw: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = EXPORT_RE.match(line)
        if m:
            raw[m.group(1)] = m.group(2)

    expanded: dict[str, str] = {}
    for key, val in raw.items():
        v = val.strip()
        # Strip matching surrounding quotes (bash does this on `source`).
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        expanded[key] = Template(v).safe_substitute(expanded)
    return expanded


def main() -> int:
    if not ENV_FILE.exists():
        print(
            f"FATAL: {ENV_FILE} not found. cp .env.example .env, then edit.",
            file=sys.stderr,
        )
        return 1
    if not shutil.which("openssl"):
        print("FATAL: openssl not on PATH", file=sys.stderr)
        return 1

    env = parse_env(ENV_FILE)

    # Namespace
    ns_yaml = kubectl(
        "create", "namespace", NAMESPACE,
        "--dry-run=client", "-o", "yaml", capture=True,
    ).stdout
    kubectl("apply", "-f", "-", input=ns_yaml, capture=True)

    # centaur-infra-env Secret
    literal_args: list[str] = [
        f"--from-literal={k}={v}" for k, v in env.items() if k not in SKIP_KEYS
    ]
    secret_yaml = kubectl(
        "-n", NAMESPACE, "create", "secret", "generic", "centaur-infra-env",
        *literal_args, "--dry-run=client", "-o", "yaml", capture=True,
    ).stdout
    kubectl("apply", "-f", "-", input=secret_yaml)

    # Self-signed firewall CA — created only if missing (long-lived; do
    # NOT regenerate casually, iron-proxy clients will reject the new cert).
    if kubectl(
        "-n", NAMESPACE, "get", "secret", "centaur-firewall-ca",
        check=False, capture=True,
    ).returncode != 0:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            run(
                "openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes",
                "-days", "3650",
                "-keyout", str(d / "ca-key.pem"),
                "-out", str(d / "ca-cert.pem"),
                "-subj", "/CN=centaur-firewall-ca/O=centaur-lab",
                capture=True,
            )
            kubectl(
                "-n", NAMESPACE, "create", "secret", "generic", "centaur-firewall-ca",
                f"--from-file=ca-cert.pem={d / 'ca-cert.pem'}",
            )
            kubectl(
                "-n", NAMESPACE, "create", "secret", "generic", "centaur-firewall-ca-key",
                f"--from-file=ca-cert.pem={d / 'ca-cert.pem'}",
                f"--from-file=ca-key.pem={d / 'ca-key.pem'}",
            )

    print(f"Done. Secrets in {NAMESPACE}:")
    kubectl(
        "-n", NAMESPACE, "get", "secret",
        "centaur-infra-env", "centaur-firewall-ca", "centaur-firewall-ca-key",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

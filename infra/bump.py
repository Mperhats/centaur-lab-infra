"""Bump bootstrap/centaur.yaml to the most-recent published overlay tag.

Walks git history of the overlay source repo (newest first) and picks
the first commit whose `sha-<7chars>` image exists in GHCR. This handles
the case where main is ahead of the latest successful build (build
pending, failed, in-flight, etc.) — we always pick the newest published
build, not the newest commit.

All API calls are anonymous (public repo + public GHCR package), so no
GITHUB_TOKEN scoping is required.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

from . import sync as sync_cmd
from ._common import BOOTSTRAP_DIR, REPO_ROOT

APP_FILE = BOOTSTRAP_DIR / "centaur.yaml"
COMMITS_TO_SCAN = 20


def _parse_image(app_yaml: str) -> tuple[str, str, str]:
    """Returns (owner, ghcr_package, github_repo) from centaur.yaml annotations.

    Annotation format: ghcr.io/<owner>/<repo>/<image>. The <owner>/<repo>
    segment doubles as the source GitHub repo for the build.
    """
    m = re.search(
        r"argocd-image-updater\.argoproj\.io/image-list:\s*\S+="
        r"ghcr\.io/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/(?P<image>\S+)",
        app_yaml,
    )
    if not m:
        raise SystemExit("Could not parse image-list annotation in centaur.yaml")
    owner, repo, image = m["owner"], m["repo"], m["image"]
    return owner, f"{repo}/{image}", repo


def _current_tag(app_yaml: str) -> str | None:
    m = re.search(
        r"-\s*name:\s*overlay\.image\.tag\s*\n\s*value:\s*(?P<tag>\S+)",
        app_yaml,
    )
    return m["tag"] if m else None


def _ghcr_token(owner: str, package: str) -> str:
    url = f"https://ghcr.io/token?scope=repository:{owner}/{package}:pull"
    with urllib.request.urlopen(url) as r:
        return json.load(r)["token"]


def _ghcr_tags(owner: str, package: str, token: str) -> set[str]:
    req = urllib.request.Request(
        f"https://ghcr.io/v2/{owner}/{package}/tags/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as r:
        return set(json.load(r).get("tags") or [])


def _github_commits(owner: str, repo: str, n: int) -> list[str]:
    """Newest-first short shas from the source repo's default branch."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={n}",
        headers={"Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as r:
        return [c["sha"][:7] for c in json.load(r)]


def _resolve_latest(owner: str, package: str, repo: str) -> tuple[str, str]:
    """Returns (tag, short_sha) for the newest commit whose image is published."""
    tags = _ghcr_tags(owner, package, _ghcr_token(owner, package))
    for short in _github_commits(owner, repo, COMMITS_TO_SCAN):
        candidate = f"sha-{short}"
        if candidate in tags:
            return candidate, short
    raise SystemExit(
        f"No published sha-* image found in last {COMMITS_TO_SCAN} commits "
        f"of {owner}/{repo}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bump", description=__doc__)
    parser.add_argument(
        "--no-sync", action="store_true",
        help="edit the file; skip kubectl apply + wait",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print current vs latest, change nothing",
    )
    parser.add_argument(
        "--tag",
        help="bump to a specific tag instead of auto-detecting (e.g. sha-abc1234)",
    )
    args = parser.parse_args(argv)

    app_yaml = APP_FILE.read_text()
    owner, package, repo = _parse_image(app_yaml)
    current = _current_tag(app_yaml) or "(unknown)"

    if args.tag:
        latest = args.tag
    else:
        latest, _ = _resolve_latest(owner, package, repo)

    print(f"Image:    ghcr.io/{owner}/{package}")
    print(f"Source:   https://github.com/{owner}/{repo}")
    print(f"Current:  {current}")
    print(f"Latest:   {latest}")

    if args.dry_run:
        return 0
    if latest == current:
        print("Already at latest.")
        return 0

    new_yaml, n = re.subn(
        r"(-\s*name:\s*overlay\.image\.tag\s*\n\s*value:\s*)\S+",
        rf"\g<1>{latest}",
        app_yaml,
    )
    if n != 1:
        raise SystemExit(
            f"Expected exactly one overlay.image.tag in centaur.yaml; got {n}"
        )

    APP_FILE.write_text(new_yaml)
    print(f"Updated {APP_FILE.relative_to(REPO_ROOT)}: {current} -> {latest}")

    if args.no_sync:
        return 0
    return sync_cmd.main()


if __name__ == "__main__":
    sys.exit(main())

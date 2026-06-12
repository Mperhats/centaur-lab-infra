"""At-a-glance progress for a BFTS workflow run (bfts_root / bfts_tree).

Queries the Centaur API via kubectl exec (no port-forward required).
Reads LOCAL_DEV_API_KEY from the environment or .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from ._common import NAMESPACE, kubectl, kubectl_json
from .secrets import ENV_FILE, parse_env


def _normalize_run_id(run_id: str) -> str:
    run_id = run_id.strip()
    if not run_id.startswith("wfr_"):
        run_id = f"wfr_{run_id}"
    return run_id


def _pod_slug(run_id: str) -> str:
    return run_id.removeprefix("wfr_")


def _api_key() -> str | None:
    if key := os.environ.get("LOCAL_DEV_API_KEY"):
        return key
    if ENV_FILE.exists():
        return parse_env(ENV_FILE).get("LOCAL_DEV_API_KEY")
    return None


def _parse_api_json(stdout: str) -> dict | None:
    idx = stdout.find("{")
    if idx == -1:
        return None
    try:
        return json.loads(stdout[idx:])
    except json.JSONDecodeError:
        return None


def _api_get(path: str, api_key: str) -> dict | None:
    proc = kubectl(
        "-n", NAMESPACE, "exec", "deploy/centaur-centaur-api", "--",
        "curl", "-fsS", "-H", f"x-api-key: {api_key}",
        f"http://localhost:8000{path}",
        check=False, capture=True,
    )
    if proc.returncode != 0:
        return None
    return _parse_api_json(proc.stdout or "")


def _bfts_pods(slug: str) -> list[tuple[str, str, str]]:
    """Return (name, phase, age-ish) for pods matching bfts-wfr-{slug}."""
    needle = f"bfts-wfr-{slug}"
    items = kubectl_json("-n", NAMESPACE, "get", "pods").get("items", [])
    out: list[tuple[str, str, str]] = []
    for pod in items:
        name = pod["metadata"]["name"]
        if needle not in name:
            continue
        phase = pod.get("status", {}).get("phase", "?")
        ts = pod["metadata"].get("creationTimestamp", "")
        out.append((name, phase, ts))
    return sorted(out)


def _short_run_id(run_id: str) -> str:
    return run_id.removeprefix("wfr_")[-8:]


def _print_run(label: str, run: dict) -> None:
    waiting = run.get("waiting_on") or {}
    wait_desc = ""
    if waiting:
        wait_desc = (
            f"  waiting_on: {waiting.get('workflow_name', '?')} "
            f"({_short_run_id(waiting.get('run_id', ''))})"
        )
    err = run.get("error_text")
    err_line = f"  error: {err}" if err else ""
    print(f"  {label} {run['run_id']}  [{run.get('workflow_name', '?')}]")
    print(f"    status={run.get('status')}  checkpoint={run.get('latest_checkpoint_name')}")
    if run.get("child_runs_count"):
        print(f"    children={run['child_runs_count']}")
    if wait_desc:
        print(wait_desc)
    if err_line:
        print(err_line)


def _print_checkpoints(api_key: str, run_id: str, tail: int) -> None:
    data = _api_get(f"/workflows/runs/{run_id}/checkpoints", api_key)
    if not data:
        print(f"    (checkpoints unavailable for {_short_run_id(run_id)})")
        return
    checkpoints = data.get("checkpoints") or []
    if not checkpoints:
        print("    (no checkpoints yet)")
        return
    print(f"    last {min(tail, len(checkpoints))} checkpoints:")
    for cp in checkpoints[-tail:]:
        ts = (cp.get("created_at") or "")[:19]
        kind = cp.get("step_kind") or ""
        kind_suffix = f" ({kind})" if kind else ""
        print(f"      {ts}  {cp.get('checkpoint_name')}{kind_suffix}")


def _render(run_id: str, api_key: str, checkpoint_tail: int) -> int:
    run = _api_get(f"/workflows/runs/{run_id}", api_key)
    if not run or not run.get("run_id"):
        print(f"FATAL: workflow run not found: {run_id}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"=== BFTS status @ {now} ===")
    print()
    _print_run("run", run)

    root_id = run.get("root_run_id")
    if root_id and root_id != run_id:
        root = _api_get(f"/workflows/runs/{root_id}", api_key)
        if root and root.get("run_id"):
            print()
            _print_run("root", root)

    children = _api_get(f"/workflows/runs/{run_id}/children", api_key)
    items = (children or {}).get("items") or []
    if items:
        print()
        print("=== tree children ===")
        for child in items:
            _print_run("child", child)
            if checkpoint_tail and child.get("status") == "running":
                _print_checkpoints(api_key, child["run_id"], checkpoint_tail)

    slug = _pod_slug(run_id)
    pods = _bfts_pods(slug)
    print()
    print(f"=== sandbox pods (bfts-wfr-{slug}) ===")
    if pods:
        for name, phase, ts in pods:
            print(f"  {phase:12} {name}  since {ts[:19]}")
    else:
        print("  (none — run may be finished or slug differs from pod names)")

    if run.get("thread_key"):
        print()
        print(f"=== slack thread ===")
        print(f"  {run['thread_key']}")

    status = run.get("status")
    if status == "completed" and not run.get("error_text"):
        print()
        print("done.")
    elif status == "failed" or run.get("error_text"):
        print()
        print("failed — inspect checkpoints and API logs.")
        return 1
    elif status == "waiting":
        print()
        print("orchestrator waiting on tree child(ren) — normal while bfts_tree runs.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bfts-status",
        description=__doc__,
    )
    parser.add_argument(
        "run_id",
        help="workflow run id, e.g. wfr_8dada4e00eda40f2 or 8dada4e00eda40f2",
    )
    parser.add_argument(
        "--watch", type=int, metavar="SECS", default=0,
        help="refresh every SECS seconds (0 = once)",
    )
    parser.add_argument(
        "--checkpoints", type=int, metavar="N", default=5,
        help="show last N checkpoints per running tree child (0 = skip)",
    )
    args = parser.parse_args(argv)

    api_key = _api_key()
    if not api_key:
        print(
            f"FATAL: LOCAL_DEV_API_KEY not set. Add it to {ENV_FILE} or export it.",
            file=sys.stderr,
        )
        return 1

    run_id = _normalize_run_id(args.run_id)

    while True:
        if args.watch:
            os.system("clear")  # noqa: S605 — intentional watch UX
        rc = _render(run_id, api_key, args.checkpoints)
        if not args.watch:
            return rc
        time.sleep(args.watch)


if __name__ == "__main__":
    sys.exit(main())

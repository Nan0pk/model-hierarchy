#!/usr/bin/env python3
"""Turn persisted fetch failures into a visible GitHub issue (daily workflow).

A failed source refresh is normal and non-fatal: the board keeps its dated
last-good snapshot and the dashboard shows the failure. But an unattended
failure should not live only in Actions logs. This script opens, updates, or
closes a single tracking issue from data/leaderboards/fetch_status.json, so a
source that keeps failing becomes a TODO without anyone watching CI.

Runs inside GitHub Actions (GITHUB_REPOSITORY + GH_TOKEN set). Outside CI it
prints the summary instead of touching GitHub.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

STATUS_FILE = pathlib.Path("data/leaderboards/fetch_status.json")
ISSUE_TITLE = "Daily refresh: failing source adapters"


def summarize(statuses: dict) -> str:
    failed = [f"- **{bid}** — {status.get('error', 'unknown error')}"
              f" (attempted {str(status.get('attempted_at', ''))[:10] or 'date unknown'})"
              for bid, status in sorted(statuses.items())
              if status.get("status") == "failed"]
    if not failed:
        return "All configured sources refreshed successfully."
    return ("The daily refresh retained last-good snapshots for these boards. This is "
            "fail-closed behavior, not data corruption — but a source that keeps failing "
            "needs an adapter review.\n\n" + "\n".join(failed)
            + "\n\nThis issue is managed by the daily workflow: it updates while failures "
              "persist and closes itself when every source succeeds.")


def _gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> int:
    if not STATUS_FILE.exists():
        print(f"no {STATUS_FILE}; nothing to report")
        return 0
    statuses = json.loads(STATUS_FILE.read_text())
    body = summarize(statuses)
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo or not os.environ.get("GH_TOKEN"):
        print(body)
        return 0
    repo_args = ["--repo", repo]
    open_issues = json.loads(_gh("issue", "list", *repo_args, "--state", "open",
                                 "--json", "number,title", "--limit", "200"))
    tracked = [issue for issue in open_issues if issue.get("title") == ISSUE_TITLE]
    failing = any(status.get("status") == "failed" for status in statuses.values())
    if failing:
        if tracked:
            _gh("issue", "edit", str(tracked[0]["number"]), *repo_args, "--body", body)
            print(f"updated tracking issue #{tracked[0]['number']}")
        else:
            print(f"opened tracking issue {_gh('issue', 'create', *repo_args, '--title', ISSUE_TITLE, '--body', body)}")
    elif tracked:
        _gh("issue", "close", str(tracked[0]["number"]), *repo_args,
            "--comment", "All configured sources refreshed successfully; closing.")
        print(f"closed tracking issue #{tracked[0]['number']}")
    else:
        print("all sources refreshed; no tracking issue needed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

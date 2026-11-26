#!/usr/bin/env python3
"""Sync duplicated version strings from the single source of truth.

hierarchy/__init__.py::METHOD_VERSION is authoritative for the methodology
implementation. This rewrites the package version (pyproject.toml) and the
native-board registry version (config/leaderboards.yaml). METHODOLOGY.md's
heading is intentionally NOT auto-edited: a methodology change is deliberate,
and `hierarchy validate` fails until its heading matches the code.

Usage: python scripts/sync_version.py   (or `make sync-version`)
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hierarchy import METHOD_VERSION  # noqa: E402

TARGETS = [
    (ROOT / "pyproject.toml",
     re.compile(r'(?m)^version\s*=\s*"\d+\.\d+\.\d+"'),
     f'version = "{METHOD_VERSION}"'),
    (ROOT / "config" / "leaderboards.yaml",
     re.compile(r'(?m)^version:\s*"\d+\.\d+\.\d+"'),
     f'version: "{METHOD_VERSION}"'),
]


def main() -> int:
    for path, pattern, replacement in TARGETS:
        text = path.read_text(encoding="utf-8")
        updated, count = pattern.subn(replacement, text, count=1)
        if count != 1:
            print(f"error: {path.relative_to(ROOT)}: version field not found", file=sys.stderr)
            return 1
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            print(f"updated {path.relative_to(ROOT)} -> {METHOD_VERSION}")
        else:
            print(f"{path.relative_to(ROOT)} already {METHOD_VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

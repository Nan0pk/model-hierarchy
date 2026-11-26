"""Documentation ↔ code consistency guards.

METHODOLOGY.md is normative; a stated version that drifts from the shipped
constants makes every published artifact claim the wrong method.
"""

import re

from hierarchy import METHOD_VERSION
from hierarchy.config import CONFIG_DIR, METHODOLOGY_FILE, methodology_version


def test_methodology_heading_matches_the_implemented_method_version():
    stated = methodology_version()
    assert stated, f"METHODOLOGY.md must state '**Version X.Y.Z' (found none in {METHODOLOGY_FILE.name})"
    assert stated == METHOD_VERSION, (
        f"METHODOLOGY.md says v{stated} but hierarchy.METHOD_VERSION is v{METHOD_VERSION}"
    )


def test_native_board_registry_version_tracks_the_methodology_version():
    registry = (CONFIG_DIR / "leaderboards.yaml").read_text(encoding="utf-8")
    match = re.search(r'^version:\s*"(\d+\.\d+\.\d+)"', registry, re.M)
    assert match, "config/leaderboards.yaml must state its version"
    assert match.group(1) == METHOD_VERSION, (
        f"config/leaderboards.yaml says v{match.group(1)} but the methodology is v{METHOD_VERSION}"
    )


def test_package_version_matches_the_method_version():
    from importlib import metadata
    import pathlib

    pyproject = (METHODOLOGY_FILE.parent / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', pyproject, re.M)
    assert match, "pyproject.toml must state the package version"
    assert match.group(1) == METHOD_VERSION


def test_methodology_version_reader_tolerates_a_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr("hierarchy.config.METHODOLOGY_FILE", tmp_path / "absent.md")
    assert methodology_version() is None

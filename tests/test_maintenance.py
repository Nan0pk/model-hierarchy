"""Maintenance tooling: refresh-failure issue summaries and version syncing."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import report_refresh_failures as reporter  # noqa: E402
import sync_version  # noqa: E402


def test_failure_summary_lists_boards_errors_and_dates():
    statuses = {
        "arena_text": {"status": "ok", "rows": 427, "attempted_at": "2026-11-26T06:05:06+00:00"},
        "artificial_analysis": {"status": "failed", "error": "index is not v5.0.2",
                                "attempted_at": "2026-11-26T06:05:06+00:00"},
        "livebench": {"status": "failed"},
    }
    body = reporter.summarize(statuses)
    assert "**artificial_analysis** — index is not v5.0.2 (attempted 2026-11-26)" in body
    assert "**livebench** — unknown error (attempted date unknown)" in body
    assert "arena_text" not in body
    assert "closes itself" in body


def test_all_clear_summary_reads_as_healthy():
    body = reporter.summarize({"arena_text": {"status": "ok", "rows": 10}})
    assert body == "All configured sources refreshed successfully."


def test_every_duplicated_version_file_is_a_sync_target():
    """A new home for the version string must be added to sync_version.TARGETS."""
    from hierarchy import METHOD_VERSION

    targets = {path.name for path, _, _ in sync_version.TARGETS}
    assert targets == {"pyproject.toml", "leaderboards.yaml"}
    for _, _, replacement in sync_version.TARGETS:
        assert METHOD_VERSION in replacement

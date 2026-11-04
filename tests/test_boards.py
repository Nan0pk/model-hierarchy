"""Native boards: current source rosters, trustworthy provenance, no synthetic fallback."""
import copy
import csv
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hierarchy.boards import (BOARD_DIR, build_board_report, load_board_config,
                              load_board_snapshots, ranked_rows, validate_snapshot,
                              write_board_snapshot)
from hierarchy.config import load_config
from hierarchy.fetch import boards as fetch
from hierarchy.fetch.boards import (FetchError, parse_artificial_analysis,
                                    parse_livebench, parse_terminal_bench)

AUDIT_DATE = dt.date(2026, 11, 3)


def table(headers, rows, title=""):
    return f"<title>{title}</title><table><thead><tr>" + "".join(
        f"<th>{h}</th>" for h in headers
    ) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    ) + "</tbody></table>"


@pytest.fixture
def audited_directory(tmp_path):
    import shutil
    for day, bid in [("2026-11-03", "artificial_analysis"), ("2026-11-03", "livebench"),
                     ("2026-11-03", "terminal_bench"), ("2026-10-28", "arena_text")]:
        target = tmp_path / day / f"{bid}.json"
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(BOARD_DIR / day / f"{bid}.json", target)
    return tmp_path


def test_complete_retained_rosters_and_current_configurations(audited_directory):
    report = build_board_report(today=AUDIT_DATE, directory=audited_directory)
    assert report["schema_version"] == 1
    assert not report["validation_issues"]
    assert {bid: b["n_scored"] for bid, b in report["boards"].items()} == {
        "artificial_analysis": 91, "arena_text": 419, "livebench": 32, "terminal_bench": 23,
    }
    aa = report["boards"]["artificial_analysis"]
    assert aa["rows"][0]["model"] == "Gemini 4 Carbon (high)"
    assert aa["rows"][0]["score"] == 59
    assert {r["model"] for r in aa["rows"]} >= {
        "Claude Opus 5.5 (max with fallback)", "GPT-6 Astra (max)", "GPT-6.1 Sol (max)",
        "Gemini 4 Argon (high)", "Kimi K3.1 Pro", "DeepSeek V4.1 Flash 1017 (max)",
    }
    assert aa["published_at"] is None
    assert aa["freshness_basis"] == "observed_at"
    assert aa["observed_at"] == "2026-11-03"
    assert "manual_transcription" in aa["retrieval_method"]
    assert "ci95" not in aa["rows"][0]
    arena = report["boards"]["arena_text"]
    assert arena["published_at"] == "2026-10-28"
    assert arena["observed_at"] is None
    assert arena["rows"][0]["votes"] == 4403
    assert arena["rows"][0]["ci95"][0] < arena["rows"][0]["score"]


def test_native_board_dates_expire_even_if_rebuilt(audited_directory):
    report = build_board_report(directory=audited_directory, today=AUDIT_DATE + dt.timedelta(days=100))
    assert all(b["status"] == "expired" for b in report["boards"].values())
    assert report["boards"]["livebench"]["observed_at"] == "2026-11-03"


def test_native_rank_ties_nulls_zero_and_effort_variants():
    rows = ranked_rows([{"model": "A (max)", "score": 50}, {"model": "A (high)", "score": 50},
                        {"model": "B", "score": None}, {"model": "C", "score": 0}])
    assert [r["rank"] for r in rows] == [1, 1, 3, None]
    assert len({r["id"] for r in rows}) == 4
    assert rows[-1]["score"] is None


def test_missing_board_never_substitutes_demo(tmp_path):
    report = build_board_report(directory=tmp_path, today=AUDIT_DATE)
    assert all(b["status"] == "missing" and not b["rows"] for b in report["boards"].values())


def small_spec_and_snap():
    spec = {"url": "https://example.test", "version": "v1", "min_rows": 2, "score_range": [0, 100]}
    snap = {"board": "example", "source": spec["url"], "version": "v1", "published_at": None,
            "observed_at": "2026-11-03", "rows": [{"model": "A", "score": 20}, {"model": "B", "score": 10}]}
    return spec, snap


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(version="v2"),
    lambda s: s.update(observed_at="2026-11-04"),
    lambda s: s.update(observed_at="not a date"),
    lambda s: s.update(rows=s["rows"][:1]),
    lambda s: s["rows"][0].update(score=float("nan")),
    lambda s: s["rows"][0].update(score=float("inf")),
    lambda s: s["rows"][0].update(score=True),
    lambda s: s["rows"][0].update(score=101),
    lambda s: s["rows"][0].update(ci95=[21, 22]),
    lambda s: s["rows"][1].update(model="a"),
    lambda s: s.update(source="https://untrusted.test"),
])
def test_invalid_native_snapshots_are_rejected(mutation):
    spec, snap = small_spec_and_snap()
    mutation(snap)
    with pytest.raises(ValueError):
        validate_snapshot(snap, "example", spec, today=AUDIT_DATE)


def test_terminal_harness_is_part_of_identity():
    spec, snap = small_spec_and_snap()
    snap["board"] = "terminal_bench"
    for row in snap["rows"]:
        row["model"] = "A (max)"
    snap["rows"][0]["harness"] = "Agent X"
    snap["rows"][1]["harness"] = "Agent Y"
    validate_snapshot(snap, "terminal_bench", spec, today=AUDIT_DATE)
    del snap["rows"][0]["harness"]
    with pytest.raises(ValueError, match="harness"):
        validate_snapshot(snap, "terminal_bench", spec, today=AUDIT_DATE)


def test_corrupt_newer_snapshot_does_not_destroy_last_valid(tmp_path):
    cfg = load_board_config()
    snapshots, _ = load_board_snapshots(today=AUDIT_DATE)
    snap = snapshots["livebench"]
    write_board_snapshot(snap, tmp_path)
    bad = copy.deepcopy(snap)
    bad["observed_at"] = "2026-11-04"
    bad["rows"] = []
    write_board_snapshot(bad, tmp_path)
    loaded, issues = load_board_snapshots(cfg, tmp_path, today=dt.date(2026, 11, 4))
    assert loaded["livebench"]["observed_at"] == "2026-11-03"
    assert issues


def test_fetch_failure_is_reported_and_retains_existing_snapshot(monkeypatch, tmp_path):
    cfg = load_config()
    _, snap = small_spec_and_snap()
    def fail(*args):
        raise FetchError("rate limited")
    monkeypatch.setattr(fetch, "fetch_native_board", fail)
    snapshots, _ = load_board_snapshots(today=AUDIT_DATE)
    write_board_snapshot(snapshots["livebench"], tmp_path)
    before = (tmp_path / "2026-11-03/livebench.json").read_bytes()
    written, failures = fetch.fetch_boards(cfg, tmp_path, quiet=True)
    assert not written and len(failures) == 4
    assert (tmp_path / "2026-11-03/livebench.json").read_bytes() == before
    report = build_board_report(directory=tmp_path, today=AUDIT_DATE)
    assert report["boards"]["livebench"]["last_fetch"]["status"] == "failed"
    assert report["boards"]["livebench"]["n_scored"] == 32


def test_aa_table_keeps_variant_names_rounding_and_null_prices():
    html = table(["Model", "Creator", "Artificial Analysis Intelligence Index", "Cost per Task USD", "Median Tokens/s"],
                 [["A (max with fallback)", "Lab", "58", "$1.25", "99"],
                  ["A (high)", "Lab", "58", "--", "--"], ["B", "Lab", "--", "$0.00", "0"]])
    rows = parse_artificial_analysis(html)
    assert len(rows) == 3
    assert rows[0]["model"] == "A (max with fallback)"
    assert rows[0]["output_tps"] == 99
    assert rows[1]["cost_per_task"] is None
    assert rows[2]["cost_per_task"] == 0 and rows[2]["score"] is None


def test_livebench_suite_version_and_missing_scores():
    html = table(["Model", "Overall▼", "Agentic", "Design", "Coding", "Browser Use", "Data Analysis", "Research", "Reasoning", "Cost per successful task"],
                 [["A open", "85.7", "77.9", "83.4", "97.7", "89.8", "80.3", "82.0", "91.7", "$7.406"],
                  ["B", "60.0", "--", "70", "80", "0", "90", "40", "50", "--"]], "LiveBench 2.0")
    rows = parse_livebench(html)
    assert rows[0]["model"] == "A" and rows[0]["open_weights"]
    assert rows[1]["agentic"] is None and rows[1]["browser_use"] == 0
    with pytest.raises(FetchError, match="version"):
        parse_livebench(html.replace("LiveBench 2.0", "LiveBench 1.0"))


def test_terminal_systems_and_release_dates_not_eval_dates():
    html = table(["Model", "Agent", "Resolution Rate", "Release Date"],
                 [["A (max)", "Agent X", "64.8% ± 3.1%", "Sep 22, 2026"],
                  ["A (max)", "Agent Y", "61.0% ± 2.9%", "Sep 22, 2026"]], "Terminal-Bench 4.0")
    rows = parse_terminal_bench(html)
    assert rows[0]["release_date"] == "2026-09-22"
    assert rows[0]["margin"] == 3.1
    assert "as_of" not in rows[0] and "ci95" not in rows[0]
    with pytest.raises(FetchError, match="version"):
        parse_terminal_bench(html.replace("4.0", "2.0"))


def test_raw_arena_mirror_cannot_substitute_for_style_control(monkeypatch):
    from hierarchy.fetch import base
    def unavailable(*args, **kwargs):
        raise FetchError("official dataset unavailable")
    monkeypatch.setattr(base, "_hf_rows", unavailable)
    with pytest.raises(FetchError, match="official dataset"):
        base.fetch_lm_arena({"endpoints": ["https://mirror.test/raw-elo"]}, load_config())


def test_evidence_transcriptions_match_committed_native_scores():
    for bid in ("artificial_analysis", "livebench", "terminal_bench"):
        snap = json.loads((BOARD_DIR / "2026-11-03" / f"{bid}.json").read_text())
        path = Path(snap["evidence_file"])
        import hashlib
        assert hashlib.sha256(path.read_bytes()).hexdigest() == snap["evidence_sha256"]
        with path.open() as handle:
            rows = list(csv.DictReader(handle))
        assert [(r["model"], float(r["score"])) for r in rows] == [(r["model"], r["score"]) for r in snap["rows"]]


def test_aa_refuses_metric_version_migration(monkeypatch):
    spec = load_board_config()["boards"]["artificial_analysis"]
    monkeypatch.setattr(fetch.base, "_get", lambda url, *a, **k: SimpleNamespace(text=(
        "<h2>Artificial Analysis Intelligence Index v6.0</h2>" if "methodology" in url else "<table></table>"
    )))
    with pytest.raises(FetchError, match="not v5.0"):
        fetch.fetch_native_board("artificial_analysis", spec, load_config())


def test_truncated_arena_pagination_fails_instead_of_publishing_first_page(monkeypatch):
    from hierarchy.fetch import base
    pages = iter([{"rows": [{"row": {"model_name": "A"}}], "num_rows_total": 3},
                  {"rows": [], "num_rows_total": 3}])
    monkeypatch.setattr(base, "_get", lambda *a, **k: SimpleNamespace(json=lambda: next(pages)))
    with pytest.raises(FetchError, match="complete roster"):
        base._hf_rows(load_config(), "text_style_control", "latest")


def test_large_roster_shrink_preserves_last_good_board(monkeypatch, tmp_path):
    snap = json.loads((BOARD_DIR / "2026-11-03/livebench.json").read_text())
    write_board_snapshot(snap, tmp_path)
    truncated = copy.deepcopy(snap)
    truncated["rows"] = truncated["rows"][:16]  # above min_rows, below the 80% guard
    def source(bid, *args):
        if bid == "livebench":
            return truncated
        raise FetchError("unavailable")
    monkeypatch.setattr(fetch, "fetch_native_board", source)
    written, failures = fetch.fetch_boards(load_config(), tmp_path, quiet=True)
    assert not written
    assert any("roster shrank" in reason for _, reason in failures)
    assert len(json.loads((tmp_path / "2026-11-03/livebench.json").read_text())["rows"]) == 32


def test_invalid_composite_snapshot_does_not_overwrite_valid_file(tmp_path):
    from hierarchy.fetch.base import write_snapshot
    valid = {"benchmark": "test", "as_of": "2026-01-01", "values": {"A": {"score": 10}}}
    path = write_snapshot(valid, tmp_path)
    before = path.read_bytes()
    invalid = copy.deepcopy(valid)
    invalid["values"]["A"]["score"] = float("nan")
    with pytest.raises(FetchError, match="Invalid snapshot"):
        write_snapshot(invalid, tmp_path)
    assert path.read_bytes() == before

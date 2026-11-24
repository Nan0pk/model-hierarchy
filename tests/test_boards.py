"""Native boards: current source rosters, trustworthy provenance, no synthetic fallback."""
import copy
import csv
import datetime as dt
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from hierarchy.boards import (BOARD_DIR, build_board_report, load_board_config,
                              load_board_snapshots, ranked_rows, validate_snapshot,
                              write_board_outputs, write_board_snapshot)
from hierarchy.config import load_config
from hierarchy.fetch import boards as fetch
from hierarchy.fetch.boards import (FetchError, parse_artificial_analysis,
                                    parse_livebench, parse_livebench_release,
                                    parse_terminal_bench, parse_terminal_bench_page)
from hierarchy.render import write_outputs

AUDIT_DATE = dt.date(2026, 11, 3)


def table(headers, rows, title=""):
    return f"<title>{title}</title><table><thead><tr>" + "".join(
        f"<th>{h}</th>" for h in headers
    ) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    ) + "</tbody></table>"


def rsc_page(payload_str: str, title: str = "") -> str:
    encoded = json.dumps(payload_str)
    return f"<title>{title}</title><script>self.__next_f.push([1,{encoded}])</script>"


@pytest.fixture
def audited_cfg():
    cfg = copy.deepcopy(load_board_config())
    cfg["boards"]["artificial_analysis"]["version"] = "Intelligence Index v5.0"
    cfg["boards"]["artificial_analysis"]["previous_versions"] = []
    cfg["boards"]["terminal_bench"]["version"] = "Terminal-Bench 4.0"
    cfg["boards"]["terminal_bench"]["previous_versions"] = []
    return cfg


@pytest.fixture
def audited_directory(tmp_path):
    for day, bid in [("2026-11-03", "artificial_analysis"), ("2026-11-03", "livebench"),
                     ("2026-11-03", "terminal_bench"), ("2026-10-28", "arena_text")]:
        target = tmp_path / day / f"{bid}.json"
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(BOARD_DIR / day / f"{bid}.json", target)
    return tmp_path


def test_complete_retained_rosters_and_current_configurations(audited_directory, audited_cfg):
    report = build_board_report(cfg=audited_cfg, today=AUDIT_DATE, directory=audited_directory)
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


def test_superseded_previous_versions_archive_cleanly_without_version_mixing(audited_directory):
    report = build_board_report(today=AUDIT_DATE, directory=audited_directory)
    assert not report["validation_issues"]
    # v5.0 and 4.0 archives must never be served under v5.0.1 and 4.1 titles.
    assert report["boards"]["artificial_analysis"]["status"] == "missing"
    assert report["boards"]["terminal_bench"]["status"] == "missing"
    assert report["boards"]["livebench"]["n_scored"] == 32


def test_november_24_v2_1_snapshots_are_fresh_and_complete(tmp_path):
    day = dt.date(2026, 11, 24)
    shutil.copytree(BOARD_DIR / day.isoformat(), tmp_path / day.isoformat())
    report = build_board_report(today=day, directory=tmp_path)
    assert not report["validation_issues"]
    for bid, board in report["boards"].items():
        assert board["status"] == "available", f"{bid} is {board['status']}"
    assert report["boards"]["artificial_analysis"]["version"] == "Intelligence Index v5.0.1"
    assert report["boards"]["artificial_analysis"]["n_scored"] >= 120
    assert report["boards"]["arena_text"]["n_scored"] >= 420
    assert report["boards"]["livebench"]["published_at"] is not None
    assert report["boards"]["livebench"]["n_scored"] >= 40
    assert report["boards"]["terminal_bench"]["version"] == "Terminal-Bench 4.1"
    assert report["boards"]["terminal_bench"]["published_at"] is not None
    assert report["boards"]["terminal_bench"]["n_scored"] >= 60


def test_native_board_dates_expire_even_if_rebuilt(audited_directory, audited_cfg):
    report = build_board_report(
        cfg=audited_cfg, directory=audited_directory, today=AUDIT_DATE + dt.timedelta(days=100)
    )
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


def test_aa_rsc_payload_retains_collapsed_variants_and_metadata():
    models = [
        {"name": "Model Alpha (Max, Default Fallback)", "modelCreatorName": "Lab A",
         "intelligenceIndex": 64.56, "contextWindowTokens": 1000000,
         "intelligenceIndexCostPerTask": 26.538, "outputSpeed": 111.4,
         "isOpenWeights": False, "deprecated": False},
        {"name": "Model Alpha (High, Default Fallback)", "modelCreatorName": "Lab A",
         "intelligenceIndex": 61.82, "contextWindowTokens": 131072,
         "intelligenceIndexCostPerTask": None, "outputSpeed": None,
         "isOpenWeights": True, "deprecated": False},
        {"name": "Unscored Placeholder", "modelCreatorName": "Lab B",
         "intelligenceIndex": None, "deprecated": False},
        {"name": "Retired Model", "modelCreatorName": "Lab C",
         "intelligenceIndex": 50.0, "deprecated": True},
    ]
    html = rsc_page(f'0:{{"initialModels":{json.dumps(models)}}}')
    rows = parse_artificial_analysis(html)
    assert len(rows) == 2
    assert rows[0] == {
        "model": "Model Alpha (Max, Default Fallback)",
        "score": 65.0,
        "provider": "Lab A",
        "context": "1M",
        "cost_per_task": 26.54,
        "output_tps": 111.0,
        "open_weights": False,
    }
    assert rows[1]["context"] == "131k" and rows[1]["open_weights"] is True


def test_livebench_suite_version_and_missing_scores():
    html = table(["Model", "Overall▼", "Agentic", "Design", "Coding", "Browser Use", "Data Analysis", "Research", "Reasoning", "Cost per successful task"],
                 [["A open", "85.7", "77.9", "83.4", "97.7", "89.8", "80.3", "82.0", "91.7", "$7.406"],
                  ["B", "60.0", "--", "70", "80", "0", "90", "40", "50", "--"]], "LiveBench 2.0")
    rows = parse_livebench(html)
    assert rows[0]["model"] == "A" and rows[0]["open_weights"]
    assert rows[1]["agentic"] is None and rows[1]["browser_use"] == 0
    with pytest.raises(FetchError, match="version"):
        parse_livebench(html.replace("LiveBench 2.0", "LiveBench 1.0"))


def test_livebench_spa_release_feed_and_unquoted_js_metadata(monkeypatch):
    js_bundle = (
        'const Yt=["20261025","20261106"],Zt="11 November 2026";'
        'const m={"model-a":{displayName:"Model A (xhigh)",organization:"Org A",openweight:!1},'
        'inkling:{displayName:"Inkling",organization:"Thinking Machines",openweight:!0},'
        '"ft-model":{displayName:"Finetune",organization:"Org B",openweight:!0,finetune:{baseKey:"inkling"}}};'
        'const hdr=["Last updated ",jsx("b",{children:Zt})," \\u2014 the latest release"];'
    )
    categories = {
        "Long Agentic": ["long_agentic"],
        "Design": ["design"],
        "Coding": ["coding"],
        "Browser": ["browser"],
        "Data Analysis": ["data_analysis"],
        "Research": ["research"],
        "Reasoning": ["reasoning"],
        "_overall_weights": {"Long Agentic": 2.0, "Coding": 1.5, "Design": 1.5},
    }
    table_csv = (
        "model,long_agentic,reasoning,coding,browser,data_analysis,research,design\n"
        "model-a,80,90,80,70,70,70,80\n"
        "inkling,50,60,n/a,0,50,50,50\n"
        "ft-model,99,99,99,99,99,99,99\n"
    )
    cost_csv = (
        "model,long_agentic,nq_long_agentic,reasoning,nq_reasoning,coding,nq_coding,"
        "browser,nq_browser,data_analysis,nq_data_analysis,research,nq_research,design,nq_design\n"
        "model-a,100,10,50,50,60,10,40,10,30,10,20,10,20,0\n"
    )
    rows, published = parse_livebench_release(
        js_bundle, categories, table_csv, cost_csv, today=dt.date(2026, 11, 24)
    )
    assert published == "2026-11-11"
    assert len(rows) == 2  # finetune excluded
    assert rows[0]["model"] == "Model A (xhigh)" and rows[0]["provider"] == "Org A"
    assert rows[0]["score"] == 77.8  # (80*2 + 80*1.5 + 80*1.5 + 90 + 70*3) / 9 = 77.78 -> 77.8
    assert rows[0]["cost_per_success"] == round((300 / 100) / 77.78 * 100, 3)
    assert rows[1]["model"] == "Inkling" and rows[1]["open_weights"] is True
    assert rows[1]["coding"] is None and rows[1]["browser_use"] == 0.0

    bad_categories = {k: v for k, v in categories.items() if k != "Research"}
    with pytest.raises(FetchError, match="suite schema"):
        parse_livebench_release(js_bundle, bad_categories, table_csv, today=dt.date(2026, 11, 24))


@pytest.mark.parametrize(("table_csv", "error"), [
    ("model,Coding\nA,99", "missing columns"),
    ("model,Agentic,Design,Coding,Browser,Data Analysis,Research,Reasoning,Coding", "duplicate"),
    ("model,Agentic,Design,Coding,Browser,Data Analysis,Research,Reasoning\nA,99", "row width"),
])
def test_livebench_rejects_incomplete_or_ambiguous_score_table(table_csv, error):
    suites = ("Agentic", "Design", "Coding", "Browser", "Data Analysis", "Research", "Reasoning")
    categories = {suite: [suite] for suite in suites}
    with pytest.raises(FetchError, match=error):
        parse_livebench_release('releases=["20261106"]', categories, table_csv,
                                today=dt.date(2026, 11, 24))


def test_terminal_systems_and_release_dates_not_eval_dates():
    html = table(["Model", "Agent", "Resolution Rate", "Release Date"],
                 [["A  ( max )", "Agent X", "64.8% ± 3.1%", "Sep 22, 2026"],
                  ["A (max)", "Agent Y", "61.0% ± 2.9%", "Sep 22, 2026"]], "Terminal-Bench 4.1")
    rows = parse_terminal_bench(html)
    assert rows[0]["model"] == "A (max)"
    assert rows[0]["release_date"] == "2026-09-22"
    assert rows[0]["margin"] == 3.1
    assert "as_of" not in rows[0] and "ci95" not in rows[0]
    with pytest.raises(FetchError, match="version"):
        parse_terminal_bench(html.replace("4.1", "4.0"))


def test_terminal_bench_rsc_extracts_display_rows_and_updated_date():
    payload = {
        "leaderboard": {"id": "lb-1", "title": "Terminal-Bench 4.1",
                        "updated_at": "2026-11-20T16:07:10+00:00"},
        "rows": [
            {"status": "display",
             "metadata": {"date": "2026-11-17", "reasoning_effort": "max",
                          "model_org": {"label": "GitHub"},
                          "model_display": {"label": "Copilot Fusion"},
                          "agent_display": {"label": "GitHub Copilot"}},
             "metrics": {"accuracy": 71.21, "display_accuracy": "**71.2%** ± 2.9%",
                         "accuracy_ci95_half_width": 2.88}},
            {"status": "hidden",
             "metadata": {"date": "2026-11-17", "reasoning_effort": "max",
                          "model_display": {"label": "Hidden"}, "agent_display": {"label": "X"}},
             "metrics": {"display_accuracy": "50.0% ± 1.0%"}},
        ],
    }
    rows, published = parse_terminal_bench_page(rsc_page(json.dumps(payload)))
    assert published == "2026-11-20"
    assert rows == [{
        "model": "Copilot Fusion (max)",
        "harness": "GitHub Copilot",
        "score": 71.2,
        "margin": 2.9,
        "release_date": "2026-11-17",
        "provider": "GitHub",
    }]
    payload["leaderboard"]["title"] = "Terminal-Bench 5.0"
    with pytest.raises(FetchError, match="4.1 version marker"):
        parse_terminal_bench_page(rsc_page(json.dumps(payload)))


def test_idempotent_outputs_do_not_churn_timestamps(tmp_path):
    report1 = build_board_report(directory=tmp_path, today=AUDIT_DATE)
    report1["generated_at"] = "2026-11-24T10:00:00+00:00"
    write_board_outputs(report1, tmp_path)
    report2 = copy.deepcopy(report1)
    report2["generated_at"] = "2026-11-24T10:05:00+00:00"
    write_board_outputs(report2, tmp_path)
    saved = json.loads((tmp_path / "leaderboards.json").read_text())
    assert saved["generated_at"] == "2026-11-24T10:00:00+00:00"
    # The discovery index ships beside the dashboard payload, not inside it.
    assert "catalogue" not in saved and "catalogue" in report2
    assert json.loads((tmp_path / "catalogue.json").read_text()) == report1["catalogue"]

    comp1 = {"generated_at": "2026-11-24 10:00 UTC", "models": [], "quality": {"status": "withheld"}}
    write_outputs(comp1, tmp_path)
    comp2 = {"generated_at": "2026-11-24 10:05 UTC", "models": [], "quality": {"status": "withheld"}}
    write_outputs(comp2, tmp_path)
    saved_comp = json.loads((tmp_path / "leaderboard.json").read_text())
    assert saved_comp["generated_at"] == "2026-11-24 10:00 UTC"


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
    with pytest.raises(FetchError, match="not v5.0.1"):
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

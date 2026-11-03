from types import SimpleNamespace

import pytest

from hierarchy.config import load_config
from hierarchy.fetch import base
from hierarchy.fetch.base import FetchError, fetch_all, fetch_livecodebench, fetch_vals_table


@pytest.fixture
def cfg():
    return load_config()


def test_vals_table_parses_published_date_and_score(monkeypatch, cfg):
    html = """
    <p>GPQA Diamond • Sep 01, 2026</p>
    <table><thead><tr><th>Rank</th><th>Model</th><th>Accuracy</th></tr></thead>
    <tbody><tr><td>1</td><td>Model X</td><td>95.45%</td></tr>
    <tr><td>2</td><td>Model Y</td><td>92.1%</td></tr></tbody></table>
    """
    monkeypatch.setattr(base, "_get", lambda *args, **kwargs: SimpleNamespace(text=html))
    source = {
        "benchmark": "gpqa_diamond",
        "url": "https://example.test/gpqa",
        "qualification": "198-item Diamond subset",
        "table_spec": {
            "model_header": "Model",
            "score_header": "Accuracy",
            "date_regex": r"([A-Za-z]{3,9} \d{1,2}, \d{4})",
        },
    }

    snap = fetch_vals_table(source, cfg)

    assert snap["values"] == {"Model X": {"score": 95.45}, "Model Y": {"score": 92.1}}
    assert snap["as_of"] == "2026-09-01"
    assert snap["provenance_type"] == "independent_evaluation"
    assert snap["qualification"] == "198-item Diamond subset"


def test_vals_table_filters_to_fixed_swe_harness(monkeypatch, cfg):
    html = """
    <p>SWE-bench • Sep 01, 2026</p>
    <table><tr><th>Model</th><th>Harness</th><th>Score</th></tr>
    <tr><td>Model X</td><td>Mini-SWE-agent</td><td>70.2%</td></tr>
    <tr><td>Model X</td><td>Other Agent</td><td>99%</td></tr></table>
    """
    monkeypatch.setattr(base, "_get", lambda *args, **kwargs: SimpleNamespace(text=html))
    source = {
        "benchmark": "swebench_verified",
        "url": "https://example.test/swebench",
        "table_spec": {
            "model_header": "Model", "score_header": "Score",
            "date_regex": r"([A-Za-z]{3,9} \d{1,2}, \d{4})",
            "filter_header": "Harness", "filter_value": "Mini-SWE-agent",
        },
    }

    snap = fetch_vals_table(source, cfg)

    assert snap["values"] == {"Model X": {"score": 70.2}}
    assert snap["harness"] == "Mini-SWE-agent"


def test_livecodebench_reads_official_table_and_window_end(monkeypatch, cfg):
    html = """
    <p>454 problems selected in the current time window (8/1/2024 to 5/1/2025).</p>
    <table><thead><tr><th>Rank</th><th>Model</th><th>Pass@1</th><th>Easy</th></tr></thead>
    <tbody><tr><td>1</td><td><a>Model A (High)</a></td><td>80.2</td><td>99.1</td></tr>
    <tr><td>2</td><td>Model B</td><td>74.2</td><td>98.2</td></tr></tbody></table>
    """
    monkeypatch.setattr(base, "_get", lambda *args, **kwargs: SimpleNamespace(text=html))
    source = {
        "benchmark": "livecodebench",
        "url": "https://example.test/leaderboard.html",
        "table_spec": {"date_regex": r"to (\d{1,2}/\d{1,2}/\d{4})"},
    }

    snap = fetch_livecodebench(source, cfg)

    assert snap["values"] == {"Model A (High)": {"score": 80.2}, "Model B": {"score": 74.2}}
    assert snap["as_of"] == "2025-05-01"


def test_unimplemented_source_kind_is_reported_not_silently_skipped(cfg):
    cfg.sources = {"sources": {"future_source": {"role": "scored", "kind": "not_implemented"}}}

    written, failures = fetch_all(cfg, quiet=True)

    assert written == []
    assert failures == [("future_source", "source kind 'not_implemented' has no fetch adapter; this benchmark is manual-only until an adapter is implemented")]


def test_livecodebench_requires_source_window_date(monkeypatch, cfg):
    html = "<table><tr><th>Model</th><th>Pass@1</th></tr><tr><td>M</td><td>50</td></tr></table>"
    monkeypatch.setattr(base, "_get", lambda *args, **kwargs: SimpleNamespace(text=html))
    source = {"url": "https://example.test/leaderboard.html", "table_spec": {"date_regex": r"to (\d+/\d+/\d+)"}}
    with pytest.raises(FetchError, match="evaluation window date not found"):
        fetch_livecodebench(source, cfg)

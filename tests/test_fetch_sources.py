from types import SimpleNamespace

import pytest

from hierarchy.config import load_config
from hierarchy.fetch import base
from hierarchy.fetch.base import FetchError, fetch_all, fetch_livecodebench, fetch_swebench


@pytest.fixture
def cfg():
    return load_config()


def test_swebench_uses_fixed_agent_and_latest_model_row(monkeypatch, cfg):
    payload = {
        "leaderboards": [
            {"name": "Lite", "results": [{"model_display": "Wrong", "resolved": 99}]},
            {
                "name": "Verified",
                "results": [
                    {"agent": "mini-SWE-agent", "model_display": "Model X", "resolved": 60, "date": "2025-01-01"},
                    {"agent": "mini-SWE-agent", "model_display": "Model X", "resolved": 70, "date": "2025-02-01"},
                    {"agent": "Other Agent", "model_display": "Model X", "resolved": 99, "date": "2025-03-01"},
                    {"agent": "mini-SWE-agent", "model_display": "Multiple", "resolved": 100, "date": "2025-03-01"},
                ],
            },
        ]
    }
    monkeypatch.setattr(base, "_get", lambda *args, **kwargs: SimpleNamespace(json=lambda: payload))
    source = {
        "benchmark": "swebench_verified",
        "url": "https://example.test/leaderboards.json",
        "leaderboard_spec": {"board": "Verified", "agent": "mini-SWE-agent"},
    }

    snap = fetch_swebench(source, cfg)

    assert snap["values"] == {"Model X": {"score": 70.0}}
    assert snap["as_of"] == "2025-02-01"
    assert snap["harness"] == "mini-SWE-agent"


def test_swebench_refuses_unscoped_agent_mixing(monkeypatch, cfg):
    source = {"url": "https://example.test/data.json", "leaderboard_spec": {"board": "Verified"}}
    with pytest.raises(FetchError, match="fixed leaderboard_spec.agent"):
        fetch_swebench(source, cfg)


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

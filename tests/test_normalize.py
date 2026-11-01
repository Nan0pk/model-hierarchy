"""Normalization contracts (METHODOLOGY.md §6)."""

import pytest

from hierarchy.normalize import borda, minmax, normalize_benchmark


def test_borda_orders_and_scales():
    v = borda({"a": 10, "b": 20, "c": 30})
    assert v["c"] == pytest.approx(1.0)
    assert v["b"] == pytest.approx(0.5)
    assert v["a"] == pytest.approx(0.0)


def test_borda_ties_share_average_rank():
    v = borda({"a": 10, "b": 10, "c": 30})
    assert v["c"] == pytest.approx(1.0)
    assert v["a"] == v["b"] == pytest.approx(0.25)


def test_minmax_clips_outliers():
    v = minmax({"a": 1, "b": 2, "c": 3, "d": 4, "e": 100})
    assert v["e"] == 1.0          # outlier capped after p95 clipping
    assert v["a"] == 0.0
    assert v["d"] < 0.1           # interior values compress


def test_minmax_no_clip_for_elo():
    v = minmax({"a": 1200, "b": 1300, "c": 1400}, clip=None)
    assert v == {"a": 0.0, "b": 0.5, "c": 1.0}


def test_minmax_degenerate_returns_half():
    assert minmax({"a": 5, "b": 5}) == {"a": 0.5, "b": 0.5}


def test_blend_is_half_borda_half_minmax():
    scores = {"a": 10, "b": 20, "c": 30}
    v = normalize_benchmark(scores, "blend")
    expected = {m: max(0.02, 0.5 * borda(scores)[m] + 0.5 * minmax(scores)[m]) for m in scores}
    assert v == pytest.approx(expected)


def test_log_share_compresses_heavy_tail():
    v = normalize_benchmark({"x": 100.0, "y": 1.0, "z": 0.01}, "log_share")
    assert v["x"] == pytest.approx(1.0)
    assert v["z"] == pytest.approx(0.02)   # floored (§6.5)
    assert 0.3 < v["y"] < 0.7     # linear minmax would put y at ~0.01


def test_lower_is_better_direction():
    v = normalize_benchmark({"a": 10, "b": 20}, "borda_only", higher_better=False)
    assert v["a"] == pytest.approx(1.0)
    assert v["b"] == pytest.approx(0.02)   # floored (§6.5)


def test_values_are_floored():
    v = normalize_benchmark({"a": 0, "b": 100}, "minmax_only")
    assert v["a"] >= 0.02          # §6.5: geometric-mean safety floor


def test_empty_input():
    assert normalize_benchmark({}, "blend") == {}

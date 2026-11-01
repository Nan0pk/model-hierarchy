"""Aggregation contracts (METHODOLOGY.md §5, §7–§11) on toy configs."""

import pytest

from hierarchy.aggregate import dominance_list, pairwise_probs, pillar_and_g
from hierarchy.config import Config
from hierarchy.tiers import assign_tiers, tier_labels


def toy_cfg(min_pillars=2, min_benchmarks=2) -> Config:
    weights = {
        "version": "test",
        "aggregation": {
            "method": "two_level_weighted_geometric",
            "value_floor": 0.02,
            "pillar_floor": 0.05,
            "coverage_penalty": {"base": 0.70, "span": 0.30},
            "eligibility": {"min_pillars": min_pillars, "min_benchmarks": min_benchmarks},
            "staleness": {"warn_after_days": 14, "exclude_after_days": 120},
        },
        "uncertainty": {"bootstrap_reps": 100, "seed": 42, "default_noise_raw": 1.5,
                        "dominance_threshold": 0.95},
        "tiers": {"max_tiers": 7, "separation_confidence": 0.95},
        "pillars": {
            "p1": {"label": "P1", "weight": 0.5},
            "p2": {"label": "P2", "weight": 0.5},
        },
        "benchmarks": {
            "b1": {"pillar": "p1", "weight": 0.5, "normalization": "blend"},
            "b2": {"pillar": "p2", "weight": 0.5, "normalization": "blend"},
        },
    }
    return Config(weights, {"sources": {}})


# ---- §8: geometric mean vs arithmetic mean --------------------------------
def test_equal_mean_balanced_beats_spiky():
    """Same arithmetic mean (0.92): the geometric aggregate strictly prefers balance."""
    cfg = toy_cfg()
    vmat = {
        "b1": {"gen": 0.92, "spk": 1.00},
        "b2": {"gen": 0.92, "spk": 0.84},
    }
    res = pillar_and_g(vmat, cfg)
    assert res["gen"]["g"] == pytest.approx(0.92, abs=1e-9)
    assert res["spk"]["g"] == pytest.approx((1.00 * 0.84) ** 0.5, abs=1e-9)
    assert res["gen"]["g"] > res["spk"]["g"]


def test_spikier_needs_strictly_higher_mean():
    cfg = toy_cfg()
    vmat = {
        "b1": {"gen": 0.92, "spk": 1.00},
        "b2": {"gen": 0.92, "spk": 0.70},
    }
    res = pillar_and_g(vmat, cfg)
    assert res["spk"]["g"] < res["gen"]["g"]
    assert res["gen"]["g"] - res["spk"]["g"] > 0.92 - 0.85  # geometric gap > arithmetic gap


# ---- §7: within-pillar renormalization -------------------------------------
def test_within_pillar_missing_benchmark_renormalizes():
    cfg = toy_cfg()
    vmat = {
        "b1": {"m": 0.8},
        "b2": {"m": 0.6},
    }
    res = pillar_and_g(vmat, cfg)
    assert res["m"]["pillars"]["p1"] == pytest.approx(0.8)   # single bench = pillar score
    assert res["m"]["g"] == pytest.approx((0.8 * 0.6) ** 0.5)


# ---- §9: coverage penalty ---------------------------------------------------
def test_coverage_penalty_charges_missing_pillars():
    cfg = toy_cfg(min_pillars=1, min_benchmarks=1)
    vmat = {
        "b1": {"full": 0.9, "partial": 0.9},
        "b2": {"full": 0.9},
    }
    res = pillar_and_g(vmat, cfg)
    assert res["full"]["coverage"] == pytest.approx(1.0)
    assert res["full"]["penalty"] == pytest.approx(1.0)
    assert res["partial"]["coverage"] == pytest.approx(0.5)
    assert res["partial"]["penalty"] == pytest.approx(0.85)   # 0.70 + 0.30*0.5
    assert res["partial"]["g"] < res["full"]["g"]


# ---- §5: eligibility ----------------------------------------------------------
def test_eligibility_flags():
    cfg = toy_cfg(min_pillars=2, min_benchmarks=2)
    vmat = {
        "b1": {"ok": 0.9, "thin": 0.9},
        "b2": {"ok": 0.9},
    }
    res = pillar_and_g(vmat, cfg)
    assert res["ok"]["eligible"] is True
    assert res["thin"]["eligible"] is False
    assert "insufficient_data" in res["thin"]["flags"]


def test_no_preference_signal_flag():
    cfg = toy_cfg(min_pillars=1, min_benchmarks=1)
    vmat = {"b1": {"m": 0.5}, "b2": {"m": 0.5}}
    res = pillar_and_g(vmat, cfg)
    assert "no_preference_signal" in res["m"]["flags"]


# ---- §10: pairwise probabilities + dominance --------------------------------
def test_pairwise_probs_and_dominance_direction():
    draws = {
        "a": [1.0, 1.1, 0.9, 1.2, 1.0],
        "b": [0.8, 0.9, 0.7, 1.0, 0.85],
        "c": [0.5, 0.6, 0.4, 0.55, 0.5],
    }
    probs = pairwise_probs(draws, ["a", "b", "c"])
    assert probs[("a", "b")] == pytest.approx(1.0)   # a > b in every draw
    assert probs[("b", "a")] == pytest.approx(0.0)
    dom = dominance_list(probs, ["a", "b", "c"], 0.95)
    pairs = {(d["a"], d["b"]) for d in dom}
    assert ("a", "b") in pairs and ("a", "c") in pairs and ("b", "c") in pairs
    assert all(d["p"] >= 0.95 for d in dom)
    # exactly one direction per unordered pair
    assert len(dom) == 3


def test_dominance_reports_dominant_direction():
    draws = {"x": [0.9, 0.8, 0.95], "y": [0.5, 0.6, 0.55]}
    probs = pairwise_probs(draws, ["x", "y"])
    dom = dominance_list(probs, ["x", "y"], 0.95)
    assert dom == [{"a": "x", "b": "y", "p": 1.0}]    # x > y, even though "x" > "y" lexically


# ---- §11: tiers ---------------------------------------------------------------
def test_tiers_separate_only_when_separated():
    entries = [
        {"model": "A", "median": 0.90, "lo": 0.88, "hi": 0.92},
        {"model": "B", "median": 0.89, "lo": 0.87, "hi": 0.91},
        {"model": "C", "median": 0.50, "lo": 0.45, "hi": 0.55},
        {"model": "D", "median": 0.48, "lo": 0.43, "hi": 0.53},
        {"model": "E", "median": 0.10, "lo": 0.05, "hi": 0.15},
    ]
    probs = {("A", "B"): 0.60, ("A", "C"): 1.0, ("A", "D"): 1.0, ("A", "E"): 1.0,
             ("C", "D"): 0.60, ("C", "E"): 1.0}
    tiers = assign_tiers(entries, probs, max_tiers=7, confidence=0.95)
    labels = tier_labels(tiers)
    assert labels == {"T1": ["A", "B"], "T2": ["C", "D"], "T3": ["E"]}


def test_tiers_respect_max_cap():
    entries = [
        {"model": f"M{i}", "median": 1.0 - i * 0.10, "lo": 1.0 - i * 0.10 - 0.01,
         "hi": 1.0 - i * 0.10 + 0.01}
        for i in range(10)
    ]
    probs = {(a["model"], b["model"]): 1.0 for a in entries for b in entries if a is not b}
    tiers = assign_tiers(entries, probs, max_tiers=4, confidence=0.95)
    assert len(tiers) == 4

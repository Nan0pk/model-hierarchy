"""End-to-end pipeline on the bundled synthetic demo data.

Also covers §12 staleness with dates computed relative to today (date-robust).
"""

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hierarchy.config import DEMO_DIR, load_config
from hierarchy.data import load_manual_csv, to_matrix
from hierarchy.pipeline import apply_staleness, compute, _cohort


@pytest.fixture(scope="module")
def result():
    cfg = load_config()
    snaps = load_manual_csv(DEMO_DIR / "scores.csv")
    for snap in snaps.values():  # re-date: keeps this test valid forever
        snap["as_of"] = dt.date.today().isoformat()
    raw, sigma, as_of, skipped, _, _ = to_matrix(snaps, cfg)
    assert skipped == set()
    return compute(raw, sigma, as_of, cfg, demo=True, reps=300)


def test_all_12_demo_models_ranked(result):
    assert len(result["models"]) == 12
    assert result["unranked"] == []
    ranks = [m["rank"] for m in result["models"]]
    assert ranks == list(range(1, 13))


def test_tier_structure(result):
    tiers = result["tiers"]
    assert 3 <= len(tiers) <= 7
    assert set(tiers.keys()) <= {f"T{i}" for i in range(1, 8)}
    # every ranked model appears in exactly one tier
    listed = [m for members in tiers.values() for m in members]
    assert sorted(listed) == sorted(m["model"] for m in result["models"])


def test_top_cluster_is_the_expected_three(result):
    top_tier = result["tiers"]["T1"]
    # canonical form: separators unified to spaces, version dots preserved (§12)
    assert set(top_tier) == {"gemini 3 pro", "gpt 5.1", "claude opus 4.5"}


def test_dominance_pairs_are_confident(result):
    assert result["dominance"], "expected at least one confidently-better pair"
    for d in result["dominance"]:
        assert d["p"] >= 0.95
        a = next(m for m in result["models"] if m["model"] == d["a"])
        b = next(m for m in result["models"] if m["model"] == d["b"])
        assert a["g"] > b["g"]


def test_scores_and_cis_are_sane(result):
    for m in result["models"]:
        assert 0 <= m["g"] <= 100
        assert m["ci95"][0] <= m["g"] <= m["ci95"][1]
        assert 0 < m["coverage"] <= 1.0
        assert m["n_benchmarks"] >= 5
        for pid, p in m["pillars"].items():
            assert 0 <= p["score"] <= 100
            assert 0 < p["coverage"] <= 1.0


def test_full_coverage_models_have_no_penalty(result):
    for m in result["models"]:
        if m["coverage"] == pytest.approx(1.0):
            assert "no_preference_signal" not in m["flags"]


def test_provenance_is_stamped(result):
    assert result["demo"] is True
    assert result["weights_version"] == "1.1.0"
    assert result["config_hash"]
    assert result["data_as_of"]


def test_staleness_flags_and_exclusion():
    cfg = load_config()
    today = dt.date.today()

    def d(offset):
        return (today - dt.timedelta(days=offset)).isoformat()

    raw = {"gpqa_diamond": {"m": 80.0}, "livebench_overall": {"m": 60.0}, "seal_average": {"m": 50.0}}
    sigma = {b: {"m": 1.5} for b in raw}
    as_of = {"gpqa_diamond": d(1), "livebench_overall": d(30), "seal_average": d(200)}
    stale, excluded = apply_staleness(raw, sigma, as_of, cfg)
    assert stale == ["livebench_overall"]          # > 14 days
    assert excluded == ["seal_average"]            # > 120 days -> dropped from raw
    assert "seal_average" not in raw
    assert "livebench_overall" in raw


def test_cohort_isolation_normalization():
    """§5: models outside the cohort must NOT stretch the normalization scales.

    A real Arena pull contains ~100 models; only the ones with >=3 pillars
    belong to the cohort. Adding non-cohort rows must leave every cohort
    model's G-score bit-for-bit unchanged.
    """
    cfg = load_config()
    snaps = load_manual_csv(DEMO_DIR / "scores.csv")
    for snap in snaps.values():
        snap["as_of"] = dt.date.today().isoformat()
    raw, sigma, as_of, _, _, _ = to_matrix(snaps, cfg)

    # a swarm of non-cohort models touching only two benchmarks (1 pillar)
    noisy = {b: dict(models) for b, models in raw.items()}   # deep enough: rows copied
    for i in range(80):
        legacy = f"legacy-model-{i}"
        noisy["lm_arena_elo"][legacy] = 1000.0 + i       # far below cohort range
        noisy["openrouter_usage"][legacy] = 0.001
    sigma_noisy = {b: dict(sig) for b, sig in sigma.items()}

    cohort, _ = _cohort(noisy, cfg)
    assert len(cohort) == 12                       # swarm excluded

    base = compute(raw, sigma, as_of, cfg, demo=True, reps=200)
    swarm = compute(noisy, sigma_noisy, as_of, cfg, demo=True, reps=200)
    base_g = {m["model"]: m["g"] for m in base["models"]}
    swarm_g = {m["model"]: m["g"] for m in swarm["models"]}
    assert base_g == swarm_g                       # identical scores
    assert len(swarm["unranked"]) == 80


def test_current_activity_filter_excludes_legacy_models(cfg=None):
    """A fresh usage list defines the current public model roster."""
    cfg = load_config()
    snaps = load_manual_csv(DEMO_DIR / "scores.csv")
    today = dt.date.today().isoformat()
    for snap in snaps.values():
        snap["as_of"] = today
    raw, sigma, as_of, *_ = to_matrix(snaps, cfg)
    # Add a legacy model to every benchmark except the current-activity signal.
    for bid, scores in raw.items():
        if bid != "openrouter_usage":
            scores["legacy model x"] = 9999.0
            sigma[bid]["legacy model x"] = 0.0
    result = compute(raw, sigma, as_of, cfg, demo=True, reps=100)
    listed = {entry["model"] for entry in result["models"]}
    listed.update(entry["model"] for entry in result["unranked"])
    assert "legacy model x" not in listed

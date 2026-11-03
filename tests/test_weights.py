"""Pins config/weights.yaml to METHODOLOGY.md v1.1.0 (§3, §4, §9, §10).

If you intentionally change a weight: bump the methodology version, add a
changelog line, and update the expected numbers here in the same commit.
"""

import pytest

from hierarchy.config import Config, load_config


@pytest.fixture(scope="module")
def cfg() -> Config:
    return load_config()


def test_loads_and_hashes(cfg):
    assert cfg.version == "1.1.0"
    assert len(cfg.config_hash()) == 16


def test_pillar_weights_match_methodology(cfg):
    assert cfg.pillar_weights == {
        "human_preference": 0.35,
        "knowledge_reasoning": 0.20,
        "math": 0.15,
        "coding": 0.20,
        "agentic": 0.10,
    }


def test_benchmark_weights_sum_to_one(cfg):
    total = sum(cfg.bench_weight(b) for b in cfg.bench_ids())
    assert total == pytest.approx(1.0, abs=1e-9)


def test_per_pillar_consistency(cfg):
    for pid, pw in cfg.pillar_weights.items():
        in_pillar = sum(cfg.bench_weight(b) for b in cfg.bench_ids() if cfg.bench_pillar(b) == pid)
        assert in_pillar == pytest.approx(pw, abs=1e-9), pid


def test_headline_benchmark_weights(cfg):
    expected = {
        "lm_arena_elo": 0.25,
        "openrouter_usage": 0.10,
        "gpqa_diamond": 0.08,
        "mmlu_pro": 0.06,
        "livebench_overall": 0.03,
        "seal_average": 0.03,
        "aime_2025": 0.08,
        "hmmt_feb_2025": 0.04,
        "math_500": 0.03,
        "swebench_verified": 0.10,
        "livecodebench": 0.07,
        "terminal_bench": 0.03,
        "tau2_bench": 0.06,
        "terminal_bench_agentic": 0.04,
    }
    assert set(cfg.bench_ids()) == set(expected)
    for bid, w in expected.items():
        assert cfg.bench_weight(bid) == pytest.approx(w), bid


def test_terminal_bench_is_a_split_alias(cfg):
    assert cfg.alias_source("terminal_bench_agentic") == "terminal_bench"
    total = cfg.bench_weight("terminal_bench") + cfg.bench_weight("terminal_bench_agentic")
    assert total == pytest.approx(0.07)  # §4 hybrid benchmarks


def test_normalization_modes_are_registered(cfg):
    for bid in cfg.bench_ids():
        assert cfg.bench_norm_mode(bid) in {"blend", "borda_only", "minmax_only", "elo", "log_share"}
    assert cfg.bench_norm_mode("lm_arena_elo") == "elo"       # §6.4
    assert cfg.bench_norm_mode("openrouter_usage") == "log_share"


def test_coverage_penalty_contract(cfg):
    cp = cfg.aggregation["coverage_penalty"]
    assert cp["base"] + cp["span"] == pytest.approx(1.0)      # §9: full coverage => x1.0
    assert (cp["base"], cp["span"]) == (0.70, 0.30)


def test_uncertainty_contract(cfg):
    u = cfg.uncertainty
    assert u["bootstrap_reps"] >= 1000                         # §10
    assert 0.5 < u["dominance_threshold"] < 1.0
    assert cfg.tiers_cfg["max_tiers"] == 7                     # §11


def test_mirror_and_optional_sources_are_not_scored(cfg):
    sources = cfg.sources["sources"]
    assert sources["llmstat"]["role"] == "mirror"              # §4: never a scored voice
    aa = sources["artanalysis_index"]
    assert aa["role"] == "optional" and not aa.get("enabled")  # off by default


def test_invalid_config_rejected():
    good = load_config().weights
    # pillar weights no longer sum to 1
    bad = dict(good)
    bad["pillars"] = {k: dict(v) for k, v in good["pillars"].items()}
    bad["pillars"]["math"]["weight"] = 0.25
    with pytest.raises(Exception):
        Config(bad, {"sources": {}})

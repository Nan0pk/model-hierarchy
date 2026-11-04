"""Regression tests for the defects behind the single-model 'hierarchy'."""
import copy
import datetime as dt
import json

import pytest

from hierarchy.aggregate import bootstrap, pairwise_probs, benjamini_hochberg, pillar_and_g
from hierarchy.config import DEMO_DIR, load_config
from hierarchy.data import load_manual_csv, load_snapshots, merge_snapshots, to_matrix
from hierarchy.pipeline import _cohort, compute, apply_staleness
from hierarchy.tiers import assign_tiers


def date(days=0):
    return (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=days)).isoformat()


def demo_matrix():
    cfg = load_config()
    snaps = load_manual_csv(DEMO_DIR / "scores.csv")
    for snap in snaps.values():
        snap["as_of"] = date()
        for entry in snap["values"].values():
            entry["as_of"] = date()
    return cfg, to_matrix(snaps, cfg)


def test_single_model_cannot_be_crowned_or_have_a_fake_zero_width_ci():
    cfg, (raw, sigma, dates, _, _, meta) = demo_matrix()
    model = "gpt 5.1"
    raw = {b: {model: rows[model]} for b, rows in raw.items() if model in rows}
    result = compute(raw, sigma, dates, cfg, source_info=meta, reps=100)
    assert result["models"] == [] and result["tiers"] == {} and result["dominance"] == []
    assert result["quality"]["status"] == "withheld"
    assert result["unranked"][0]["model"] == model


def test_alias_counts_once_for_eligibility():
    cfg = load_config()
    raw = {b: {"m": .5} for b in ["terminal_bench", "terminal_bench_agentic", "lm_arena_elo", "gpqa_diamond", "mmlu_pro"]}
    cohort, info = _cohort(raw, cfg)
    assert info["m"]["n_benchmarks"] == 4
    assert not cohort
    assert pillar_and_g(raw, cfg)["m"]["n_benchmarks"] == 4


def test_bootstrap_alias_noise_is_shared(monkeypatch):
    from hierarchy import aggregate
    cfg = load_config()
    raw = {"terminal_bench": {"a": 60, "b": 50}, "terminal_bench_agentic": {"a": 60, "b": 50}}
    sigma = {b: {"a": 10, "b": 10} for b in raw}
    seen = []
    original = aggregate.normalize_all
    def inspect(pert, config):
        seen.append(pert)
        assert pert["terminal_bench"] == pert["terminal_bench_agentic"]
        return original(pert, config)
    monkeypatch.setattr(aggregate, "normalize_all", inspect)
    bootstrap(raw, sigma, cfg, reps=20)
    assert len(seen) == 20


def test_pairwise_ties_have_no_false_significance():
    probs = pairwise_probs({"a": [.5] * 20, "b": [.5] * 20}, ["a", "b"])
    assert probs == {("a", "b"): .5, ("b", "a"): .5}
    assert benjamini_hochberg(probs, ["a", "b"])[("a", "b")] == 1


def test_disjoint_intervals_do_not_bypass_bh_corrected_probabilities():
    entries = [{"model": "a", "median": .9, "lo": .89, "hi": .91},
               {"model": "b", "median": .8, "lo": .79, "hi": .81}]
    tiers = assign_tiers(entries, {("a", "b"): .5, ("b", "a"): .5})
    assert len(tiers) == 1


def test_missing_domain_blocks_a_generalist_hierarchy():
    cfg, (raw, sigma, dates, _, _, meta) = demo_matrix()
    raw = {b: rows for b, rows in raw.items() if cfg.bench_pillar(b) != "math"}
    result = compute(raw, sigma, dates, cfg, source_info=meta, reps=100)
    assert result["cohort_size"] == 12
    assert result["quality"]["missing_pillars"] == ["math"]
    assert not result["models"]
    assert len(result["unranked"]) == 12


def test_row_freshness_cannot_be_laundered_by_newest_date():
    cfg = load_config()
    snaps = {"gpqa_diamond": {"as_of": date(), "values": {
        "Old": {"score": 60, "as_of": date(200)},
        "New": {"score": 70, "as_of": date()},
        "Stale": {"score": 65, "as_of": date(30)},
        "Bad": {"score": 65, "as_of": "oops"},
        "Future": {"score": 65, "as_of": date(-1)},
    }}}
    raw, sigma, dates, _, _, meta = to_matrix(snaps, cfg)
    rejected = []
    stale, excluded = apply_staleness(raw, sigma, dates, cfg, meta, rejected)
    assert set(raw["gpqa_diamond"]) == {"new", "stale"}
    assert stale == ["gpqa_diamond"] and excluded == []
    assert len(rejected) == 3


def test_compute_does_not_mutate_inputs_and_has_reproducible_evidence_hash():
    cfg, (raw, sigma, dates, _, _, meta) = demo_matrix()
    before = copy.deepcopy((raw, sigma, dates, meta))
    result = compute(raw, sigma, dates, cfg, source_info=meta, reps=100, seed=9)
    result2 = compute(raw, sigma, dates, cfg, source_info=meta, reps=100, seed=9)
    assert before == (raw, sigma, dates, meta)
    assert result["models"] == result2["models"]
    assert result["data_hash"] == result2["data_hash"]
    assert result["bootstrap_reps"] == 100 and result["seed"] == 9


def test_manual_row_augments_roster_and_preserves_dates_and_citations(tmp_path):
    path = tmp_path / "scores.csv"
    path.write_text(f"benchmark,model,score,as_of,source,notes\ngpqa_diamond,New,88,{date()},https://new.test,hand checked\n")
    old = {"gpqa_diamond": {"as_of": date(80), "source": "https://old.test", "values": {"Old": {"score": 50}}}}
    merged = merge_snapshots(old, load_manual_csv(path))
    assert len(merged["gpqa_diamond"]["values"]) == 2
    assert merged["gpqa_diamond"]["values"]["Old"]["as_of"] == date(80)
    _, _, _, _, _, meta = to_matrix(merged, load_config())
    assert meta["gpqa_diamond"]["observations"]["new"]["source"] == "https://new.test"
    assert meta["gpqa_diamond"]["observations"]["old"]["source"] == "https://old.test"
    assert old["gpqa_diamond"]["values"]["Old"] == {"score": 50}


def test_older_manual_row_cannot_replace_newer_observation():
    old = {"gpqa_diamond": {"as_of": date(50), "values": {"m": 10}}}
    new = {"gpqa_diamond": {"as_of": date(), "values": {"m": 20, "n": 40}}}
    result = merge_snapshots(new, old)
    assert result["gpqa_diamond"]["values"]["m"]["score"] == 20
    assert len(result["gpqa_diamond"]["values"]) == 2


def test_snapshot_order_uses_published_date_not_directory(tmp_path):
    for folder, published, score in [("2026-01-01", date(), 80), ("2026-12-31", date(80), 20)]:
        path = tmp_path / folder / "gpqa_diamond.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"benchmark": "gpqa_diamond", "as_of": published, "values": {"m": score}}))
    assert load_snapshots(tmp_path)["gpqa_diamond"]["values"]["m"] == 80


@pytest.mark.parametrize("score", ["nan", "inf", "-inf"])
def test_manual_nonfinite_score_rejected(tmp_path, score):
    path = tmp_path / "scores.csv"
    path.write_text(f"benchmark,model,score,as_of\ngpqa_diamond,A,{score},{date()}\n")
    with pytest.raises(ValueError, match="finite"):
        load_manual_csv(path)


def test_canonical_collisions_fail_instead_of_last_row_winning():
    snaps = {"gpqa_diamond": {"as_of": date(), "values": {"Model-A": 60, "model a": 65}}}
    with pytest.raises(ValueError, match="collision"):
        to_matrix(snaps, load_config())


def test_bootstrap_reps_must_support_interval():
    cfg = load_config()
    with pytest.raises(ValueError, match="repetitions"):
        bootstrap({}, {}, cfg, reps=0)


def test_bootstrap_is_invariant_to_input_dict_order():
    cfg, (raw, sigma, _, _, _, _) = demo_matrix()
    reversed_raw = {b: dict(reversed(list(rows.items()))) for b, rows in reversed(list(raw.items()))}
    assert bootstrap(raw, sigma, cfg, reps=30, seed=7) == bootstrap(reversed_raw, sigma, cfg, reps=30, seed=7)

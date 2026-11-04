"""Experimental composite with explicit publication gates and an evidence audit."""
from __future__ import annotations

import copy
import datetime as dt

from . import METHOD_VERSION, __version__
from .aggregate import (bootstrap, benjamini_hochberg, dominance_list, pairwise_probs,
                        point_estimate, summarize_draws)
from .boards import digest
from .tiers import assign_tiers, hierarchy_tree, tier_labels


def _days_old(date_str: str) -> int | None:
    try:
        day = dt.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None
    return (dt.datetime.now(dt.timezone.utc).date() - day).days


def apply_staleness(raw, sigma, as_of, cfg, source_info=None, rejected=None):
    """Prune individual observations, not whole boards using their newest row's date."""
    policy = cfg.aggregation["staleness"]
    stale, excluded = set(), set()
    for bid in list(raw):
        observations = (source_info or {}).get(bid, {}).get("observations", {})
        for model in list(raw[bid]):
            date = observations.get(model, {}).get("as_of", as_of.get(bid))
            age = _days_old(date)
            reason = ("invalid_or_future_date" if age is None or age < 0 else
                      "expired" if age > policy["exclude_after_days"] else None)
            if reason:
                raw[bid].pop(model)
                sigma.get(bid, {}).pop(model, None)
                if rejected is not None:
                    rejected.append({"benchmark": bid, "model": model, "as_of": date, "reason": reason})
            elif age > policy["warn_after_days"]:
                stale.add(bid)
        if not raw[bid]:
            raw.pop(bid)
            sigma.pop(bid, None)
            excluded.add(bid)
    return sorted(stale - excluded), sorted(excluded)


def _cohort(raw, cfg) -> tuple[list, dict]:
    policy = cfg.aggregation["eligibility"]
    cohort, info = [], {}
    for model in sorted({m for rows in raw.values() for m in rows}):
        benches = [b for b in raw if model in raw[b]]
        independent = {cfg.alias_source(b) or b for b in benches}
        pillars = {cfg.bench_pillar(b) for b in benches}
        eligible = len(pillars) >= policy["min_pillars"] and len(independent) >= policy["min_benchmarks"]
        info[model] = {"n_benchmarks": len(independent), "n_pillars": len(pillars), "eligible": eligible}
        if eligible:
            cohort.append(model)
    return cohort, info


def compute(raw, sigma, as_of, cfg, demo=False, reps=None, seed=None, name_map=None,
            source_info=None) -> dict:
    # Re-running a computation must not mutate the caller's retained evidence.
    raw, sigma = copy.deepcopy(raw), copy.deepcopy(sigma)
    source_info = source_info or {}
    evidence_hash = digest({"raw": raw, "sigma": sigma, "dates": as_of, "sources": source_info})
    rejected = []
    stale, excluded = apply_staleness(raw, sigma, as_of, cfg, source_info, rejected)
    roster_raw = copy.deepcopy(raw)
    _, presence = _cohort(raw, cfg)
    policy = cfg.aggregation["eligibility"]
    min_comparators = policy.get("min_comparators", 3)
    # Iterative: dropping a sparse metric may make models ineligible, which can
    # make another metric sparse. Normalization must never run on singletons.
    sparse = set()
    while True:
        cohort, _ = _cohort(raw, cfg)
        cohort_set = set(cohort)
        thin = {b for b, rows in raw.items() if len(cohort_set.intersection(rows)) < min_comparators}
        if not thin:
            break
        sparse.update(thin)
        raw = {b: rows for b, rows in raw.items() if b not in thin}
    cohort_set = set(cohort)
    raw_c = {b: {m: v for m, v in rows.items() if m in cohort_set} for b, rows in raw.items()}
    sigma_c = {b: {m: v for m, v in sigma.get(b, {}).items() if m in cohort_set} for b in raw_c}
    missing_pillars = sorted(set(cfg.pillars) - {cfg.bench_pillar(b) for b in raw_c if raw_c[b]})
    blockers = []
    if len(cohort) < policy.get("min_cohort_size", 5):
        blockers.append(f"Only {len(cohort)} comparable models; need at least {policy.get('min_cohort_size', 5)}.")
    if missing_pillars and policy.get("require_all_pillars", False):
        blockers.append("No comparable data for entire pillars: " + ", ".join(missing_pillars) + ".")

    point, vmat, stats, probs, qvalues, dom, tiers = {}, {}, {}, {}, {}, [], []
    if not blockers:
        point, vmat = point_estimate(raw_c, cfg)
        draws = bootstrap(raw_c, sigma_c, cfg, reps=reps, seed=seed)
        stats = summarize_draws(draws)
        eligible = [m for m in cohort if point[m]["eligible"]]
        probs = pairwise_probs(draws, eligible)
        qvalues = benjamini_hochberg(probs, eligible)
        tier_probs = dict(probs)
        for (a, b), q in qvalues.items():
            if q > 0.05:
                tier_probs[(a, b)] = tier_probs[(b, a)] = 0.5
        dom = [d for d in dominance_list(probs, eligible, cfg.uncertainty["dominance_threshold"])
               if qvalues.get(tuple(sorted((d["a"], d["b"]))), 1) <= 0.05]
        entries = sorted(({"model": m, **stats[m]} for m in eligible),
                         key=lambda e: (-e["median"], e["model"]))
        tiers = assign_tiers(entries, tier_probs, max_tiers=cfg.tiers_cfg["max_tiers"],
                             confidence=cfg.tiers_cfg["separation_confidence"])
    else:
        entries = []
    tier_map = tier_labels(tiers)
    model_tier = {m: label for label, members in tier_map.items() for m in members}
    ranked = []
    for rank, e in enumerate(entries, 1):
        model, p = e["model"], point[e["model"]]
        benchmarks = {}
        for bid in p["benchmarks_present"]:
            meta = source_info.get(bid, {}).get("observations", {}).get(model, {})
            benchmarks[bid] = {"raw": raw_c[bid][model], "value": round(vmat[bid][model] * 100, 1),
                               "as_of": meta.get("as_of", as_of.get(bid)),
                               "source": meta.get("source", source_info.get(bid, {}).get("source")),
                               "harness": meta.get("harness")}
        flags = list(p["flags"])
        if any(_days_old(b["as_of"]) > cfg.aggregation["staleness"]["warn_after_days"] for b in benchmarks.values()):
            flags.append("stale_evidence")
        ranked.append({"rank": rank, "model": model, "tier": model_tier[model],
                       "g": round(e["median"] * 100, 1), "g_point": round(p["g"] * 100, 1),
                       "ci95": [round(e["lo"] * 100, 1), round(e["hi"] * 100, 1)],
                       "pillars": {pid: {"score": round(ps * 100, 1), "coverage": round(p["pillar_coverage"][pid], 3)}
                                   for pid, ps in p["pillars"].items()},
                       "benchmarks": benchmarks, "coverage": round(p["coverage"], 3),
                       "n_benchmarks": p["n_benchmarks"], "flags": flags})
    listed = {e["model"] for e in ranked}
    unranked = [{"model": model, **info,
                 "benchmarks": sorted(b for b, rows in roster_raw.items() if model in rows),
                 "reason": "publication_gate" if info["eligible"] else "insufficient_comparable_evidence"}
                for model, info in presence.items() if model not in listed]
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "tool_version": __version__, "method": f"Experimental composite · methodology v{METHOD_VERSION}",
        "weights_version": cfg.version, "config_hash": cfg.config_hash(), "data_hash": evidence_hash,
        "bootstrap_reps": cfg.uncertainty["bootstrap_reps"] if reps is None else reps,
        "seed": cfg.uncertainty["seed"] if seed is None else seed,
        "demo": demo, "cohort_size": len(cohort), "data_as_of": as_of,
        "pillar_weights": cfg.pillar_weights, "aggregation": cfg.aggregation,
        "source_provenance": source_info, "stale": stale, "excluded_stale": excluded,
        "name_reconciliation": name_map or {}, "models": ranked, "unranked": unranked,
        "tiers": tier_map, "dominance": dom,
        "pairwise_bh_qvalues": {f"{a} | {b}": round(q, 6) for (a, b), q in qvalues.items()},
        "quality": {"status": "withheld" if blockers else "experimental", "blockers": blockers,
                    "roster_size": len(presence), "excluded_sparse": sorted(sparse),
                    "missing_pillars": missing_pillars, "rejected_observations": rejected,
                    "note": "Usage is not capability or eligibility. Missing data is not evidence of a weak model."},
    }


def tree_text(result: dict) -> str:
    if result.get("quality", {}).get("blockers"):
        return "Composite withheld: " + " ".join(result["quality"]["blockers"])
    return hierarchy_tree(result["tiers"], result["generated_at"], demo=result["demo"])

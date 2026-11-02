"""End-to-end pipeline: snapshots -> result dict (see cli.py and render.py).

Implements METHODOLOGY.md §5 (cohort: normalization happens WITHIN the eligible
cohort only), §10 (bootstrap + dominance), §11 (tiers), §12 (staleness,
name reconciliation report).
"""

from __future__ import annotations

import datetime as dt

from . import METHOD_VERSION, __version__
from .aggregate import (
    bootstrap,
    benjamini_hochberg,
    dominance_list,
    pairwise_probs,
    point_estimate,
    summarize_draws,
)
from .tiers import assign_tiers, hierarchy_tree, tier_labels


def _days_old(date_str: str) -> int:
    try:
        d = dt.date.fromisoformat(str(date_str)[:10])
    except ValueError:
        return 0
    return (dt.datetime.now(dt.timezone.utc).date() - d).days


def apply_staleness(raw, sigma, as_of, cfg):
    """§12: flag stale (>14d) and exclude (>120d) benchmarks from aggregation."""
    warn_after = cfg.aggregation["staleness"]["warn_after_days"]
    exclude_after = cfg.aggregation["staleness"]["exclude_after_days"]
    stale, excluded = [], []
    for bid in list(raw.keys()):
        age = _days_old(as_of.get(bid, ""))
        if age > exclude_after:
            excluded.append(bid)
            raw.pop(bid)
            sigma.pop(bid, None)
        elif age > warn_after:
            stale.append(bid)
    return stale, excluded


def _cohort(raw, cfg) -> tuple[list, dict]:
    """§5: models meeting the pillar/benchmark minimums, computed on raw presence.

    Returns (cohort_models, presence_info) — normalization MUST be restricted
    to this cohort so that non-cohort rows (e.g. 100 legacy models on an Arena
    pull) cannot stretch the min-max/borda scales of the hierarchy.
    """
    min_pillars = cfg.aggregation["eligibility"]["min_pillars"]
    min_bench = cfg.aggregation["eligibility"]["min_benchmarks"]
    models = sorted({m for bench in raw.values() for m in bench})
    cohort, info = [], {}
    for m in models:
        benches = [b for b in raw if m in raw[b]]
        pillars = {cfg.bench_pillar(b) for b in benches}
        present = len(pillars) >= min_pillars and len(benches) >= min_bench
        info[m] = {"n_benchmarks": len(benches), "n_pillars": len(pillars), "eligible": present}
        if present:
            cohort.append(m)
    return cohort, info


def compute(raw, sigma, as_of, cfg, demo: bool = False, reps: int | None = None,
            seed: int | None = None, name_map: dict | None = None) -> dict:
    stale, excluded = apply_staleness(raw, sigma, as_of, cfg)
    cohort, presence = _cohort(raw, cfg)

    # restrict every subsequent step to the cohort (§5)
    cohort_set = set(cohort)
    raw_c = {b: {m: v for m, v in models.items() if m in cohort_set}
             for b, models in raw.items() if any(m in cohort_set for m in models)}
    sigma_c = {b: {m: s for m, s in sig.items() if m in cohort_set}
               for b, sig in sigma.items() if b in raw_c}

    point, vmat = point_estimate(raw_c, cfg)
    draws = bootstrap(raw_c, sigma_c, cfg, reps=reps, seed=seed)
    stats = summarize_draws(draws)

    eligible = [m for m, r in point.items() if r["eligible"]]
    probs = pairwise_probs(draws, eligible)
    qvalues = benjamini_hochberg(probs, eligible)
    # Retain the existing directional confidence threshold, but only separate
    # tiers where the pairwise bootstrap evidence survives BH correction.
    tier_probs = dict(probs)
    for (a, b), q in qvalues.items():
        if q > 0.05:
            tier_probs[(a, b)] = tier_probs[(b, a)] = 0.5
    dom = dominance_list(probs, eligible, cfg.uncertainty["dominance_threshold"])
    dom = [d for d in dom if qvalues.get(tuple(sorted((d["a"], d["b"]))), 1.0) <= 0.05]

    entries = sorted(({"model": m, **stats[m]} for m in eligible), key=lambda e: -e["median"])
    tiers = assign_tiers(
        entries, tier_probs,
        max_tiers=cfg.tiers_cfg["max_tiers"],
        confidence=cfg.tiers_cfg["separation_confidence"],
    )
    tier_map = tier_labels(tiers)
    model_tier = {e["model"]: f"T{i + 1}" for i, t in enumerate(tiers) for e in t}

    ranked = []
    for rank, e in enumerate(entries, start=1):
        m = e["model"]
        p = point[m]
        ranked.append({
            "rank": rank,
            "model": m,
            "tier": model_tier.get(m, "—"),
            "g": round(e["median"] * 100, 1),
            "g_point": round(p["g"] * 100, 1),
            "ci95": [
                min(round(e["lo"] * 100, 1), round(e["median"] * 100, 1)),
                max(round(e["hi"] * 100, 1), round(e["median"] * 100, 1)),
            ],
            "pillars": {
                pid: {
                    "score": round(ps * 100, 1),
                    "coverage": round(p["pillar_coverage"][pid], 3),
                }
                for pid, ps in p["pillars"].items()
            },
            "benchmarks": {
                bid: {
                    "raw": raw_c[bid][m],
                    "value": round(vmat[bid][m] * 100, 1),
                    "as_of": as_of.get(bid),
                }
                for bid in p["benchmarks_present"]
            },
            "coverage": round(p["coverage"], 3),
            "n_benchmarks": p["n_benchmarks"],
            "flags": p["flags"],
        })

    unranked = [
        {
            "model": m,
            "n_benchmarks": info["n_benchmarks"],
            "n_pillars": info["n_pillars"],
            "benchmarks": sorted(b for b in raw if m in raw[b]),
        }
        for m, info in sorted(presence.items())
        if not info["eligible"]
    ]

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "tool_version": __version__,
        "method": f"model-hierarchy methodology v{METHOD_VERSION}",
        "weights_version": cfg.version,
        "config_hash": cfg.config_hash(),
        "demo": demo,
        "cohort_size": len(cohort),
        "data_as_of": as_of,
        "stale": sorted(stale),
        "excluded_stale": sorted(excluded),
        "name_reconciliation": name_map or {},
        "models": ranked,
        "unranked": unranked,
        "tiers": tier_map,
        "dominance": dom,
        "pairwise_bh_qvalues": {f"{a} | {b}": round(q, 6) for (a, b), q in qvalues.items()},
    }


def tree_text(result: dict) -> str:
    return hierarchy_tree(result["tiers"], result["generated_at"], demo=result["demo"])

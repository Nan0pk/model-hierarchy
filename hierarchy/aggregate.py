"""Aggregation engine (METHODOLOGY.md §5, §7–§10).

Pipeline: raw scores -> normalize (§6) -> pillar arithmetic means with weight
renormalization (§7) -> cross-pillar weighted geometric mean (§8) -> coverage
penalty (§9) -> parametric bootstrap for CIs and pairwise probabilities (§10).
"""

from __future__ import annotations

import random

from .normalize import normalize_all

PREFERENCE_BENCHES = ("lm_arena_elo", "openrouter_usage")


# --------------------------------------------------------------------------
# §7 + §8 + §9: point estimates
# --------------------------------------------------------------------------
def pillar_and_g(vmat: dict, cfg) -> dict:
    """Per-model pillar scores, geometric aggregate, coverage, penalty, flags."""
    agg = cfg.aggregation
    floor_v = agg["value_floor"]
    floor_p = agg["pillar_floor"]
    base, span = agg["coverage_penalty"]["base"], agg["coverage_penalty"]["span"]
    min_pillars = agg["eligibility"]["min_pillars"]
    min_bench = agg["eligibility"]["min_benchmarks"]

    models = sorted({m for bench in vmat.values() for m in bench})
    out: dict[str, dict] = {}

    for m in models:
        # ---- §7 within-pillar: coverage-renormalized weighted arithmetic mean
        pillar_scores: dict[str, float] = {}
        pillar_cov: dict[str, float] = {}
        for pid, pw in cfg.pillar_weights.items():
            benches = [
                b for b in cfg.bench_ids()
                if cfg.bench_pillar(b) == pid and m in vmat.get(b, {})
            ]
            if not benches:
                continue
            wsum = sum(cfg.bench_weight(b) for b in benches)
            ps = sum(cfg.bench_weight(b) * vmat[b][m] for b in benches) / wsum
            pillar_scores[pid] = max(floor_p, max(floor_v, ps))
            pillar_cov[pid] = wsum / pw  # share of pillar weight covered

        # ---- §8 across pillars: weighted geometric mean, weights redistributed
        wpresent = sum(cfg.pillar_weights[p] for p in pillar_scores)
        g = 1.0
        for pid, ps in pillar_scores.items():
            g *= ps ** (cfg.pillar_weights[pid] / wpresent)

        # ---- §9 coverage penalty: C = sum of global weights present
        present_bench = [b for b in cfg.bench_ids() if m in vmat.get(b, {})]
        C = sum(cfg.bench_weight(b) for b in present_bench)
        penalty = base + span * C
        g_final = g * penalty

        n_pillars = len(pillar_scores)
        eligible = n_pillars >= min_pillars and len(present_bench) >= min_bench
        flags = []
        if not any(b in PREFERENCE_BENCHES for b in present_bench):
            flags.append("no_preference_signal")
        if not eligible:
            flags.append("insufficient_data")

        out[m] = {
            "g": g_final,
            "g_raw": g,
            "pillars": pillar_scores,
            "pillar_coverage": pillar_cov,
            "benchmarks_present": present_bench,
            "coverage": C,
            "penalty": penalty,
            "n_pillars": n_pillars,
            "n_benchmarks": len(present_bench),
            "eligible": eligible,
            "flags": flags,
        }
    return out


def point_estimate(raw: dict, cfg) -> tuple[dict, dict]:
    """Full point-estimate path: normalize then aggregate. Returns (result, vmat)."""
    vmat = normalize_all(raw, cfg)
    return pillar_and_g(vmat, cfg), vmat


# --------------------------------------------------------------------------
# §10: parametric bootstrap
# --------------------------------------------------------------------------
def bootstrap(raw: dict, sigma: dict, cfg, reps: int | None = None, seed: int | None = None):
    """Perturb raw scores with N(0, sigma) and re-run the FULL pipeline per draw.

    Returns draws = {model: [G per rep]}.
    """
    u = cfg.uncertainty
    reps = int(reps or u["bootstrap_reps"])
    rng = random.Random(u["seed"] if seed is None else seed)
    models = sorted({m for bench in raw.values() for m in bench})
    draws: dict[str, list[float]] = {m: [] for m in models}

    benches = list(raw.keys())
    for _ in range(reps):
        pert = {
            b: {
                m: v + rng.gauss(0, sigma.get(b, {}).get(m, 0.0))
                for m, v in raw[b].items()
            }
            for b in benches
        }
        res = pillar_and_g(normalize_all(pert, cfg), cfg)
        for m in models:
            draws[m].append(res[m]["g"])
    return draws


def summarize_draws(draws: dict) -> dict:
    """Median + 95% percentile interval per model."""
    out = {}
    for m, vals in draws.items():
        s = sorted(vals)
        n = len(s)
        def pct(p):
            k = (n - 1) * p
            f = int(k)
            c = min(f + 1, n - 1)
            return s[f] + (k - f) * (s[c] - s[f])
        out[m] = {
            "median": pct(0.5),
            "lo": pct(0.025),
            "hi": pct(0.975),
        }
    return out


def pairwise_probs(draws: dict, models: list) -> dict:
    """P[A > B] per ordered pair, computed across bootstrap draws (§10)."""
    probs = {}
    for a in models:
        for b in models:
            if a == b:
                continue
            da, db = draws[a], draws[b]
            wins = sum(1 for x, y in zip(da, db) if x > y)
            probs[(a, b)] = wins / len(da)
    return probs


def dominance_list(probs: dict, models: list, threshold: float) -> list:
    """Directed 'confidently better' pairs with p >= threshold (§10).

    For each unordered pair exactly one direction is reported — the dominant
    one — so the list reads as a set of confident statements "a ≻ b".
    """
    dom = []
    for (a, b), p in probs.items():
        if a >= b:
            continue
        q = probs.get((b, a), 0.0)
        if p >= threshold:
            dom.append({"a": a, "b": b, "p": round(p, 4)})
        elif q >= threshold:
            dom.append({"a": b, "b": a, "p": round(q, 4)})
    dom.sort(key=lambda d: (-d["p"], d["a"], d["b"]))
    return dom

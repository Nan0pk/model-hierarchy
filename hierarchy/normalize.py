"""Normalization (METHODOLOGY.md §6).

Borda + clipped min-max blend by default; min-max only for Elo; log + min-max
for usage share. All outputs live in [value_floor, 1.0].
"""

from __future__ import annotations

import math

VALUE_FLOOR = 0.02


# --------------------------------------------------------------------------
# rank helpers
# --------------------------------------------------------------------------
def _average_ranks_desc(values: list[float]) -> list[float]:
    """1-based ranks, descending by value, ties share the average rank."""
    order = sorted(range(len(values)), key=lambda i: -values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def borda(scores: dict[str, float]) -> dict[str, float]:
    """B(m) = (N - rank) / (N - 1) in [0,1]; 1 = best (§6.1)."""
    if len(scores) <= 1:
        return {m: 1.0 for m in scores}
    vals = list(scores.values())
    ranks = _average_ranks_desc(vals)
    n = len(vals)
    return {m: (n - r) / (n - 1) for m, r in zip(scores.keys(), ranks)}


# --------------------------------------------------------------------------
# scale helpers
# --------------------------------------------------------------------------
def _percentile(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolated percentile of an already-sorted list (p in 0..100)."""
    if not sorted_vals:
        raise ValueError("percentile of empty list")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


def minmax(scores: dict[str, float], clip: tuple[float, float] | None = (5.0, 95.0)) -> dict[str, float]:
    """Min-max to [0,1], optionally after clipping to cohort percentiles (§6.2).

    clip=None (used for Elo) skips percentile clipping: the cohort is tight and
    Elo gaps are the signal.
    """
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if clip is not None:
        svals = sorted(vals)
        lo = _percentile(svals, clip[0])
        hi = _percentile(svals, clip[1])
        if hi <= lo:  # degenerate after clipping -> fall back to raw extremes
            lo, hi = min(vals), max(vals)
    if hi <= lo:
        return {m: 0.5 for m in scores}
    return {m: min(1.0, max(0.0, (s - lo) / (hi - lo))) for m, s in scores.items()}


# --------------------------------------------------------------------------
# per-benchmark dispatch
# --------------------------------------------------------------------------
def normalize_benchmark(scores: dict[str, float], mode: str, higher_better: bool = True) -> dict[str, float]:
    """Map one benchmark's raw scores to v in [VALUE_FLOOR, 1.0] (§6)."""
    if not scores:
        return {}
    if not higher_better:
        scores = {m: -s for m, s in scores.items()}

    if mode == "borda_only":
        v = borda(scores)
    elif mode == "minmax_only":
        v = minmax(scores)
    elif mode == "elo":
        v = minmax(scores, clip=None)
    elif mode == "log_share":
        lg = {m: math.log10(max(float(s), 0.0) + 1e-6) for m, s in scores.items()}
        v = minmax(lg, clip=None)
    elif mode == "blend":
        b = borda(scores)
        mm = minmax(scores)
        v = {m: 0.5 * b[m] + 0.5 * mm[m] for m in scores}
    else:
        raise ValueError(f"unknown normalization mode: {mode}")

    return {m: max(VALUE_FLOOR, val) for m, val in v.items()}


def normalize_all(raw: dict[str, dict[str, float]], cfg) -> dict[str, dict[str, float]]:
    """Normalize every benchmark in the matrix (mode/direction from config)."""
    out: dict[str, dict[str, float]] = {}
    for bench_id, models in raw.items():
        mode = cfg.bench_norm_mode(bench_id)
        hb = cfg.bench_higher_better(bench_id)
        out[bench_id] = normalize_benchmark(models, mode, hb)
    return out

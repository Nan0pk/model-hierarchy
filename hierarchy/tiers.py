"""Tier assignment (METHODOLOGY.md §11).

Greedy, anchored separation: walk down the median-sorted list; a new tier opens
when the candidate is separated from the CURRENT TIER'S ANCHOR (its best
member) — by disjoint bootstrap CIs or P(anchor > candidate) >= threshold.
Same tier means statistically indistinguishable on current data.
"""

from __future__ import annotations


def assign_tiers(
    entries: list[dict],
    probs: dict,
    max_tiers: int = 7,
    confidence: float = 0.95,
) -> list[list[dict]]:
    """entries: [{model, median, lo, hi}, ...] sorted by median desc."""
    if not entries:
        return []
    tiers: list[list[dict]] = []
    current: list[dict] = [entries[0]]
    anchor = entries[0]

    for cand in entries[1:]:
        separated = (
            cand["hi"] < anchor["lo"]
            or probs.get((anchor["model"], cand["model"]), 0.0) >= confidence
        )
        if separated and len(tiers) < max_tiers - 1:
            tiers.append(current)
            current = [cand]
            anchor = cand
        else:
            current.append(cand)
    tiers.append(current)
    return tiers


def tier_labels(tiers: list[list[dict]]) -> dict:
    return {f"T{i + 1}": [e["model"] for e in tier] for i, tier in enumerate(tiers)}


def hierarchy_tree(tier_map: dict, generated_at: str, demo: bool = False) -> str:
    lines = [
        f"Tier hierarchy (G-score 0-100) — generated {generated_at}"
        + (" — SYNTHETIC DEMO DATA" if demo else ""),
        "─" * 64,
    ]
    for label in sorted(tier_map, key=lambda t: int(t[1:])):
        lines.append(f"{label} │ " + " · ".join(sorted(tier_map[label])))
    lines.append("─" * 64)
    lines.append("Same tier = statistically indistinguishable on current data (METHODOLOGY.md §11).")
    return "\n".join(lines)

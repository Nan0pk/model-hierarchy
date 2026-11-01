"""Rendering: README sections, leaderboard.json / .csv (METHODOLOGY.md §11)."""

from __future__ import annotations

import csv
import json
import pathlib

PILLAR_ORDER = ["human_preference", "knowledge_reasoning", "math", "coding", "agentic"]
PILLAR_SHORT = {
    "human_preference": "Hum.",
    "knowledge_reasoning": "Know.",
    "math": "Math",
    "coding": "Code",
    "agentic": "Agent",
}

README_MARKERS = ("<!-- leaderboard:start -->", "<!-- leaderboard:end -->")
DEMO_MARKERS = ("<!-- demo-leaderboard:start -->", "<!-- demo-leaderboard:end -->")


def markdown_table(result: dict, top_n: int = 25) -> str:
    from .tiers import hierarchy_tree  # local import to avoid cycle at load time

    lines = []
    if result.get("demo"):
        lines.append("> ⚠️ **Synthetic demo data** (see `demo/scores.csv`) — illustrates the output "
                     "shape only. Run `python -m hierarchy run` for a real leaderboard.")
        lines.append("")
    lines.append(hierarchy_tree(result["tiers"], result["generated_at"], demo=result.get("demo", False)))
    lines.append("")
    lines.append("| # | Model | Tier | G | 95% CI | " + " | ".join(PILLAR_SHORT[p] for p in PILLAR_ORDER) + " | Cov. | Flags |")
    lines.append("|---|-------|------|---|--------|" + "---|" * len(PILLAR_ORDER) + "------|-------|")

    for e in result["models"][:top_n]:
        pillars = [
            f"{e['pillars'][p]['score']:.0f}" if p in e["pillars"] else "–"
            for p in PILLAR_ORDER
        ]
        ci = f"{e['ci95'][0]:.1f}–{e['ci95'][1]:.1f}"
        flags = ", ".join(e["flags"]) if e["flags"] else "–"
        lines.append(
            f"| {e['rank']} | `{e['model']}` | {e['tier']} | **{e['g']:.1f}** | {ci} | "
            + " | ".join(pillars) + f" | {e['coverage'] * 100:.0f}% | {flags} |"
        )

    if result.get("stale"):
        lines.append("")
        lines.append(f"*Stale (>14d): {', '.join(result['stale'])}*")
    if result.get("excluded_stale"):
        lines.append(f"*Excluded (>120d): {', '.join(result['excluded_stale'])}*")
    if result.get("unranked"):
        shown = [f"`{u['model']}`" for u in result["unranked"][:15]]
        more = len(result["unranked"]) - len(shown)
        suffix = f" … and {more} more in `output/leaderboard.json`" if more > 0 else ""
        lines.append("")
        lines.append(f"*Unranked (insufficient data, §5): {', '.join(shown)}{suffix}*")
    if not result.get("tiers"):
        lines.append("")
        lines.append("*No tiers yet — tier assignment requires data from at least 3 pillars "
                     "(§5). Fill `data/manual/scores.csv` or wire more sources in "
                     "`config/sources.yaml`.*")
    return "\n".join(lines)


def csv_rows(result: dict) -> list[dict]:
    rows = []
    for e in result["models"]:
        rows.append({
            "rank": e["rank"],
            "model": e["model"],
            "tier": e["tier"],
            "g": e["g"],
            "ci_lo": e["ci95"][0],
            "ci_hi": e["ci95"][1],
            **{p: e["pillars"].get(p, {}).get("score") for p in PILLAR_ORDER},
            "coverage": e["coverage"],
            "flags": ";".join(e["flags"]),
        })
    return rows


def write_outputs(result: dict, out_dir: pathlib.Path, demo: bool = False) -> tuple:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "demo_leaderboard" if demo else "leaderboard"
    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(csv_rows(result)[0].keys()) if result["models"]
                                else ["rank", "model", "tier", "g", "ci_lo", "ci_hi", "coverage", "flags"])
        writer.writeheader()
        writer.writerows(csv_rows(result))
    return json_path, csv_path


def update_readme(readme_path: pathlib.Path, content: str, markers=README_MARKERS) -> bool:
    """Replace the section between markers; append a section if markers absent."""
    if not readme_path.exists():
        return False
    text = readme_path.read_text()
    start, end = markers
    if start in text and end in text:
        pre = text.split(start)[0]
        post = text.split(end)[1]
        new = f"{pre}{start}\n\n{content}\n\n{end}{post}"
    else:
        new = f"{text.rstrip()}\n\n{start}\n\n{content}\n\n{end}\n"
    if new == text:
        return False
    readme_path.write_text(new)
    return True

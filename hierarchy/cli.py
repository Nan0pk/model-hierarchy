"""CLI: python -m hierarchy <command> (see README for the full guide)."""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, DEMO_DIR, OUTPUT_DIR, ROOT, load_config
from .data import load_manual_csv, load_snapshots, merge_snapshots, to_matrix, today
from .fetch import fetch_all
from .fetch.base import ADAPTERS
from .pipeline import compute, tree_text
from .render import DEMO_MARKERS, README_MARKERS, markdown_table, update_readme, write_outputs


def cmd_validate(args) -> int:
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"config ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"config OK — methodology v{cfg.version}, config_hash {cfg.config_hash()}")
    print(f"pillars   : " + ", ".join(f"{pid}={w:.2f}" for pid, w in cfg.pillar_weights.items()))
    print(f"benchmarks: {len(cfg.bench_ids())} registered, weights sum "
          f"{sum(cfg.bench_weight(b) for b in cfg.bench_ids()):.2f}")
    for bid in cfg.bench_ids():
        b = cfg.benchmarks[bid]
        alias = f" (alias_of {b['alias_of']})" if b.get("alias_of") else ""
        print(f"  {bid:<24} {b['pillar']:<20} w={b['weight']:.2f} norm={b['normalization']}{alias}")
    active = [
        sid for sid, source in cfg.sources.get("sources", {}).items()
        if source.get("role", "scored") == "scored" and source.get("kind") in ADAPTERS
    ]
    manual = [
        sid for sid, source in cfg.sources.get("sources", {}).items()
        if source.get("role", "scored") == "scored" and source.get("kind") == "manual"
    ]
    print(f"automatic sources: {', '.join(active) or 'none'}")
    print(f"manual-only sources: {', '.join(manual) or 'none'}")
    return 0


def _run_matrix(raw, sigma, as_of, cfg, demo: bool, reps=None, name_map=None) -> int:
    if not raw:
        print("No data found. Run `python -m hierarchy fetch --allow-missing` and/or fill "
              "data/manual/scores.csv (see config/sources.yaml fallback_note per benchmark).")
        return 1
    result = compute(raw, sigma, as_of, cfg, demo=demo, reps=reps, name_map=name_map)
    json_path, csv_path = write_outputs(result, OUTPUT_DIR, demo=demo)
    table = markdown_table(result)
    readme = ROOT / "README.md"
    markers = DEMO_MARKERS if demo else README_MARKERS
    if update_readme(readme, table, markers):
        print(f"README.md section updated")
    print(tree_text(result))
    print(f"\nwrote {json_path.relative_to(ROOT)} and {csv_path.relative_to(ROOT)}")
    return 0


def cmd_demo(args) -> int:
    cfg = load_config()
    snaps = load_manual_csv(DEMO_DIR / "scores.csv")
    for snap in snaps.values():  # keep the demo evergreen: re-date to today
        snap["as_of"] = today()
    raw, sigma, as_of, skipped, name_map = to_matrix(snaps, cfg)
    if skipped:
        print(f"demo CSV: skipping unregistered benchmarks: {sorted(skipped)}")
    return _run_matrix(raw, sigma, as_of, cfg, demo=True, reps=args.reps, name_map=name_map)


def cmd_aggregate(args) -> int:
    cfg = load_config()
    snaps = merge_snapshots(load_snapshots(), load_manual_csv())
    raw, sigma, as_of, skipped, name_map = to_matrix(snaps, cfg)
    if skipped:
        print(f"skipping unregistered benchmarks: {sorted(skipped)}")
    return _run_matrix(raw, sigma, as_of, cfg, demo=False, reps=args.reps, name_map=name_map)


def cmd_fetch(args) -> int:
    cfg = load_config()
    written, failures = fetch_all(cfg, allow_missing=args.allow_missing)
    print(f"fetch done: {len(written)} written, {len(failures)} failed (see messages above).")
    if failures and not args.allow_missing:
        return 1
    return 0


def cmd_run(args) -> int:
    cmd_fetch(argparse.Namespace(allow_missing=True))
    return cmd_aggregate(argparse.Namespace(reps=args.reps))


def cmd_render(args) -> int:
    import json
    cfg = load_config()
    path = OUTPUT_DIR / "leaderboard.json"
    if not path.exists():
        print(f"{path} does not exist — run `python -m hierarchy aggregate` first.")
        return 1
    result = json.loads(path.read_text())
    result.setdefault("tiers", {})
    table = markdown_table(result)
    if update_readme(ROOT / "README.md", table, README_MARKERS):
        print("README.md leaderboard section re-rendered")
    else:
        print("README.md already up to date")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="hierarchy", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="check config ↔ methodology consistency")

    d = sub.add_parser("demo", help="end-to-end run on bundled synthetic demo data")
    d.add_argument("--reps", type=int, default=None, help="override bootstrap reps")

    a = sub.add_parser("aggregate", help="aggregate latest snapshots + manual CSV")
    a.add_argument("--reps", type=int, default=None, help="override bootstrap reps")
    sub.add_parser("render", help="re-render README from output/leaderboard.json")

    f = sub.add_parser("fetch", help="run fetch adapters (soft-fail per source)")
    f.add_argument("--allow-missing", action="store_true", default=True,
                   help="exit 0 even if some sources fail (default)")

    r = sub.add_parser("run", help="fetch + aggregate (the daily job)")
    r.add_argument("--reps", type=int, default=None, help="override bootstrap reps")

    args = p.parse_args(argv)
    return {
        "validate": cmd_validate,
        "demo": cmd_demo,
        "aggregate": cmd_aggregate,
        "fetch": cmd_fetch,
        "render": cmd_render,
        "run": cmd_run,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

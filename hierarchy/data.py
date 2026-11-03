"""Data loading: committed snapshots + the guaranteed manual CSV path (§12).

Snapshot format: data/raw/YYYY-MM-DD/<bench_id>.json
    {"benchmark": <id>, "as_of": "YYYY-MM-DD",
     "values": {"<model>": {"score": <float>, "ci95": [lo, hi] | optional}}}

Manual CSV (data/manual/scores.csv or demo/scores.csv):
    benchmark,model,score,as_of,source,notes[,ci95_lo,ci95_hi]
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import pathlib

from .config import DATA_DIR
from .names import canonical

MANUAL_CSV_FIELDS = ("benchmark", "model", "score", "as_of", "source", "notes")


def today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def load_snapshots(raw_dir: pathlib.Path = DATA_DIR / "raw") -> dict:
    """Latest snapshot per benchmark id across data/raw/<date>/<bench>.json."""
    snaps: dict[str, dict] = {}
    if not raw_dir.exists():
        return snaps
    for day_dir in sorted(raw_dir.iterdir()):
        if not day_dir.is_dir():
            continue
        for f in sorted(day_dir.glob("*.json")):
            try:
                snap = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            bid = snap.get("benchmark") or f.stem
            prev = snaps.get(bid)
            if prev is None or str(day_dir.name) >= prev["_day"]:
                snap["_day"] = str(day_dir.name)
                snaps[bid] = snap
    for snap in snaps.values():
        snap.pop("_day", None)
    return snaps


def load_manual_csv(csv_path: pathlib.Path | None = None) -> dict:
    """Manual CSV rows -> snapshot-shaped dict {bench: {as_of, values}}."""
    if csv_path is None:
        csv_path = DATA_DIR / "manual" / "scores.csv"
    snaps: dict[str, dict] = {}
    if not csv_path.exists():
        return snaps
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"benchmark", "model", "score", "as_of"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{csv_path}: missing required CSV columns: {sorted(missing)}")
        for line, row in enumerate(reader, start=2):
            row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
            if not row.get("benchmark") or not row.get("model"):
                raise ValueError(f"{csv_path}:{line}: benchmark and model must be non-empty")
            bid, model = row["benchmark"], row["model"]
            try:
                score = float(row["score"])
                if not math.isfinite(score):
                    raise ValueError
                dt.date.fromisoformat(row["as_of"])
            except (TypeError, ValueError):
                raise ValueError(f"{csv_path}:{line}: score must be finite and as_of must be YYYY-MM-DD") from None
            entry = {"score": score}
            lo, hi = row.get("ci95_lo"), row.get("ci95_hi")
            try:
                if lo not in (None, "") and hi not in (None, ""):
                    entry["ci95"] = [float(lo), float(hi)]
            except ValueError:
                pass
            as_of = row.get("as_of") or today()
            snap = snaps.setdefault(bid, {"benchmark": bid, "as_of": as_of, "values": {}})
            snap["values"][model] = entry
            if as_of > snap["as_of"]:
                snap["as_of"] = as_of
    return snaps


def merge_snapshots(*snapshot_dicts: dict) -> dict:
    """Union of snapshot dicts; newest as_of wins per benchmark."""
    merged: dict[str, dict] = {}
    for snaps in snapshot_dicts:
        for bid, snap in snaps.items():
            prev = merged.get(bid)
            if prev is None or str(snap.get("as_of", "")) >= str(prev.get("as_of", "")):
                merged[bid] = snap
    return merged


def to_matrix(snapshots: dict, cfg) -> tuple[dict, dict, dict, set, dict, dict]:
    """Snapshots -> score matrices plus benchmark-level source provenance.

    Returns raw scores, noise, evaluation dates, skipped benchmark IDs,
    name reconciliation, and source/methodology metadata.
    """
    registered = set(cfg.bench_ids())
    # map alias -> source benchmark snapshot
    resolved: dict[str, dict] = {}
    for bid in registered:
        src = cfg.alias_source(bid) or bid
        if src in snapshots:
            resolved[bid] = snapshots[src]

    raw: dict[str, dict[str, float]] = {}
    sigma: dict[str, dict[str, float]] = {}
    as_of: dict[str, str] = {}
    name_map: dict[str, str] = {}
    source_info: dict[str, dict] = {}
    skipped = set(snapshots) - registered - {cfg.alias_source(b) for b in registered if cfg.alias_source(b)}
    for bid, snap in resolved.items():
        vals = snap.get("values", {})
        raw[bid] = {}
        sigma[bid] = {}
        for model, entry in vals.items():
            cname = canonical(model)
            name_map[str(model)] = cname
            if isinstance(entry, dict):
                score = float(entry["score"])
                ci = entry.get("ci95")
            else:  # bare number tolerated
                score, ci = float(entry), None
            raw[bid][cname] = score
            if ci and len(ci) == 2 and ci[1] > ci[0]:
                sigma[bid][cname] = (ci[1] - ci[0]) / 3.92
            else:
                sigma[bid][cname] = cfg.bench_noise_raw(bid)
        as_of[bid] = str(snap.get("as_of", today()))
        source_info[bid] = {
            key: snap[key]
            for key in ("source", "provenance_type", "evaluation_provider", "qualification", "harness")
            if snap.get(key) is not None
        }

    return raw, sigma, as_of, skipped, name_map, source_info


def load_all(cfg, manual_csv: pathlib.Path | None = None) -> tuple[dict, dict, dict, set, dict, dict]:
    """Standard load path: committed snapshots + manual CSV, newest wins."""
    manual = load_manual_csv(manual_csv or (DATA_DIR / "manual" / "scores.csv"))
    snaps = merge_snapshots(load_snapshots(), manual)
    return (*to_matrix(snaps, cfg),)

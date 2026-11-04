"""Composite inputs: dated observations, conservative identities, row-level provenance.

A manual row augments a benchmark; it must not replace the whole source roster,
or make old rows fresh by sharing the newest row's date.
"""
from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import math
import pathlib

from .config import DATA_DIR
from .names import canonical

MANUAL_CSV_FIELDS = ("benchmark", "model", "score", "as_of", "source", "notes")
PROVENANCE = ("source", "provenance_type", "evaluation_provider", "qualification", "harness")


def today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def _valid_date(value):
    try:
        day = dt.date.fromisoformat(value)
        if day > dt.date.fromisoformat(today()):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError(f"invalid or future evaluation date: {value!r}") from None
    return value


def observation(entry, snap):
    result = dict(entry) if isinstance(entry, dict) else {"score": entry}
    for key in ("as_of", *PROVENANCE):
        if key not in result and key in snap:
            result[key] = snap[key]
    return result


def load_snapshots(raw_dir: pathlib.Path = DATA_DIR / "raw") -> dict:
    """Newest published snapshot per benchmark, never newest folder/scrape time."""
    snaps = {}
    for path in sorted(raw_dir.glob("*/*.json")):
        try:
            snap = json.loads(path.read_text())
            bid = snap["benchmark"]
            _valid_date(snap.get("as_of"))
            if not isinstance(snap.get("values"), dict):
                raise ValueError("snapshot values must be a mapping")
        except (ValueError, KeyError, TypeError):
            continue
        previous = snaps.get(bid)
        if previous is None or snap["as_of"] >= previous["as_of"]:
            snaps[bid] = snap
    return snaps


def load_manual_csv(csv_path: pathlib.Path | None = None) -> dict:
    csv_path = csv_path or (DATA_DIR / "manual" / "scores.csv")
    snaps = {}
    if not csv_path.exists():
        return snaps
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"benchmark", "model", "score", "as_of"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{csv_path}: missing required CSV columns: {sorted(missing)}")
        for line, row in enumerate(reader, 2):
            row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k}
            if not row.get("benchmark") or not row.get("model"):
                raise ValueError(f"{csv_path}:{line}: benchmark and model must be non-empty")
            try:
                score = float(row["score"])
                if not math.isfinite(score):
                    raise ValueError("score must be finite")
                date = _valid_date(row["as_of"])
                entry = {"score": score, "as_of": date, "source": row.get("source", ""),
                         "notes": row.get("notes", "")}
                lo, hi = row.get("ci95_lo"), row.get("ci95_hi")
                if lo or hi:
                    lo, hi = float(lo), float(hi)
                    if not (math.isfinite(lo) and math.isfinite(hi) and lo <= score <= hi):
                        raise ValueError("invalid confidence interval")
                    entry["ci95"] = [lo, hi]
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{csv_path}:{line}: {exc}") from None
            bid, model = row["benchmark"], row["model"]
            snap = snaps.setdefault(bid, {"benchmark": bid, "as_of": date, "values": {}})
            previous = snap["values"].get(model)
            if previous and previous["as_of"] == date and previous != entry:
                raise ValueError(f"{csv_path}:{line}: conflicting duplicate model/date")
            if previous is None or date >= previous["as_of"]:
                snap["values"][model] = entry
            snap["as_of"] = max(date, snap["as_of"])
    return snaps


def merge_snapshots(*snapshot_dicts: dict) -> dict:
    """Union rows by canonical identity; newest observation wins, later input breaks ties.

    Called after choosing the latest full automatic snapshot. Historical rows
    removed from that automatic board are not resurrected from older files.
    """
    merged = {}
    for snapshots in snapshot_dicts:
        for bid, snap in snapshots.items():
            if bid not in merged:
                merged[bid] = copy.deepcopy(snap)
                merged[bid]["values"] = {m: observation(e, snap) for m, e in snap["values"].items()}
                continue
            target = merged[bid]
            names = {canonical(m): m for m in target["values"]}
            for name, value in snap["values"].items():
                entry = observation(value, snap)
                previous_name = names.get(canonical(name))
                previous = target["values"].get(previous_name)
                if previous is None or str(entry.get("as_of", "")) >= str(previous.get("as_of", "")):
                    if previous_name is not None:
                        del target["values"][previous_name]
                    target["values"][name] = entry
                    names[canonical(name)] = name
            target["as_of"] = max(str(target.get("as_of", "")), str(snap.get("as_of", "")))
    return merged


def to_matrix(snapshots: dict, cfg) -> tuple[dict, dict, dict, set, dict, dict]:
    registered = set(cfg.bench_ids())
    raw, sigma, as_of, name_map, source_info = {}, {}, {}, {}, {}
    skipped = set(snapshots) - registered
    for bid in cfg.bench_ids():
        source = cfg.alias_source(bid) or bid
        if source not in snapshots:
            continue
        snap = snapshots[source]
        raw[bid], sigma[bid] = {}, {}
        source_info[bid] = {k: snap[k] for k in PROVENANCE if k in snap}
        source_info[bid]["observations"] = {}
        for model, value in snap.get("values", {}).items():
            entry = observation(value, snap)
            cname = canonical(model)
            name_map[str(model)] = cname
            if cname in raw[bid]:
                raise ValueError(f"{bid}: canonical identity collision: {model}")
            score = float(entry["score"])
            if not math.isfinite(score):
                raise ValueError(f"{bid}/{model}: score must be finite")
            ci = entry.get("ci95")
            if ci is not None:
                if (len(ci) != 2 or not all(math.isfinite(v) for v in ci)
                        or not ci[0] <= score <= ci[1]):
                    raise ValueError(f"{bid}/{model}: invalid confidence interval")
            raw[bid][cname] = score
            sigma[bid][cname] = ((ci[1] - ci[0]) / 3.92 if ci and ci[1] > ci[0]
                                 else cfg.bench_noise_raw(bid))
            source_info[bid]["observations"][cname] = {k: v for k, v in entry.items() if k != "score"}
        # This is a summary only. Freshness and published benchmark rows use each
        # observation's own date, not this maximum.
        as_of[bid] = str(snap.get("as_of", ""))
    return raw, sigma, as_of, skipped, name_map, source_info


def load_all(cfg, manual_csv: pathlib.Path | None = None):
    return to_matrix(merge_snapshots(load_snapshots(), load_manual_csv(manual_csv)), cfg)

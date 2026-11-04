"""Source-native rankings, independent of the experimental composite.

No cross-source score averaging, family-name merging, popularity gating, inferred
confidence intervals, or evaluation dates manufactured from retrieval time.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .config import CONFIG_DIR, DATA_DIR, OUTPUT_DIR
from .names import canonical

BOARD_DIR = DATA_DIR / "leaderboards"


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     ensure_ascii=False).encode()).hexdigest()


def load_board_config() -> dict:
    cfg = yaml.safe_load((CONFIG_DIR / "leaderboards.yaml").read_text())
    if cfg["default_board"] not in cfg["boards"]:
        raise ValueError("default_board must be registered")
    for bid, spec in cfg["boards"].items():
        if urlparse(spec["url"]).scheme != "https":
            raise ValueError(f"{bid}: HTTPS source URL required")
        if spec["min_rows"] < 2 or len(spec["score_range"]) != 2:
            raise ValueError(f"{bid}: invalid integrity thresholds")
    return cfg


def _date(value: str | None) -> dt.date | None:
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid ISO date: {value!r}") from None


def _number(value) -> bool:
    import math
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def validate_snapshot(snap: dict, bid: str, spec: dict, *, today=None) -> None:
    """Fail closed on schema/version changes and duplicate model+system identities."""
    today = today or utc_today()
    if snap.get("board") != bid or snap.get("version") != spec["version"]:
        raise ValueError(f"{bid}: board/version mismatch; migrate deliberately")
    if snap.get("source") not in {spec["url"], spec.get("data_url")}:
        raise ValueError(f"{bid}: unexpected source URL")
    dates = [_date(snap.get(k)) for k in ("published_at", "observed_at")]
    if not any(dates) or any(day and day > today for day in dates):
        raise ValueError(f"{bid}: missing or future provenance dates")
    rows = snap.get("rows")
    if not isinstance(rows, list) or len(rows) < spec["min_rows"]:
        raise ValueError(f"{bid}: too few rows; refusing a truncated leaderboard")
    low, high = spec["score_range"]
    identities = set()
    scored = 0
    numeric_fields = {c["key"] for c in spec.get("columns", [])
                      if c["type"] in {"money", "number", "integer"}}
    numeric_fields.update(spec.get("suites", []))
    for row in rows:
        if not isinstance(row.get("model"), str) or not row["model"].strip():
            raise ValueError(f"{bid}: empty model")
        identity = (canonical(row["model"]), row.get("harness", "").casefold())
        if identity in identities:
            raise ValueError(f"{bid}: duplicate identity: {row['model']}")
        identities.add(identity)
        value = row.get("score")
        if value is not None:
            if not _number(value) or not low <= value <= high:
                raise ValueError(f"{bid}: invalid score for {row['model']}")
            scored += 1
        for key in numeric_fields:
            v = row.get(key)
            if v is not None and (not _number(v) or v < 0):
                raise ValueError(f"{bid}: invalid {key} for {row['model']}")
            if key in spec.get("suites", []) and v is not None and v > 100:
                raise ValueError(f"{bid}: suite score out of range")
        if bid == "terminal_bench" and not row.get("harness"):
            raise ValueError("terminal_bench: agent harness is required")
        ci = row.get("ci95")
        if ci is not None and (not isinstance(ci, list) or len(ci) != 2
                               or not all(_number(v) for v in ci)
                               or value is None or not ci[0] <= value <= ci[1]):
            raise ValueError(f"{bid}: invalid confidence interval")
    if scored < spec["min_rows"]:
        raise ValueError(f"{bid}: too few scored rows")


def ranked_rows(rows: list[dict]) -> list[dict]:
    """Competition ranks: 1, 2, 2, 4. Missing is not zero; source names stay intact."""
    ordered = sorted(rows, key=lambda r: (r.get("score") is None,
                                          -(r.get("score") or 0), r["model"],
                                          r.get("harness", "")))
    out, last, rank = [], None, None
    for i, row in enumerate(ordered, 1):
        value = row.get("score")
        if value is not None and value != last:
            rank = i
        identity = f"{canonical(row['model'])}|{row.get('harness', '')}"
        out.append({**row, "id": identity, "rank": rank if value is not None else None})
        last = value
    return out


def load_board_snapshots(cfg=None, directory: Path = BOARD_DIR, *, today=None) -> tuple[dict, list]:
    cfg = cfg or load_board_config()
    snaps, issues = {}, []
    for path in sorted(directory.glob("*/*.json")):
        bid = path.stem
        if bid not in cfg["boards"]:
            continue
        try:
            snap = json.loads(path.read_text())
            validate_snapshot(snap, bid, cfg["boards"][bid], today=today)
        except (ValueError, KeyError, TypeError) as exc:
            issues.append(f"{path.name}: {exc}")
            continue
        # Retrieval is an observation of a board, not a new evaluation. A source
        # date regression cannot supersede a newer published board.
        previous = snaps.get(bid)
        def key(s):
            return (s.get("published_at") or "", s.get("observed_at") or "")
        if previous is None or key(snap) >= key(previous):
            snaps[bid] = snap
    return snaps, issues


def write_board_snapshot(snap: dict, directory: Path = BOARD_DIR) -> Path:
    day = snap.get("observed_at") or snap["published_at"]
    path = directory / day / f"{snap['board']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(snap, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)
    return path


def build_board_report(cfg=None, directory: Path = BOARD_DIR, *, today=None) -> dict:
    cfg = cfg or load_board_config()
    today = today or utc_today()
    snapshots, issues = load_board_snapshots(cfg, directory, today=today)
    status_path = directory / "fetch_status.json"
    try:
        attempts = json.loads(status_path.read_text()) if status_path.exists() else {}
        if not isinstance(attempts, dict):
            raise ValueError("refresh status must be an object")
    except ValueError as exc:
        issues.append(f"fetch_status.json: {exc}")
        attempts = {}
    boards = {}
    for bid, spec in cfg["boards"].items():
        snap = snapshots.get(bid)
        board = {**spec, "id": bid, "rows": [], "status": "missing", "warnings": [],
                 "last_fetch": attempts.get(bid)}
        if snap:
            dates = {k: snap.get(k) for k in ("published_at", "observed_at")}
            # A recently fetched frozen board remains old if its published date is old.
            reference = dates["published_at"] or dates["observed_at"]
            age = (today - _date(reference)).days
            status = ("expired" if age > cfg["freshness"]["expire_after_days"] else
                      "stale" if age > cfg["freshness"]["warn_after_days"] else "available")
            board.update({**dates, "status": status, "age_days": age,
                          "freshness_basis": "published_at" if dates["published_at"] else "observed_at",
                          "source": snap["source"], "data_hash": digest(snap),
                          "retrieval_method": snap.get("retrieval_method", "unspecified"),
                          "scope": snap.get("scope", "Source table"),
                          "rows": ranked_rows(snap["rows"])})
            if not dates["published_at"]:
                board["warnings"].append("Evaluation/publication date not supplied by the table; observed date is retrieval only.")
            if not dates["observed_at"]:
                board["warnings"].append("Retrieval time was not recorded in this retained snapshot.")
            if status != "available":
                board["warnings"].append(f"{status.capitalize()} snapshot ({age} days); not a current ranking.")
            if snap.get("notes"):
                board["warnings"].append(snap["notes"])
        else:
            board["warnings"].append("No valid snapshot. A failed fetch never substitutes demo scores.")
        if attempts.get(bid, {}).get("status") == "failed":
            board["warnings"].append("Last refresh failed; retaining the last valid snapshot.")
        board["n_scored"] = sum(r["score"] is not None for r in board["rows"])
        boards[bid] = board
    catalogue = {}
    for bid, board in boards.items():
        for row in board["rows"]:
            # Exact variants only. This is a discovery index, never cross-board scoring.
            key = canonical(row["model"])
            entry = catalogue.setdefault(key, {"model": row["model"], "boards": []})
            if bid not in entry["boards"]:
                entry["boards"].append(bid)
    return {
        "schema_version": 1, "methodology_version": cfg["version"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "default_board": cfg["default_board"],
        "config_hash": digest({"boards": cfg, "aliases": yaml.safe_load((CONFIG_DIR / "models.yaml").read_text())})[:16],
        "freshness": cfg["freshness"], "boards": boards,
        "catalogue": catalogue, "validation_issues": issues,
        "policy": "Source-native scores only. No cross-board averaging or inferred model equivalence.",
    }


def write_board_outputs(report: dict, out_dir: Path = OUTPUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "leaderboards.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    fields = ["board", "version", "rank", "model", "score", "harness", "published_at", "observed_at", "source"]
    with (out_dir / "leaderboards.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for bid, board in report["boards"].items():
            for row in board["rows"]:
                writer.writerow({"board": bid, **{k: board.get(k) for k in ("version", "published_at", "observed_at", "source")},
                                 **{k: row.get(k) for k in ("rank", "model", "score", "harness")}})
    return path


def board_markdown(report: dict, top_n: int = 10) -> str:
    lines = ["Source-native rankings. **Scores from different boards are not interchangeable.**", ""]
    for board in report["boards"].values():
        lines += [f"### {board['label']} — {board['version']}", "",
                  f"[Source]({board['url']}) · {board['n_scored']} scored entries · "
                  f"published: {board.get('published_at') or 'not supplied'} · "
                  f"observed: {board.get('observed_at') or 'not recorded'} · **{board['status']}**", "",
                  "| Rank | Model / configuration | Score |", "|---|---|---|"]
        for row in board["rows"][:top_n]:
            name = row["model"].replace("|", "\\|")
            if row.get("harness"):
                name += " / " + row["harness"]
            value = "—" if row["score"] is None else f"{row['score']:.{board['decimals']}f}"
            lines.append(f"| {row['rank'] or '—'} | {name} | {value} |")
        lines += ["", board["qualification"], ""]
        for warning in board["warnings"]:
            lines += [f"> {warning}", ""]
    return "\n".join(lines)

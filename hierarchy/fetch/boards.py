"""Version-pinned adapters for source-native public leaderboard tables.

HTML changes, partial pagination, and undocumented metric changes are errors,
not reasons to fabricate scores or change the meaning of an existing metric.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from ..boards import (BOARD_DIR, load_board_config, load_board_snapshots,
                      validate_snapshot, write_board_snapshot)
from . import base

FetchError = base.FetchError


def _normal(text):
    return re.sub(r"[\W_]+", "", text.casefold())


def _table(html: str, required: list[str]):
    parser = base._TableParser()
    parser.feed(html)
    for table in parser.tables:
        for i, header in enumerate(table[:4]):
            headings = [_normal(c) for c in header]
            if all(_normal(key) in headings for key in required):
                return headings, table[i + 1:], " ".join(parser.page_text)
    raise FetchError("Required leaderboard headers missing; page/schema may have changed")


def _number(text, *, optional=True):
    token = text.strip().replace(",", "").removeprefix("$").removesuffix("%").strip()
    if optional and token in {"", "--", "—", "–", "N/A", "null"}:
        return None
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", token):
        raise FetchError(f"Invalid numeric cell: {text!r}")
    return float(token)


def _cell(row, headers, name, *, optional=False):
    key = _normal(name)
    if key not in headers:
        if optional:
            return ""
        raise FetchError(f"Required column missing: {name}")
    index = headers.index(key)
    if index >= len(row):
        raise FetchError("Incomplete leaderboard row")
    return row[index]


def parse_artificial_analysis(html: str) -> list[dict]:
    headers, data, _ = _table(html, ["Model", "Artificial Analysis Intelligence Index"])
    rows = []
    for row in data:
        if not row or not any(row):
            continue
        model = _cell(row, headers, "Model")
        rows.append({"model": model,
                     "score": _number(_cell(row, headers, "Artificial Analysis Intelligence Index")),
                     "provider": _cell(row, headers, "Creator", optional=True) or None,
                     "context": _cell(row, headers, "Context Window", optional=True) or None,
                     "cost_per_task": _number(_cell(row, headers, "Cost per TaskUSD", optional=True)),
                     "output_tps": _number(_cell(row, headers, "MedianTokens/s", optional=True))})
    return rows


def parse_livebench(html: str) -> list[dict]:
    headers, data, text = _table(html, ["Model", "Overall", "Agentic", "Coding", "Reasoning"])
    if not re.search(r"LiveBench\s+2\.0\b", text, re.I):
        raise FetchError("LiveBench 2.0 version marker missing; do not import legacy/new suites")
    suites = {"Agentic": "agentic", "Design": "design", "Coding": "coding",
              "Browser Use": "browser_use", "Data Analysis": "data_analysis",
              "Research": "research", "Reasoning": "reasoning"}
    rows = []
    for row in data:
        if not row or not any(row):
            continue
        name = _cell(row, headers, "Model")
        # 'open' is an explicit badge, not a model variant. Preserve all other suffixes.
        open_weights = bool(re.search(r"\bopen$|(?<=[\d)])open$", name))
        name = re.sub(r"\s*open$", "", name).removeprefix("▸").strip() if open_weights else name.strip()
        entry = {"model": name, "score": _number(_cell(row, headers, "Overall")),
                 **{key: _number(_cell(row, headers, label)) for label, key in suites.items()},
                 "open_weights": open_weights,
                 "cost_per_success": _number(_cell(row, headers, "Cost per successful task", optional=True))}
        rows.append(entry)
    return rows


def parse_terminal_bench(html: str) -> list[dict]:
    headers, data, text = _table(html, ["Model", "Agent", "Resolution Rate", "Release Date"])
    if not re.search(r"\b4\.0\b", text):
        raise FetchError("Terminal-Bench 4.0 version marker missing")
    rows = []
    for row in data:
        if not row or not any(row):
            continue
        score = _cell(row, headers, "Resolution Rate")
        match = re.fullmatch(r"\s*([\d.]+)\s*%\s*±\s*([\d.]+)\s*%\s*", score)
        if not match:
            raise FetchError(f"Unexpected resolution rate/margin: {score!r}")
        released = dt.datetime.strptime(_cell(row, headers, "Release Date"), "%b %d, %Y").date()
        rows.append({"model": _cell(row, headers, "Model"),
                     "harness": _cell(row, headers, "Agent"),
                     "score": float(match[1]), "margin": float(match[2]),
                     "release_date": released.isoformat()})
    return rows


def fetch_native_board(bid: str, spec: dict, cfg) -> dict:
    observed = dt.datetime.now(dt.timezone.utc).date().isoformat()
    snap = {"board": bid, "version": spec["version"], "source": spec["url"],
            "observed_at": observed, "published_at": None,
            "retrieval_method": "automatic_public_source", "scope": "Complete parsed source table"}
    if spec["kind"] == "arena_hf":
        # Canonical dataset only. No mirror of raw Elo in a style-control slot,
        # no first-100-rows fallback masquerading as the complete leaderboard.
        rows = base._hf_rows(cfg, base.HF_STYLE_CONFIG, "latest", where=base._OVERALL_WHERE)
        values, published = base._arena_values_from_rows(rows)
        if not published:
            raise FetchError("Arena publication date missing")
        snap.update(source=spec["data_url"], published_at=published,
                    rows=[{"model": name, **entry} for name, entry in values.items()])
    else:
        html = base._get(spec["url"], cfg.sources).text
        if spec["kind"] == "artificial_analysis":
            methodology = base._get(spec["methodology_url"], cfg.sources).text
            plain = re.sub(r"<[^>]+>", " ", methodology)
            # Check the current heading, not a version string somewhere in history.
            versions = re.findall(r"Intelligence\s+Index\s+v(\d+(?:\.\d+)+)", plain, re.I)
            if not versions or versions[0] != "5.0":
                raise FetchError("Artificial Analysis current index is not v5.0; review the metric version")
            snap["rows"] = parse_artificial_analysis(html)
        elif spec["kind"] == "livebench_v2":
            snap["rows"] = parse_livebench(html)
        elif spec["kind"] == "terminal_bench_v4":
            snap["rows"] = parse_terminal_bench(html)
        else:
            raise FetchError(f"No native board adapter: {spec['kind']}")
    return snap


def fetch_boards(cfg, directory: Path = BOARD_DIR, *, quiet=False) -> tuple[list, list]:
    board_cfg = load_board_config()
    previous, _ = load_board_snapshots(board_cfg, directory)
    written, failures, statuses = [], [], {}
    for bid, spec in board_cfg["boards"].items():
        try:
            snap = fetch_native_board(bid, spec, cfg)
            validate_snapshot(snap, bid, spec)
            if bid in previous:
                old = previous[bid]
                old_count = sum(r.get("score") is not None for r in old["rows"])
                new_count = sum(r.get("score") is not None for r in snap["rows"])
                if new_count < old_count * 0.8:
                    raise FetchError(f"scored roster shrank from {old_count} to {new_count}; review before publishing")
                if old.get("published_at") and (snap.get("published_at") or "") < old["published_at"]:
                    raise FetchError("source publication date regressed")
            path = write_board_snapshot(snap, directory)
            written.append((bid, path, len(snap["rows"])))
            statuses[bid] = {"status": "ok", "rows": len(snap["rows"])}
            if not quiet:
                print(f"  ✔ {bid}: {len(snap['rows'])} source-native entries")
        except (FetchError, ValueError, KeyError, TypeError) as exc:
            failures.append((bid, str(exc)))
            statuses[bid] = {"status": "failed", "error": str(exc)}
            if not quiet:
                print(f"  ✘ {bid}: {exc} (retaining last valid snapshot)")
        statuses[bid]["attempted_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "fetch_status.json").write_text(json.dumps(statuses, indent=2) + "\n")
    return written, failures

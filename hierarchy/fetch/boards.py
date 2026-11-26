"""Version-pinned adapters for source-native public leaderboard tables and feeds.

HTML/SPA changes, partial pagination, and undocumented metric changes are errors,
not reasons to fabricate scores or change the meaning of an existing metric.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import re
from pathlib import Path
from urllib.parse import urljoin

from ..boards import (BOARD_DIR, load_board_config, load_board_snapshots,
                      utc_today, validate_snapshot, write_board_snapshot)
from . import base

FetchError = base.FetchError

_LIVEBENCH_SUITES = {
    "Long Agentic": "agentic",
    "Agentic": "agentic",
    "Design": "design",
    "Coding": "coding",
    "Browser": "browser_use",
    "Browser Use": "browser_use",
    "Data Analysis": "data_analysis",
    "Research": "research",
    "Reasoning": "reasoning",
}
_REQUIRED_LIVEBENCH_SUITES = {
    "agentic", "design", "coding", "browser_use",
    "data_analysis", "research", "reasoning",
}


def _normal(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def _round_half_up(value: float) -> float:
    return float(int(math.floor(value + 0.5)))


def _rsc_stream(html: str) -> str:
    chunks = []
    for match in re.finditer(r'self\.__next_f\.push\(\[1,("(?:\\.|[^"\\])*")\]\)', html, re.S):
        try:
            chunks.append(json.loads(match.group(1)))
        except ValueError:
            continue
    return "".join(chunks)


def _table(html: str, required: list[str]):
    parser = base._TableParser()
    parser.feed(html)
    for table in parser.tables:
        for i, header in enumerate(table[:4]):
            headings = [_normal(c) for c in header]
            if all(_normal(key) in headings for key in required):
                body = [r for r in table[i + 1:] if r and any(c.strip() for c in r)]
                if body:
                    return headings, body, " ".join(parser.page_text)
    raise FetchError("Required leaderboard headers missing; page/schema may have changed")


def _number(text: str, *, optional: bool = True) -> float | None:
    token = text.strip().replace(",", "").removeprefix("$").removesuffix("%").strip()
    if optional and token in {"", "--", "—", "–", "N/A", "null"}:
        return None
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", token):
        raise FetchError(f"Invalid numeric cell: {text!r}")
    return float(token)


def _cell(row: list[str], headers: list[str], name: str, *, optional: bool = False) -> str:
    key = _normal(name)
    if key not in headers:
        if optional:
            return ""
        raise FetchError(f"Required column missing: {name}")
    index = headers.index(key)
    if index >= len(row):
        raise FetchError("Incomplete leaderboard row")
    return row[index]


def _format_aa_context(tokens) -> str | None:
    if not isinstance(tokens, (int, float)) or isinstance(tokens, bool) or tokens <= 0:
        return None
    if tokens >= 1_000_000:
        return f"{int(math.floor(tokens / 1_000_000 + 0.5))}M"
    return f"{int(math.floor(tokens / 1_000 + 0.5))}k"


def parse_artificial_analysis(html: str) -> list[dict]:
    rsc = _rsc_stream(html)
    marker = re.search(r'"initialModels"\s*:\s*\[', rsc)
    if marker:
        try:
            models, _ = json.JSONDecoder().raw_decode(rsc, marker.end() - 1)
        except ValueError as exc:
            raise FetchError("Artificial Analysis RSC model payload malformed") from exc
        rows = []
        for item in models:
            if not isinstance(item, dict) or item.get("deprecated"):
                continue
            raw_index = item.get("intelligenceIndex")
            if raw_index is None:
                continue
            if isinstance(raw_index, bool) or not math.isfinite(float(raw_index)):
                raise FetchError(f"Invalid Artificial Analysis score: {raw_index!r}")
            name = str(item.get("name") or "").strip()
            if not name:
                raise FetchError("Artificial Analysis entry missing model name")
            cost_raw = item.get("intelligenceIndexCostPerTask")
            tps_raw = item.get("outputSpeed")
            cost = (round(float(cost_raw), 2)
                    if cost_raw is not None and math.isfinite(float(cost_raw)) else None)
            tps = (_round_half_up(float(tps_raw))
                   if tps_raw is not None and math.isfinite(float(tps_raw)) else None)
            row = {
                "model": name,
                "score": _round_half_up(float(raw_index)),
                "provider": (str(item.get("modelCreatorName") or "").strip() or None),
                "context": _format_aa_context(item.get("contextWindowTokens")),
                "cost_per_task": cost,
                "output_tps": tps,
            }
            if item.get("isOpenWeights") is not None:
                row["open_weights"] = bool(item["isOpenWeights"])
            rows.append(row)
        if not rows:
            raise FetchError("Artificial Analysis RSC payload contained zero scored models")
        return rows

    headers, data, _ = _table(html, ["Model", "Artificial Analysis Intelligence Index"])
    rows = []
    for row in data:
        model = _cell(row, headers, "Model")
        rows.append({
            "model": model,
            "score": _number(_cell(row, headers, "Artificial Analysis Intelligence Index")),
            "provider": _cell(row, headers, "Creator", optional=True) or None,
            "context": _cell(row, headers, "Context Window", optional=True) or None,
            "cost_per_task": _number(_cell(row, headers, "Cost per TaskUSD", optional=True)),
            "output_tps": _number(_cell(row, headers, "MedianTokens/s", optional=True)),
        })
    return rows


def _skip_js_block(text: str, start: int) -> int:
    """Return index past the balanced `{...}` object starting at `start`."""
    depth = 0
    quote = None
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in {'"', "'", "`"}:
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx + 1
    raise FetchError("Unbalanced object literal in LiveBench bundle")


def _extract_livebench_model_meta(js_text: str) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    key_pattern = re.compile(r'(?:(?<=[\{,])\s*)(?:"([^"]+)"|([A-Za-z_$][A-Za-z0-9_$]*)):\{')
    pos = 0
    while True:
        match = key_pattern.search(js_text, pos)
        if not match:
            break
        brace_start = match.end() - 1
        try:
            brace_end = _skip_js_block(js_text, brace_start)
        except FetchError:
            pos = match.end()
            continue
        body = js_text[brace_start:brace_end]
        if 'displayName:"' not in body:
            pos = match.end()
            continue
        key = match.group(1) or match.group(2)
        display_match = re.search(r'displayName:"([^"]+)"', body)
        org_match = re.search(r'organization:"([^"]+)"', body)
        open_match = re.search(r'openweight:(!0|true)', body)
        finetune_match = re.search(r'finetune:\{', body)
        base_entry = {
            "display_name": display_match.group(1) if display_match else key,
            "provider": org_match.group(1) if org_match else None,
            "open_weights": bool(open_match),
            "finetune": bool(finetune_match),
        }
        meta[key] = base_entry
        variants_match = re.search(r'variants:\[(.*?)\]', body, re.S)
        if variants_match:
            for variant_body in re.findall(r'\{[^{}]+\}', variants_match.group(1)):
                raw_match = re.search(r'rawName:"([^"]+)"', variant_body)
                if not raw_match:
                    continue
                v_disp = re.search(r'displayName:"([^"]+)"', variant_body)
                v_open = re.search(r'openweight:(!0|true|!1|false)', variant_body)
                meta[raw_match.group(1)] = {
                    "display_name": v_disp.group(1) if v_disp else base_entry["display_name"],
                    "provider": base_entry["provider"],
                    "open_weights": (v_open.group(1) in {"!0", "true"}
                                     if v_open else base_entry["open_weights"]),
                    "finetune": base_entry["finetune"],
                }
        pos = brace_end
    return meta


def _parse_human_date(token: str) -> dt.date | None:
    cleaned = token.strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def extract_livebench_release(js_text: str, *, today: dt.date | None = None) -> tuple[str, str]:
    """Return `(release_id, published_at_iso)` from the LiveBench 2.0 bundle."""
    today = today or utc_today()
    arrays = re.findall(r'\[(?:"20\d{6}"(?:,"20\d{6}")*)\]', js_text)
    releases: list[str] = []
    for raw in arrays:
        releases.extend(json.loads(raw))
    if not releases:
        raise FetchError("LiveBench 2.0 release directory list not found in app bundle")
    release_id = max(releases)
    try:
        release_date = dt.date.fromisoformat(
            f"{release_id[:4]}-{release_id[4:6]}-{release_id[6:8]}"
        )
    except ValueError as exc:
        raise FetchError(f"Invalid LiveBench release identifier: {release_id!r}") from exc

    published = release_date
    banner_ident = re.search(
        r'"Last updated ".*?children:([A-Za-z_$][A-Za-z0-9_$]*)\}\)\s*,\s*"\s*(?:\\u2014|—)\s*the latest release',
        js_text,
    )
    if banner_ident:
        ident = re.escape(banner_ident.group(1))
        for val_match in re.finditer(rf'\b{ident}="([^"]+)"', js_text):
            parsed = _parse_human_date(val_match.group(1))
            if parsed and release_date <= parsed <= today:
                published = max(published, parsed)
    return release_id, published.isoformat()


def parse_livebench_release(
    js_text: str,
    categories_payload: dict,
    table_csv: str,
    cost_csv: str | None = None,
    *,
    today: dt.date | None = None,
) -> tuple[list[dict], str]:
    _, published_at = extract_livebench_release(js_text, today=today)
    if not isinstance(categories_payload, dict):
        raise FetchError("LiveBench categories payload must be an object")
    weights_raw = categories_payload.get("_overall_weights") or {}
    suite_columns: dict[str, tuple[str, list[str]]] = {}
    for cat_name, cols in categories_payload.items():
        if cat_name == "_overall_weights":
            continue
        mapped = _LIVEBENCH_SUITES.get(cat_name)
        if not mapped or not isinstance(cols, list) or not cols:
            raise FetchError(f"Unexpected LiveBench suite definition: {cat_name!r}")
        suite_columns[cat_name] = (mapped, [str(c) for c in cols])
    if {mapped for mapped, _ in suite_columns.values()} != _REQUIRED_LIVEBENCH_SUITES:
        raise FetchError("LiveBench 2.0 suite schema changed; review metric version")

    meta = _extract_livebench_model_meta(js_text)
    cost_by_model: dict[str, dict] = {}
    if cost_csv:
        for crow in csv.DictReader(io.StringIO(cost_csv)):
            if crow.get("model"):
                cost_by_model[crow["model"].strip()] = crow

    reader = csv.DictReader(io.StringIO(table_csv))
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)):
        raise FetchError("LiveBench score table has duplicate column names")
    required = {"model"}
    for _, columns in suite_columns.values():
        required.update(columns)
    missing = required.difference(headers)
    if missing:
        raise FetchError(f"LiveBench score table missing columns: {', '.join(sorted(missing))}")

    rows = []
    for raw_row in reader:
        if None in raw_row or None in raw_row.values():
            raise FetchError(f"Unexpected LiveBench row width at line {reader.line_num}")
        model_key = (raw_row.get("model") or "").strip()
        if not model_key:
            continue
        info = meta.get(model_key, {
            "display_name": model_key,
            "provider": None,
            "open_weights": False,
            "finetune": False,
        })
        if info.get("finetune"):
            continue

        cat_scores: dict[str, float | None] = {}
        suite_scores: dict[str, float | None] = {}
        for cat_name, (suite_key, cols) in suite_columns.items():
            vals = []
            for col in cols:
                cell = (raw_row.get(col) or "").strip()
                if not cell or cell.lower() in {"-", "--", "n/a", "null", "none"}:
                    continue
                try:
                    num = float(cell)
                except ValueError as exc:
                    raise FetchError(f"Invalid LiveBench cell {col}={cell!r}") from exc
                if not math.isfinite(num):
                    raise FetchError(f"Non-finite LiveBench cell {col}={cell!r}")
                vals.append(num)
            avg = sum(vals) / len(vals) if vals else None
            cat_scores[cat_name] = avg
            suite_scores[suite_key] = round(avg, 1) if avg is not None else None

        weighted_sum = 0.0
        weight_total = 0.0
        for cat_name, avg in cat_scores.items():
            weight = float(weights_raw.get(cat_name, 1.0))
            if avg is not None and weight > 0:
                weighted_sum += avg * weight
                weight_total += weight
        overall_2 = round(weighted_sum / weight_total, 2) if weight_total > 0 else None

        cost_per_success = None
        crow = cost_by_model.get(model_key)
        if crow and overall_2 and overall_2 > 0:
            total_cost = 0.0
            total_tasks = 0.0
            for _, cols in suite_columns.values():
                for col in cols:
                    c_str = (crow.get(col) or "").strip()
                    q_str = (crow.get(f"nq_{col}") or "").strip()
                    if not c_str or not q_str:
                        continue
                    try:
                        c_val, q_val = float(c_str), float(q_str)
                    except ValueError:
                        continue
                    if math.isfinite(c_val) and math.isfinite(q_val) and q_val > 0:
                        total_cost += c_val
                        total_tasks += q_val
            if total_tasks > 0:
                cost_per_success = round((total_cost / total_tasks) / overall_2 * 100.0, 3)

        entry = {
            "model": info["display_name"],
            "score": round(overall_2, 1) if overall_2 is not None else None,
            **suite_scores,
            "open_weights": bool(info["open_weights"]),
            "cost_per_success": cost_per_success,
        }
        if info.get("provider"):
            entry["provider"] = info["provider"]
        rows.append(entry)

    if not rows:
        raise FetchError("LiveBench 2.0 release contained zero model rows")
    return rows, published_at


def parse_livebench(html: str) -> list[dict]:
    headers, data, text = _table(html, ["Model", "Overall", "Agentic", "Coding", "Reasoning"])
    if not re.search(r"LiveBench\s+2\.0\b", text, re.I):
        raise FetchError("LiveBench 2.0 version marker missing; do not import legacy/new suites")
    suites = {"Agentic": "agentic", "Design": "design", "Coding": "coding",
              "Browser Use": "browser_use", "Data Analysis": "data_analysis",
              "Research": "research", "Reasoning": "reasoning"}
    rows = []
    for row in data:
        name = _cell(row, headers, "Model")
        # 'open' is an explicit badge, not a model variant. Preserve all other suffixes.
        open_weights = bool(re.search(r"\bopen$|(?<=[\d)])open$", name))
        name = (re.sub(r"\s*open$", "", name).removeprefix("▸").strip()
                if open_weights else name.strip())
        entry = {
            "model": name,
            "score": _number(_cell(row, headers, "Overall")),
            **{key: _number(_cell(row, headers, label)) for label, key in suites.items()},
            "open_weights": open_weights,
            "cost_per_success": _number(_cell(row, headers, "Cost per successful task", optional=True)),
        }
        rows.append(entry)
    return rows


def _clean_parenthesized_model(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name).strip()
    return re.sub(r"\s*\(\s*([^()]+?)\s*\)", r" (\1)", cleaned)


def parse_terminal_bench_page(
    html: str, *, expected_version: str = "4.1"
) -> tuple[list[dict], str | None]:
    rsc = _rsc_stream(html)
    marker = re.search(r'\{\s*"leaderboard"\s*:\s*\{\s*"id"\s*:', rsc)
    if marker:
        try:
            payload, _ = json.JSONDecoder().raw_decode(rsc, marker.start())
        except ValueError as exc:
            raise FetchError("Terminal-Bench RSC leaderboard payload malformed") from exc
        leaderboard = payload.get("leaderboard") or {}
        expected_title = f"Terminal-Bench {expected_version}"
        if leaderboard.get("title") != expected_title:
            raise FetchError(f"{expected_title} version marker missing")
        published_at = None
        updated_raw = str(leaderboard.get("updated_at") or "")[:10]
        if updated_raw:
            published_at = dt.date.fromisoformat(updated_raw).isoformat()
        rows = []
        for item in payload.get("rows") or []:
            if not isinstance(item, dict) or item.get("status") != "display":
                continue
            metadata = item.get("metadata") or {}
            metrics = item.get("metrics") or {}
            model_label = str((metadata.get("model_display") or {}).get("label") or "").strip()
            harness = str((metadata.get("agent_display") or {}).get("label") or "").strip()
            if not model_label or not harness:
                raise FetchError("Terminal-Bench entry missing model or agent label")
            effort = str(metadata.get("reasoning_effort") or "").strip()
            model = f"{model_label} ({effort})" if effort else model_label
            display_acc = str(metrics.get("display_accuracy") or "")
            acc_match = re.search(r"([\d.]+)\s*%\**\s*±\s*([\d.]+)\s*%", display_acc)
            if acc_match:
                score, margin = float(acc_match.group(1)), float(acc_match.group(2))
            elif metrics.get("accuracy") is not None and metrics.get("accuracy_ci95_half_width") is not None:
                score = round(float(metrics["accuracy"]), 1)
                margin = round(float(metrics["accuracy_ci95_half_width"]), 1)
            else:
                raise FetchError(f"Unexpected Terminal-Bench accuracy/margin: {display_acc!r}")
            released = dt.date.fromisoformat(str(metadata.get("date") or "")).isoformat()
            provider = str((metadata.get("model_org") or {}).get("label") or "").strip() or None
            entry = {
                "model": model,
                "harness": harness,
                "score": score,
                "margin": margin,
                "release_date": released,
            }
            if provider:
                entry["provider"] = provider
            rows.append(entry)
        if not rows:
            raise FetchError("Terminal-Bench RSC payload contained zero display rows")
        return rows, published_at

    headers, data, text = _table(html, ["Model", "Agent", "Resolution Rate", "Release Date"])
    if not re.search(rf"\b{re.escape(expected_version)}\b", text):
        raise FetchError(f"Terminal-Bench {expected_version} version marker missing")
    rows = []
    for row in data:
        score = _cell(row, headers, "Resolution Rate")
        match = re.fullmatch(r"\s*([\d.]+)\s*%\s*±\s*([\d.]+)\s*%\s*", score)
        if not match:
            raise FetchError(f"Unexpected resolution rate/margin: {score!r}")
        released = dt.datetime.strptime(_cell(row, headers, "Release Date"), "%b %d, %Y").date()
        rows.append({
            "model": _clean_parenthesized_model(_cell(row, headers, "Model")),
            "harness": _cell(row, headers, "Agent").strip(),
            "score": float(match[1]),
            "margin": float(match[2]),
            "release_date": released.isoformat(),
        })
    return rows, None


def parse_terminal_bench(html: str, *, expected_version: str = "4.1") -> list[dict]:
    rows, _ = parse_terminal_bench_page(html, expected_version=expected_version)
    return rows


def fetch_native_board(bid: str, spec: dict, cfg) -> dict:
    observed = utc_today().isoformat()
    snap = {
        "board": bid,
        "version": spec["version"],
        "source": spec["url"],
        "observed_at": observed,
        "published_at": None,
        "retrieval_method": "automatic_public_source",
        "scope": "Complete parsed source table",
    }
    if spec["kind"] == "arena_hf":
        # Canonical dataset only. No mirror of raw Elo in a style-control slot,
        # no first-100-rows fallback masquerading as the complete leaderboard.
        rows = base._hf_rows(cfg, base.HF_STYLE_CONFIG, "latest", where=base._OVERALL_WHERE)
        values, published = base._arena_values_from_rows(rows)
        if not published:
            raise FetchError("Arena publication date missing")
        snap.update(
            source=spec["data_url"],
            published_at=published,
            rows=[{"model": name, **entry} for name, entry in values.items()],
        )
    elif spec["kind"] == "artificial_analysis":
        html = base._get(spec["url"], cfg.sources).text
        methodology = base._get(spec["methodology_url"], cfg.sources).text
        plain = re.sub(r"<[^>]+>", " ", methodology)
        expected_ver = spec["version"].removeprefix("Intelligence Index v").strip()
        # The current heading can sit below historical notes, so judge by the
        # newest version mentioned, not the first string occurrence: pass when
        # the expected version is present and nothing newer supersedes it.
        def _vtuple(version: str) -> tuple:
            return tuple(int(part) for part in version.split("."))
        mentioned = sorted({_vtuple(v) for v in
                            re.findall(r"Intelligence\s+Index\s+v(\d+(?:\.\d+)+)", plain, re.I)})
        expected = _vtuple(expected_ver)
        if expected not in mentioned or max(mentioned) != expected:
            raise FetchError(
                f"Artificial Analysis current index is not v{expected_ver}; "
                f"methodology mentions {[('v' + '.'.join(map(str, v))) for v in mentioned]} "
                "— review the metric version"
            )
        snap["rows"] = parse_artificial_analysis(html)
        if re.search(r'"initialModels"\s*:\s*\[', _rsc_stream(html)):
            snap["scope"] = "Complete scored current-model roster (including grouped effort variants)"
    elif spec["kind"] == "livebench_v2":
        html = base._get(spec["url"], cfg.sources).text
        if "<table" in html.lower():
            snap["rows"] = parse_livebench(html)
        else:
            if not re.search(r"LiveBench\s+2\.0\b", html, re.I):
                raise FetchError("LiveBench 2.0 version marker missing; do not import legacy/new suites")
            script_match = re.search(r'<script[^>]+src=["\']([^"\']*static/js/main\.[^"\']+\.js)["\']', html)
            if not script_match:
                raise FetchError("LiveBench 2.0 app bundle script tag missing")
            js_text = base._get(urljoin(spec["url"], script_match.group(1)), cfg.sources).text
            release_id, _ = extract_livebench_release(js_text)
            categories_payload = base._get(
                urljoin(spec["url"], f"data/{release_id}/categories.json"), cfg.sources
            ).json()
            table_csv = base._get(
                urljoin(spec["url"], f"data/{release_id}/table.csv"), cfg.sources
            ).text
            cost_csv = base._get(
                urljoin(spec["url"], f"data/{release_id}/cost.csv"), cfg.sources
            ).text
            rows, published_at = parse_livebench_release(
                js_text, categories_payload, table_csv, cost_csv
            )
            snap.update(
                rows=rows,
                published_at=published_at,
                scope=f"Complete official LiveBench 2.0 release ({release_id})",
            )
    elif spec["kind"] == "terminal_bench_v4":
        html = base._get(spec["url"], cfg.sources).text
        expected_ver = spec["version"].removeprefix("Terminal-Bench ").strip()
        rows, published_at = parse_terminal_bench_page(html, expected_version=expected_ver)
        snap.update(rows=rows, published_at=published_at)
        if re.search(r'\{\s*"leaderboard"\s*:\s*\{\s*"id"\s*:', _rsc_stream(html)):
            snap["scope"] = "Complete official display roster (all evaluated model + agent systems)"
    else:
        raise FetchError(f"No native board adapter: {spec['kind']}")
    return snap


def fetch_boards(cfg, directory: Path = BOARD_DIR, *, quiet: bool = False) -> tuple[list, list]:
    board_cfg = load_board_config()
    previous, _ = load_board_snapshots(board_cfg, directory)
    status_path = directory / "fetch_status.json"
    try:
        old_statuses = json.loads(status_path.read_text()) if status_path.exists() else {}
        if not isinstance(old_statuses, dict):
            old_statuses = {}
    except (ValueError, OSError):
        old_statuses = {}

    written, failures, statuses = [], [], {}
    for bid, spec in board_cfg["boards"].items():
        changed_on_disk = False
        try:
            snap = fetch_native_board(bid, spec, cfg)
            validate_snapshot(snap, bid, spec)
            if bid in previous:
                old = previous[bid]
                old_count = sum(r.get("score") is not None for r in old["rows"])
                new_count = sum(r.get("score") is not None for r in snap["rows"])
                if new_count < old_count * 0.8:
                    raise FetchError(
                        f"scored roster shrank from {old_count} to {new_count}; review before publishing"
                    )
                if old.get("published_at") and (snap.get("published_at") or "") < old["published_at"]:
                    raise FetchError("source publication date regressed")
            day = snap.get("observed_at") or snap["published_at"]
            existing_path = directory / day / f"{snap['board']}.json"
            before_bytes = existing_path.read_bytes() if existing_path.exists() else None
            path = write_board_snapshot(snap, directory)
            changed_on_disk = before_bytes != path.read_bytes()
            written.append((bid, path, len(snap["rows"])))
            statuses[bid] = {"status": "ok", "rows": len(snap["rows"])}
            if not quiet:
                print(f"  ✔ {bid}: {len(snap['rows'])} source-native entries")
        except (FetchError, ValueError, KeyError, TypeError) as exc:
            failures.append((bid, str(exc)))
            statuses[bid] = {"status": "failed", "error": str(exc)}
            if not quiet:
                print(f"  ✘ {bid}: {exc} (retaining last valid snapshot)")

        now_iso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        prev_status = old_statuses.get(bid)
        if (isinstance(prev_status, dict)
                and not changed_on_disk
                and {k: v for k, v in prev_status.items() if k != "attempted_at"} == statuses[bid]
                and str(prev_status.get("attempted_at", ""))[:10] == now_iso[:10]):
            statuses[bid]["attempted_at"] = prev_status["attempted_at"]
        else:
            statuses[bid]["attempted_at"] = now_iso

    directory.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(statuses, indent=2) + "\n")
    return written, failures

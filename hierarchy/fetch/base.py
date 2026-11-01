"""Fetch adapters (METHODOLOGY.md §12).

Design contract: every adapter either returns a snapshot dict
{"benchmark": id, "as_of": ..., "values": {model: {"score": x, "ci95": [lo,hi]?}}}
or raises FetchError with actionable instructions. A failing source NEVER
fails the daily run — the pipeline aggregates whatever succeeded and flags
staleness. data/manual/scores.csv is the guaranteed fallback.

Adapter order for LMArena (canonical first):
1. Official HF dataset lmarena-ai/leaderboard-dataset via the public
   datasets-server JSON API (CC-BY-4.0) — style-controlled config, with
   per-model 95% CIs and the leaderboard publish date.
2. Community mirror API (clean JSON).
3. Manual drop.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

import requests
import requests_cache

from ..config import DATA_DIR

HF_DATASET = "lmarena-ai/leaderboard-dataset"
HF_STYLE_CONFIG = "text_style_control"   # style-controlled text leaderboard (§4 row 1)
DATASETS_SERVER = "https://datasets-server.huggingface.co"


class FetchError(RuntimeError):
    pass


_HTTP = requests_cache.CachedSession(".cache/model-hierarchy-http", expire_after=24 * 60 * 60)


def _get(url: str, cfg_sources: dict, params: dict | None = None) -> requests.Response:
    defaults = cfg_sources.get("defaults", {})
    headers = {"User-Agent": defaults.get("user_agent", "model-hierarchy")}
    last = None
    for _ in range(int(defaults.get("retries", 2))):
        try:
            r = _HTTP.get(url, headers=headers, params=params,
                          timeout=int(defaults.get("timeout_seconds", 20)))
            if r.status_code == 200:
                return r
            last = FetchError(f"{url} -> HTTP {r.status_code}")
        except requests.RequestException as exc:  # network, DNS, TLS...
            last = FetchError(f"{url} -> {exc.__class__.__name__}")
    raise last or FetchError(url)


def _dig(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise FetchError(f"json path '{dotted}' not found")
        cur = cur[part]
    return cur


def write_snapshot(snap: dict, raw_dir: pathlib.Path = None) -> pathlib.Path:
    raw_dir = raw_dir or (DATA_DIR / "raw")
    day = snap.get("as_of") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    out_dir = raw_dir / day
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{snap['benchmark']}.json"
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n")
    return path


def _rel(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(path.parents[3]))
    except (IndexError, ValueError):
        return str(path)


# --------------------------------------------------------------------------
# LMArena (§4 row 1) — canonical: official HF dataset via datasets-server
# --------------------------------------------------------------------------
_OVERALL_WHERE = '"category"=\'overall\''


def _hf_rows(cfg, config: str, split: str, where: str | None = None) -> list:
    """Paginate the datasets-server rows/filter API, yielding row dicts."""
    endpoint = "filter" if where else "rows"
    out: list[dict] = []
    offset, length = 0, 100
    while True:
        params = {"dataset": HF_DATASET, "config": config, "split": split,
                  "offset": offset, "length": length}
        if where:
            params["where"] = where
        r = _get(f"{DATASETS_SERVER}/{endpoint}", cfg.sources, params=params)
        d = r.json()
        rows = d.get("rows", [])
        if not rows:
            break
        out.extend(w.get("row", {}) for w in rows)
        total = int(d.get("num_rows_total", len(out)))
        offset += length
        if offset >= total:
            break
    return out


def _arena_values_from_rows(rows: list) -> tuple[dict, str]:
    values: dict[str, dict] = {}
    as_of = ""
    for row in rows:
        if str(row.get("category", "overall")).lower() != "overall":
            continue
        name, rating = row.get("model_name"), row.get("rating")
        if not name or rating is None:
            continue
        entry = {"score": float(rating)}
        lo, hi = row.get("rating_lower"), row.get("rating_upper")
        if lo is not None and hi is not None:
            entry["ci95"] = [float(lo), float(hi)]
        if row.get("vote_count") is not None:
            entry["votes"] = int(row["vote_count"])
        values[str(name)] = entry
        d = str(row.get("leaderboard_publish_date", ""))[:10]
        if d > as_of:
            as_of = d
    return values, as_of


def fetch_lm_arena(source: dict, cfg) -> dict:
    errors: list[str] = []

    # -- 1. canonical: official HF dataset, style-controlled, category=overall
    try:
        rows = _hf_rows(cfg, HF_STYLE_CONFIG, "latest", where=_OVERALL_WHERE)
        values, as_of = _arena_values_from_rows(rows)
        if values:
            return {
                "benchmark": "lm_arena_elo",
                "as_of": as_of or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
                "values": values,
                "source": f"hf:{HF_DATASET}/{HF_STYLE_CONFIG}",
            }
        errors.append("hf filter: 0 'overall' rows parsed")
    except (FetchError, ValueError, KeyError) as exc:
        errors.append(f"hf filter: {exc}")

    # -- 1b. single-shot first-rows (top-100 overall, rank-ordered)
    try:
        r = _get(
            f"{DATASETS_SERVER}/first-rows",
            cfg.sources,
            params={"dataset": HF_DATASET, "config": HF_STYLE_CONFIG, "split": "latest"},
        )
        values, as_of = _arena_values_from_rows(
            w.get("row", {}) for w in r.json().get("rows", [])
        )
        if values:
            return {
                "benchmark": "lm_arena_elo",
                "as_of": as_of or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
                "values": values,
                "source": f"hf:{HF_DATASET}/{HF_STYLE_CONFIG} (first-rows)",
            }
        errors.append("hf first-rows: 0 'overall' rows parsed")
    except (FetchError, ValueError, KeyError) as exc:
        errors.append(f"hf first-rows: {exc}")

    # -- 2. community mirror API
    for url in source.get("endpoints", []):
        try:
            payload = _get(url, cfg.sources).json()
            models = payload.get("models") if isinstance(payload, dict) else None
            if not models:
                errors.append(f"{url}: no 'models' array")
                continue
            mirror_vals = {}
            for m in models:
                name, score = m.get("model"), m.get("score")
                if not name or score is None:
                    continue
                entry = {"score": float(score)}
                if m.get("ci"):
                    entry["ci95"] = [float(score) - float(m["ci"]), float(score) + float(m["ci"])]
                mirror_vals[str(name)] = entry
            if mirror_vals:
                return {
                    "benchmark": "lm_arena_elo",
                    "as_of": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
                    "values": mirror_vals,
                    "source": url,
                }
            errors.append(f"{url}: parsed 0 models")
        except (FetchError, ValueError) as exc:
            errors.append(str(exc))

    raise FetchError(
        "LMArena fetch failed: " + "; ".join(errors) + ". Fallback: copy the style-control "
        "Elo + CI from lmarena.ai/leaderboard into data/manual/scores.csv "
        "(benchmark=lm_arena_elo). Canonical dataset: huggingface.co/datasets/"
        "lmarena-ai/leaderboard-dataset (CC-BY-4.0)."
    )


# --------------------------------------------------------------------------
# OpenRouter usage share (§4 row 2) — daily tokens table -> share of parsed total
# --------------------------------------------------------------------------
_NUM_TOKENS = re.compile(r"([\d,.]+)\s*([kmbt]?)", re.I)
_MULTIPLIERS = {"": 1.0, "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}


def _parse_tokens(cell: str) -> float | None:
    """'47.8T tokens' -> 4.78e13; '603m' -> 6.03e8; '+55%' -> None."""
    m = _NUM_TOKENS.search(str(cell).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1)) * _MULTIPLIERS[m.group(2).lower()]
    except (ValueError, KeyError):
        return None


def _strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment).strip()


def fetch_openrouter(source: dict, cfg) -> dict:
    url = (source.get("endpoints") or ["https://openrouter.ai/rankings"])[0]
    html = _get(url, cfg.sources).text

    # the page renders several or-table tables; we need the one captioned
    # "Model rankings by tokens processed" (most recent complete day)
    rows: list[tuple[str, float]] = []
    for table in re.findall(r"<table.*?</table>", html, re.S):
        if "Model rankings by tokens processed" not in table:
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
            # data rows carry exactly one <th> (the row head = model name);
            # header rows are all <th> and are skipped naturally
            ths = re.findall(r"<th[^>]*>(.*?)</th>", tr, re.S)
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(ths) != 1 or not tds:
                continue
            model = _strip_tags(ths[0])
            if not model or not any(c.isalpha() for c in model):
                continue
            tokens = None
            for td in tds:  # the tokens cell literally contains the word 'token'
                if "token" in _strip_tags(td).lower():
                    tokens = _parse_tokens(td)
                    break
            if tokens:
                rows.append((model, tokens))
        break

    if len(rows) < 5:
        raise FetchError(
            "OpenRouter rankings page changed shape or has too few rows "
            f"({len(rows)} parsed). Fallback: copy top-model token share (%) "
            "from openrouter.ai/rankings into data/manual/scores.csv "
            "(benchmark=openrouter_usage)."
        )
    total = sum(t for _, t in rows)
    values = {
        model: {"score": round(100.0 * tokens / total, 4), "tokens": tokens}
        for model, tokens in rows
    }
    return {
        "benchmark": "openrouter_usage",
        "as_of": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "values": values,
        "source": f"{url} (share of parsed daily tokens, n={len(rows)})",
    }


# --------------------------------------------------------------------------
# Generic JSON URL (config-driven, no code changes to add sources)
# --------------------------------------------------------------------------
def fetch_json_url(source: dict, cfg) -> dict:
    spec = source.get("json_spec") or {}
    url = source.get("url")
    if not url:
        raise FetchError("json_url source missing 'url'")
    try:
        payload = _get(url, cfg.sources).json()
        root = _dig(payload, spec["root"]) if spec.get("root") else payload
        items = root if isinstance(root, list) else list(root.values())
        values = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            model, score = it.get(spec.get("model_key", "model")), it.get(spec.get("score_key", "score"))
            if model is None or score is None:
                continue
            values[str(model)] = {"score": float(score)}
        if not values:
            raise FetchError(f"{url}: 0 rows parsed with spec {spec}")
        bench = spec.get("benchmark") or _bench_id_for_source(source, cfg)
        return {
            "benchmark": bench,
            "as_of": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
            "values": values,
            "source": url,
        }
    except (FetchError, KeyError, TypeError, ValueError) as exc:
        raise FetchError(f"{source.get('url')}: {exc}. See fallback_note in config/sources.yaml.") from exc


def _bench_id_for_source(source: dict, cfg) -> str:
    for bid in cfg.bench_ids():
        if cfg.sources["sources"].get(bid) is source:
            return bid
    raise FetchError("could not resolve benchmark id for json_url source; set json_spec.benchmark")


# --------------------------------------------------------------------------
# llmstat — mirror only, never scored (§4). No scraper shipped on purpose.
# --------------------------------------------------------------------------
def fetch_llmstat(source: dict, cfg) -> dict:
    raise FetchError(
        "llmstat is a MIRROR (aggregator of the same benchmarks), not a scored voice — "
        "fetching it as data would double-count every benchmark it republishes "
        "(METHODOLOGY.md §4). Use it to source manual drops: copy numbers into "
        "data/manual/scores.csv."
    )


ADAPTERS = {
    "lm_arena": fetch_lm_arena,
    "openrouter": fetch_openrouter,
    "json_url": fetch_json_url,
    "llmstat": fetch_llmstat,
}


def fetch_all(cfg, allow_missing: bool = True, quiet: bool = False) -> tuple[list, list]:
    """Run all scored + enabled adapters. Returns (written, failures)."""
    written, failures = [], []
    for sid, source in cfg.sources.get("sources", {}).items():
        role = source.get("role", "scored")
        if role not in ("scored",) and not (role == "optional" and source.get("enabled")):
            continue
        adapter = ADAPTERS.get(source.get("kind"))
        if adapter is None:
            if not quiet:
                print(f"  · {sid}: kind '{source.get('kind')}' has no adapter — manual drop expected")
            continue
        try:
            snap = adapter(source, cfg)
            path = write_snapshot(snap)
            written.append((sid, path, len(snap["values"])))
            if not quiet:
                print(f"  ✔ {sid}: {len(snap['values'])} models -> {_rel(path)}")
        except FetchError as exc:
            failures.append((sid, str(exc)))
            if not quiet:
                print(f"  ✘ {sid}: {exc}")
    if failures and not allow_missing:
        raise FetchError(f"{len(failures)} source(s) failed: {[f[0] for f in failures]}")
    return written, failures

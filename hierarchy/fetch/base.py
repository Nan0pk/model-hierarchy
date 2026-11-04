"""Fetch adapters (METHODOLOGY.md §12).

Design contract: every adapter either returns a snapshot dict
{"benchmark": id, "as_of": ..., "values": {model: {"score": x, "ci95": [lo,hi]?}}}
or raises FetchError with actionable instructions. A failing source NEVER
fails the daily run — the pipeline aggregates whatever succeeded and flags
staleness. data/manual/scores.csv is the guaranteed fallback.

Arena uses only the complete, official style-controlled dataset. A raw-Elo
mirror or truncated first-rows response is not an equivalent fallback.
"""

from __future__ import annotations

import datetime as dt
import html as html_lib
import json
import math
import pathlib
import re
from html.parser import HTMLParser

import requests
import requests_cache

from ..config import DATA_DIR

HF_DATASET = "lmarena-ai/leaderboard-dataset"
HF_STYLE_CONFIG = "text_style_control"   # style-controlled text leaderboard (§4 row 1)
DATASETS_SERVER = "https://datasets-server.huggingface.co"


class FetchError(RuntimeError):
    pass


_HTTP = requests_cache.CachedSession(".cache/model-hierarchy-http", expire_after=24 * 60 * 60)


def _get(
    url: str,
    cfg_sources: dict,
    params: dict | None = None,
    extra_headers: dict | None = None,
) -> requests.Response:
    defaults = cfg_sources.get("defaults", {})
    headers = {"User-Agent": defaults.get("user_agent", "model-hierarchy")}
    headers.update(extra_headers or {})
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
    day = snap.get("as_of")
    try:
        if dt.date.fromisoformat(day) > dt.datetime.now(dt.timezone.utc).date():
            raise ValueError("future source date")
        if not isinstance(snap.get("values"), dict) or not snap["values"]:
            raise ValueError("empty values")
        for name, entry in snap["values"].items():
            score = entry.get("score") if isinstance(entry, dict) else entry
            if not name or isinstance(score, bool) or not math.isfinite(float(score)):
                raise ValueError("non-finite score or empty model")
            if isinstance(entry, dict) and entry.get("ci95") is not None:
                lo, hi = entry["ci95"]
                if not (math.isfinite(lo) and math.isfinite(hi) and lo <= score <= hi):
                    raise ValueError("invalid source confidence interval")
    except (ValueError, TypeError, KeyError) as exc:
        raise FetchError(f"Invalid snapshot; refusing to publish: {exc}") from exc
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
        total = int(d.get("num_rows_total", 0))
        if not rows:
            if offset < total or not out:
                raise FetchError("Arena pagination ended before the complete roster was received")
            break
        out.extend(w.get("row", {}) for w in rows)
        offset += len(rows)
        if not total:
            raise FetchError("Arena pagination metadata missing")
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
        d = str(row.get("leaderboard_publish_date", ""))[:10]
        if not d:
            raise FetchError("Arena row is missing leaderboard publication date")
        entry["as_of"] = d
        if str(name) in values:
            raise FetchError(f"Arena duplicate model row: {name}")
        values[str(name)] = entry
        if d > as_of:
            as_of = d
    return values, as_of


def fetch_lm_arena(source: dict, cfg) -> dict:
    rows = _hf_rows(cfg, HF_STYLE_CONFIG, "latest", where=_OVERALL_WHERE)
    values, as_of = _arena_values_from_rows(rows)
    if not values or not as_of:
        raise FetchError("Arena: complete style-controlled rows and publication date required")
    return {"benchmark": "lm_arena_elo", "as_of": as_of, "values": values,
            "source": "https://huggingface.co/datasets/" + HF_DATASET,
            "qualification": "text_style_control / latest / overall; complete paginated dataset"}


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

    # Use the visible model-ranking table (the page's default This Week view),
    # not its separate daily/monthly text summaries or author market-share table.
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
    plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", html))
    date_match = re.search(
        r"Usage\s*data\s*through\s*([A-Za-z]+ \d{1,2}, \d{4})", plain, re.I
    )
    if not date_match:
        raise FetchError(f"{url}: published usage date not found; refusing to use scrape time")
    as_of = dt.datetime.strptime(date_match.group(1), "%b %d, %Y").date().isoformat()
    total = sum(t for _, t in rows)
    values = {
        model: {"score": round(100.0 * tokens / total, 4), "tokens": tokens}
        for model, tokens in rows
    }
    return {
        "benchmark": "openrouter_usage",
        "as_of": as_of,
        "values": values,
        "source": url,
        "provenance_type": "usage_aggregate",
        "qualification": f"Top {len(rows)} visible weekly-ranking rows; share normalized within parsed rows only, not global traffic share",
    }


# --------------------------------------------------------------------------
# Official leaderboard APIs
# --------------------------------------------------------------------------
class _TableParser(HTMLParser):
    """Small dependency-free HTML table reader for source-owned static boards."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.page_text: list[str] = []
        self._table_depth = 0
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self.tables.append([])
        elif self._table_depth == 1 and tag == "tr":
            self._row = []
        elif self._table_depth == 1 and tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.page_text.append(text)
            if self._cell is not None:
                self._cell.append(text)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._table_depth == 1 and tag in {"th", "td"} and self._cell is not None:
            self._row.append(" ".join(self._cell).strip())
            self._cell = None
        elif self._table_depth == 1 and tag == "tr" and self._row is not None:
            if self._row:
                self.tables[-1].append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1


def fetch_vals_table(source: dict, cfg) -> dict:
    """Fetch a methodology-documented Vals AI independent benchmark result table.

    Vals runs the benchmark itself and publishes its evaluation date and
    methodology. Optional fixed-column filters (e.g. SWE harness) prevent
    mixing materially different evaluation setups.
    """
    url = source.get("url")
    spec = source.get("table_spec") or {}
    required = ("model_header", "score_header", "date_regex")
    if not url or any(not spec.get(k) for k in required):
        raise FetchError("vals_table requires url and model_header, score_header, date_regex")
    try:
        response = _get(url, cfg.sources)
        parser = _TableParser()
        parser.feed(response.text)
        model_col = score_col = filter_col = None
        rows = None
        for table in parser.tables:
            if not table:
                continue
            headers = [" ".join(cell.casefold().split()) for cell in table[0]]
            model_col = next((i for i, h in enumerate(headers) if h == spec["model_header"].casefold()), None)
            score_col = next((i for i, h in enumerate(headers) if h == spec["score_header"].casefold()), None)
            filter_col = None
            if spec.get("filter_header"):
                filter_col = next((i for i, h in enumerate(headers) if h == spec["filter_header"].casefold()), None)
            if model_col is not None and score_col is not None and (
                not spec.get("filter_header") or filter_col is not None
            ):
                rows = table[1:]
                break
        if rows is None:
            raise FetchError(f"{url}: no results table matches the configured headers")
        expected_filter = str(spec.get("filter_value", "")).casefold()
        values = {}
        for row in rows:
            needed_col = max(model_col, score_col, filter_col if filter_col is not None else 0)
            if needed_col >= len(row):
                continue
            if filter_col is not None and row[filter_col].casefold() != expected_filter:
                continue
            model = row[model_col]
            try:
                score = float(row[score_col].replace("%", "").replace(",", ""))
            except ValueError:
                continue
            if model and math.isfinite(score):
                values[model] = {"score": score}
        if not values:
            raise FetchError(f"{url}: no valid rows after table and evaluation filters")
        date_matches = re.findall(spec["date_regex"], " ".join(parser.page_text), flags=re.I)
        if not date_matches:
            raise FetchError(f"{url}: benchmark evaluation date not found")
        # Choose the newest explicitly published evaluation date, never the
        # scrape date, as the snapshot's freshness signal.
        dates = []
        for token in date_matches:
            token = token.strip()
            try:
                parsed = dt.datetime.strptime(token, "%b %d, %Y")
            except ValueError:
                try:
                    parsed = dt.datetime.strptime(token, "%B %d, %Y")
                except ValueError:
                    month, day, year = map(int, re.split(r"[/.-]", token))
                    parsed = dt.datetime(year, month, day)
            dates.append(parsed.date())
        as_of = max(dates).isoformat()
        return {
            "benchmark": source.get("benchmark") or _bench_id_for_source(source, cfg),
            "as_of": as_of,
            "values": values,
            "source": url,
            "provenance_type": "independent_evaluation",
            "evaluation_provider": "Vals AI",
            **({"qualification": source["qualification"]} if source.get("qualification") else {}),
            **({"harness": spec["filter_value"]} if spec.get("filter_value") else {}),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise FetchError(f"{url}: could not parse Vals AI results table: {exc}") from exc


def fetch_livecodebench(source: dict, cfg) -> dict:
    """Fetch the latest official LiveCodeBench leaderboard table.

    The official page declares the evaluated date window; that end date, not
    the scrape date, is stamped so stale frozen releases are not misrepresented
    as fresh measurements.
    """
    url = source.get("url")
    spec = source.get("table_spec") or {}
    if not url or not spec.get("date_regex"):
        raise FetchError("livecodebench requires url and table_spec.date_regex")
    try:
        response = _get(url, cfg.sources)
        parser = _TableParser()
        parser.feed(response.text)
        model_col = score_col = None
        rows = None
        for table in parser.tables:
            if not table:
                continue
            headers = [cell.casefold() for cell in table[0]]
            model_col = next((i for i, h in enumerate(headers) if h == "model"), None)
            score_col = next((i for i, h in enumerate(headers) if h == "pass@1"), None)
            if model_col is not None and score_col is not None:
                rows = table[1:]
                break
        if rows is None:
            raise FetchError(f"{url}: no official table with Model and Pass@1 columns found")
        values = {}
        for row in rows:
            if max(model_col, score_col) >= len(row):
                continue
            model = row[model_col]
            try:
                score = float(row[score_col].replace("%", ""))
            except ValueError:
                continue
            if model and math.isfinite(score):
                values[model] = {"score": score}
        if not values:
            raise FetchError(f"{url}: official table parsed zero valid model scores")
        matches = re.findall(spec["date_regex"], " ".join(parser.page_text), flags=re.I)
        if not matches:
            raise FetchError(f"{url}: official evaluation window date not found")
        date_token = matches[-1]
        month, day, year = map(int, re.split(r"[/.-]", date_token))
        as_of = dt.date(year, month, day).isoformat()
        return {
            "benchmark": source.get("benchmark") or _bench_id_for_source(source, cfg),
            "as_of": as_of,
            "values": values,
            "source": url,
            "provenance_type": "orchestrator_run",
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise FetchError(f"{url}: could not parse official LiveCodeBench board: {exc}") from exc


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
            "as_of": str(_dig(payload, spec["date_path"]))[:10],
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
    "vals_table": fetch_vals_table,
    "livecodebench": fetch_livecodebench,
    "llmstat": fetch_llmstat,
}


def fetch_all(cfg, allow_missing: bool = True, quiet: bool = False) -> tuple[list, list]:
    """Run all scored + enabled adapters. Returns (written, failures)."""
    written, failures = [], []
    for sid, source in cfg.sources.get("sources", {}).items():
        role = source.get("role", "scored")
        if role not in ("scored",) and not (role == "optional" and source.get("enabled")):
            continue
        kind = source.get("kind")
        if kind == "manual":
            if not quiet:
                print(f"  · {sid}: intentionally manual source — see fallback_note")
            continue
        adapter = ADAPTERS.get(kind)
        if adapter is None:
            message = (
                f"source kind {source.get('kind')!r} has no fetch adapter; "
                "this benchmark is manual-only until an adapter is implemented"
            )
            failures.append((sid, message))
            if not quiet:
                print(f"  ✘ {sid}: {message}")
            continue
        try:
            snap = adapter(source, cfg)
            path = write_snapshot(snap)
            written.append((sid, path, len(snap["values"])))
            if not quiet:
                print(f"  ✔ {sid}: {len(snap['values'])} models -> {_rel(path)}")
        except (FetchError, ValueError, KeyError, TypeError) as exc:
            failures.append((sid, str(exc)))
            if not quiet:
                print(f"  ✘ {sid}: {exc}")
    if failures and not allow_missing:
        raise FetchError(f"{len(failures)} source(s) failed: {[f[0] for f in failures]}")
    return written, failures

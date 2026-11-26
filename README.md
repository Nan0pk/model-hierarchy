# Model Atlas · model-hierarchy

[![tests](https://github.com/Nan0pk/model-hierarchy/actions/workflows/tests.yml/badge.svg)](https://github.com/Nan0pk/model-hierarchy/actions/workflows/tests.yml)
[![daily refresh](https://github.com/Nan0pk/model-hierarchy/actions/workflows/daily.yml/badge.svg)](https://github.com/Nan0pk/model-hierarchy/actions/workflows/daily.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**AI model rankings with the evidence still attached.**

Explore original scores from **Artificial Analysis, Arena, LiveBench 2.0, and Terminal-Bench 4.1**.
Keep exact reasoning settings, benchmark versions, uncertainty when supplied, and source dates.
No popularity-based model exclusions. No fictional universal winner.

[**Open the dashboard →**](https://nan0pk.github.io/model-hierarchy/dashboard/) ·
[Methodology](METHODOLOGY.md) · [Ranking quality audit](docs/RANKING_AUDIT.md) ·
Atlas ranking [JSON](output/atlas.json) · [CSV](output/atlas.csv) ·
Source boards [JSON](output/leaderboards.json) · [CSV](output/leaderboards.csv)

## What changed in v2

The previous pipeline filtered every source through OpenRouter's **ten visible usage leaders**.
It eliminated most of the model roster and crowned the only remaining eligible model with a
meaningless singleton T1. Usage is now neither an eligibility gate nor a capability score.

The dashboard opens on the **Atlas model hierarchy**. It takes each model’s median
tested score within each evaluator, converts that standing to a percentile among
the models at least two evaluators share, and
averages across at least two current evaluators. Because LiveBench's field is
stronger than Arena's or AA's, each board gets a fitted offset so a model that skipped
a harder board gains nothing from it; models on every board keep their plain average.
The ranking is also published as [`output/atlas.csv`](output/atlas.csv).
Above the table, three picks (top model, best under $1 per task, cheapest in the top 10)
and a **value map** of Atlas score against cost per task show the best-value frontier:
the models nothing else beats on both score and price. Select **Effort levels** to rank
exact reasoning configurations, or expand a row for its original measurements.
Terminal-Bench stays in its own model-plus-agent view.
The initial audited views contain 91 AA configurations, 419 Arena entries, 32 LiveBench models,
and 23 Terminal-Bench systems. These are source entries, not distinct model families. The
experimental geometric composite remains available but is withheld if its evidence is inadequate.
See [the audit](docs/RANKING_AUDIT.md) for scoring, freshness, identity, and statistical repairs.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

python -m hierarchy validate
python -m hierarchy aggregate  # offline: native boards + composite audit + README
python -m http.server 8000 --bind 0.0.0.0
# open /dashboard/
```

The dashboard is static and dependency-free at runtime. Search source rosters, switch evaluators,
filter creators or agent harnesses, sort task scores/costs, expand a row's evidence, and download
JSON/CSV. Search and sorting preserve source score ranks. Missing data is never a zero score.
The UI recalculates staleness even when daily refreshes stop.

## Refresh

```bash
python -m hierarchy run                   # best effort: fetch + publish + evidence audit
python -m hierarchy run --strict          # nonzero if any automatic source fails
python -m hierarchy fetch --allow-missing # fetch only; retain last-good snapshots on failure
python -m hierarchy boards                # publish native views only, offline
```

[**Open the refresh workflow →**](https://github.com/Nan0pk/model-hierarchy/actions/workflows/daily.yml)
The workflow supports scheduled and manual runs. Select the branch you intend to publish; an
authenticated contributor must start it. The static dashboard's **Reload snapshot** button reloads
published files only; it does not claim to run GitHub Actions or carry credentials.

Adapters read the public source-owned tables and the official Arena dataset. They reject metric
version changes, invalid scores, duplicate identities, truncated rosters, and source date regression.
A failed refresh keeps the previous valid snapshot **without refreshing its dates**, records the
failure, and displays it in the dashboard. Native views never silently fall back to synthetic data.

The initial AA/LiveBench/Terminal-Bench snapshots are explicitly labeled public-table transcriptions
observed on 2026-11-03; they do **not** claim an evaluation date or a successful unattended scrape.
The retained Arena snapshot keeps its original source date. See the
[capture record](data/evidence/2026-11-03/README.md) for sources, scope, and checksums.

## Read the ranks correctly

- **Artificial Analysis:** current-model Intelligence Index **v5.0.1**; rounded raw scores, exact
  effort and fallback settings (including grouped release variants). Equal displayed scores share
  a rank. No invented CIs.
- **Arena:** complete official **style-controlled text / overall** roster, not raw text or agent
  rankings. Includes historical models; vote counts and source 95% intervals are retained.
- **LiveBench 2.0:** official release CSV/JSON feed with overall plus seven task suites and
  release dates, separate from the retired LiveBench metric.
- **Terminal-Bench 4.1:** **model + agent system** performance across all evaluated display
  configurations, with source-supplied 95% confidence margins. Different harnesses are not
  controlled comparisons of base models. Release dates are not evaluation dates.

Scores across these boards are **not interchangeable**. A recently observed board does not prove
public model availability, a recent model release, or a recent evaluation. Unknown dates are shown
as unknown, and stale snapshots remain clearly labeled reference data.

## Source-native leaderboards

<!-- leaderboard:start -->

Source-native rankings. **Scores from different boards are not interchangeable.**

### Artificial Analysis — Intelligence Index v5.0.1

[Source](https://artificialanalysis.ai/leaderboards/models) · 127 scored entries · published: not supplied · observed: 2026-11-24 · **available**

| Rank | Model / configuration | Score |
|---|---|---|
| 1 | Claude Fable 5.2 (Max, Default Fallback) | 65 |
| 2 | Claude Fable 5.2 (High, Default Fallback) | 62 |
| 2 | Claude Fable 5.2 (Xhigh, Default Fallback) | 62 |
| 2 | GPT-6.2 Astra (Max) | 62 |
| 2 | GPT-6.2 Astra (Xhigh) | 62 |
| 6 | Gemini 4 Neon (Xhigh) | 61 |
| 7 | GPT-6.2 Astra (High) | 60 |
| 7 | Gemini 4 Carbon (High) | 60 |
| 7 | Gemini 4 Neon (High) | 60 |
| 10 | Claude Opus 5.5 (Max, Default Fallback) | 59 |

Source-native Intelligence Index v5.0.1 (CritPt v2 regrade across the 9-benchmark v5 suite), not a Model Atlas aggregate. Reasoning effort and fallback settings are distinct entries, including configurations collapsed under release groups on the source page. Public table scores are rounded integers; equal displayed scores share a rank here. No confidence intervals are published in this table. Cost per task is not API price per million tokens; a rounded $0.00 is not proof of free usage. The source's current-model view is not a guarantee of public availability.

> Evaluation/publication date not supplied by the table; observed date is retrieval only.

> Last refresh failed; retaining the last valid snapshot.

### Arena — Text · style-controlled · overall

[Source](https://arena.ai/leaderboard/text) · 427 scored entries · published: 2026-11-22 · observed: 2026-11-26 · **available**

| Rank | Model / configuration | Score |
|---|---|---|
| 1 | Gemini 4 Carbon (High) | 1526.5 |
| 2 | Gemini 4 Argon (High) | 1519.8 |
| 3 | Gemini 4 Neon (High) | 1512.2 |
| 4 | Muse Wonder (Max) | 1511.9 |
| 5 | Claude Opus 5.5 (High) | 1507.0 |
| 6 | Claude Fable 5 (High) | 1504.1 |
| 7 | Claude Opus 4.6 (High) | 1502.9 |
| 8 | Claude Fable 5.2 (Max) | 1502.2 |
| 9 | Claude Fable 5.1 (Max) | 1502.1 |
| 10 | Claude Opus 4.7 (High) | 1501.2 |

Official text_style_control dataset, overall category only. Not the raw text, coding, or agent board. Retains the full source roster, including historical models. A recent board publication does not mean every model was recently released or re-evaluated. Source 95% intervals and vote counts are preserved; adjacent ranks are not claims of statistical separation.

### LiveBench — LiveBench 2.0

[Source](https://livebench.ai/) · 41 scored entries · published: 2026-11-11 · observed: 2026-11-26 · **stale**

| Rank | Model / configuration | Score |
|---|---|---|
| 1 | Gemini 4 Neon | 87.4 |
| 2 | Claude Fable 5.2 (xhigh) | 84.9 |
| 2 | GPT-6.2 Astra | 84.9 |
| 4 | GPT-6 Astra | 84.2 |
| 5 | Claude Fable 5.1 | 84.0 |
| 6 | Claude Opus 5.5 | 83.4 |
| 7 | Gemini 4 Carbon | 83.3 |
| 8 | GPT-6.1 Sol | 81.2 |
| 9 | GPT-6.2 Sol | 80.3 |
| 10 | GPT-6.1 Terra | 78.6 |

LiveBench 2.0 official release feed, NOT the retired LiveBench overall benchmark. Overall is the source's weighted mean (Long Agentic ×2; Design and Coding ×1.5; other suites ×1). Suites are single runs; effort is highest supported unless the source's model notes say otherwise. No per-model confidence intervals are supplied. Missing suite results stay missing, not zero. Cost is per successful task.

> Stale snapshot (15 days); not a current ranking.

### Terminal-Bench — Terminal-Bench 4.1

[Source](https://www.tbench.ai/) · 67 scored entries · published: 2026-11-20 · observed: 2026-11-26 · **available**

| Rank | Model / configuration | Score |
|---|---|---|
| 1 | Copilot Fusion (max) / GitHub Copilot | 71.2 |
| 2 | Fable 5.2 (max) / Claude Code | 65.8 |
| 2 | Opus 5.5 (max) / Claude Code | 65.8 |
| 4 | Gemini 4 Carbon (high) / Antigravity CLI | 64.5 |
| 5 | Sonnet 5.5 (max) / Claude Code | 63.9 |
| 6 | GPT-6.2 Astra (max) / Codex | 62.1 |
| 7 | GPT-6.2 Sol (max) / Codex | 61.5 |
| 8 | Gemini 4 Neon (xhigh) / Antigravity CLI | 61.2 |
| 9 | GPT-6.1 Sol (max) / Codex | 60.9 |
| 10 | GPT-6 Astra (max) / Codex | 60.3 |

SYSTEM ranking: model + reasoning setting + agent harness on Terminal-Bench 4.1. Mixed harnesses must not be interpreted as an isolated model comparison. No best-agent cherry-picking or reuse in the legacy Terminal-Bench composite slots. Release dates are model release dates, NOT evaluation dates. Published ± margins reflect the source's 95% confidence half-widths across evaluation trials.


<!-- leaderboard:end -->

## Experimental composite evidence audit

The old five-pillar geometric aggregate lives in `output/leaderboard.json` (singular). It is not
the dashboard default. It requires five distinct measurements across three pillars, at least
five comparator models, and evidence in every capability domain across the cohort before it
publishes rankings. Usage is context-only, split aliases count once, and data gaps are visible.

<!-- composite:start -->

**Experimental composite withheld.**

- No comparable data for entire pillars: agentic, math.

536 models remain in the evidence roster; none are deleted for being absent from a usage top ten. Use the source-native rankings above. Missing data is not a low score.

<!-- composite:end -->

For compatible, cited composite observations, use `data/manual/scores.csv`:
`benchmark,model,score,as_of,source,notes[,ci95_lo,ci95_hi]`. Rows retain their individual dates
and citations and augment, rather than replace, a benchmark's roster. Never put a new benchmark
version or a different agent harness in an old metric slot just to obtain more coverage.

## Tests and synthetic demo

```bash
pytest -q                         # scoring, integrity, parsers, provenance, retention
ruff check hierarchy tests
npm ci && npm test                 # dashboard data/rendering/interaction regressions
python -m hierarchy demo           # explicitly synthetic; separate demo outputs
```

The demo writes `output/demo_leaderboard.{json,csv}` only and is never substituted for live data.
The historical dashboard preview image also uses synthetic data and is not a current screenshot.

<details><summary>Synthetic composite example (not current model rankings)</summary>

<!-- demo-leaderboard:start -->

> ⚠️ **Synthetic demo data** (see `demo/scores.csv`) — illustrates the output shape only. Run `python -m hierarchy run` for a real leaderboard.

Tier hierarchy (G-score 0-100) — generated 2026-11-26 07:36 UTC — SYNTHETIC DEMO DATA
────────────────────────────────────────────────────────────────
T1 │ claude opus 4.5 · gemini 3 pro · gpt 5.1
T2 │ grok 4.1
T3 │ deepseek v3.2 · kimi k2.5
T4 │ glm 4.7 · qwen3 max
T5 │ gpt 5 mini · minimax m2.5
T6 │ mistral large 3
T7 │ llama 4 maverick
────────────────────────────────────────────────────────────────
Tiers are a bootstrap grouping heuristic, not proof of equivalence (METHODOLOGY.md).

| # | Model | Tier | G | 95% CI | Hum. | Know. | Math | Code | Agent | Cov. | Flags |
|---|-------|------|---|--------|---|---|---|---|---|------|-------|
| 1 | `gpt 5.1` | T1 | **93.6** | 89.1–95.9 | 98 | 96 | 94 | 96 | 94 | 94% | – |
| 2 | `gemini 3 pro` | T1 | **93.0** | 89.4–94.8 | 100 | 98 | 100 | 89 | 84 | 94% | – |
| 3 | `claude opus 4.5` | T1 | **88.8** | 84.1–92.8 | 93 | 86 | 84 | 95 | 100 | 94% | – |
| 4 | `grok 4.1` | T2 | **73.2** | 68.7–77.5 | 80 | 76 | 75 | 70 | 71 | 94% | – |
| 5 | `kimi k2.5` | T3 | **60.6** | 55.8–65.1 | 65 | 57 | 61 | 69 | 58 | 94% | – |
| 6 | `deepseek v3.2` | T3 | **59.7** | 54.7–64.2 | 56 | 66 | 69 | 65 | 59 | 94% | – |
| 7 | `glm 4.7` | T4 | **52.7** | 48.2–57.0 | 62 | 46 | 53 | 53 | 48 | 94% | – |
| 8 | `qwen3 max` | T4 | **47.4** | 42.8–51.8 | 52 | 47 | 48 | 46 | 42 | 94% | – |
| 9 | `gpt 5 mini` | T5 | **36.6** | 32.2–40.7 | 43 | 33 | 39 | 34 | 33 | 94% | – |
| 10 | `minimax m2.5` | T5 | **31.3** | 27.2–35.0 | 40 | 23 | 34 | 33 | 26 | 90% | – |
| 11 | `mistral large 3` | T6 | **13.2** | 8.6–16.0 | 18 | 11 | 13 | 11 | 11 | 91% | – |
| 12 | `llama 4 maverick` | T7 | **4.9** | 4.9–4.9 | 5 | 5 | 5 | 5 | 5 | 94% | – |

<!-- demo-leaderboard:end -->

</details>

## Repository map

```text
config/leaderboards.yaml        source-native metric versions, adapters, qualifications
config/weights.yaml             experimental composite weights and publication gates
config/models.yaml              reviewed exact identity aliases (not family merging)
hierarchy/boards.py             native snapshots, integrity, ranks, provenance, export
hierarchy/fetch/boards.py        version-pinned public source adapters + refresh health
hierarchy/pipeline.py            composite, sparse-cohort gates, evidence diagnostics
data/leaderboards/               retained dated native snapshots + fetch status
data/evidence/                   dated source transcriptions and capture notes
data/raw/, data/manual/          legacy composite observations
output/atlas.{json,csv}           Atlas model and effort rankings (node dashboard/export.mjs)
output/leaderboards.{json,csv}    main native-board publication (plural)
output/catalogue.json             cross-board name discovery index (not used for scoring)
output/leaderboard.{json,csv}     experimental composite and evidence audit (singular)
dashboard/                      static, source-aware explorer
METHODOLOGY.md                   current normative specification
docs/RANKING_AUDIT.md             findings and repairs
```

## Automation

The daily workflow (`.github/workflows/daily.yml`) fetches, validates, publishes, runs both Python
(`pytest`, `ruff`) and dashboard (`npm test`) suites, and commits only when meaningful data or
status changes occur (suppressing timestamp-only commits). Pull requests and pushes to `main` are
verified offline by `.github/workflows/tests.yml`.

No secrets are required by the public-source adapters. Sites can change or block scraping;
transparent failure reporting and dated last-good snapshots are part of the ranking, not an
excuse to re-date old results.

## Maintenance model

Built to run unattended: the daily job fetches, validates, publishes, tests, and commits only
meaningful changes. Human action is needed when a source changes *meaning*, not when it
changes *markup*.

**Automatic — no action needed**

- A failing source retains its dated last-good snapshot, keeps its recorded dates, and shows
  the failure in the dashboard; the other boards keep publishing. The Atlas ranking re-widens
  by itself when a board recovers.
- `dashboard/stamps.mjs` rewrites the dashboard's cache-busting `?v=` hashes each daily build,
  so a forgotten stamp heals itself; `scripts/sync_version.py` propagates
  `hierarchy.METHOD_VERSION` into `pyproject.toml` and `config/leaderboards.yaml`.
- Persisted refresh failures open, update, and close a GitHub issue automatically
  (`scripts/report_refresh_failures.py`), so a broken adapter becomes a visible TODO instead
  of a line in an Actions log.

**Deliberate — needs you**

- A source changing metric version or semantics (e.g. a new Artificial Analysis index) fails
  closed by design. Migrate deliberately: review, bump the pin, add fixtures, add a changelog
  line. The adapter error now lists the versions the source mentions to make that review a
  five-minute task.
- Methodology edits stay manual on purpose; `hierarchy validate` and the tests fail if the
  stated version drifts from the code.

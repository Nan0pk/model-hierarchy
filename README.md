# Model Atlas · model-hierarchy

**AI model rankings with the evidence still attached.**

Explore original scores from **Artificial Analysis, Arena, LiveBench 2.0, and Terminal-Bench 4.0**.
Keep exact reasoning settings, benchmark versions, uncertainty when supplied, and source dates.
No popularity-based model exclusions. No fictional universal winner.

[**Open the dashboard →**](https://nan0pk.github.io/model-hierarchy/dashboard/) ·
[Methodology](METHODOLOGY.md) · [Ranking quality audit](docs/RANKING_AUDIT.md) ·
[JSON](output/leaderboards.json) · [CSV](output/leaderboards.csv)

## What changed in v2

The previous pipeline filtered every source through OpenRouter's **ten visible usage leaders**.
It eliminated most of the model roster and crowned the only remaining eligible model with a
meaningless singleton T1. Usage is now neither an eligibility gate nor a capability score.

The default publication is **source-native rankings**, not an average of incompatible indexes.
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

- **Artificial Analysis:** current-model Intelligence Index **v5.0**; rounded raw scores, exact effort
  and fallback settings. Equal displayed scores share a rank. No invented CIs.
- **Arena:** complete official **style-controlled text / overall** roster, not raw text or agent
  rankings. Includes historical models; vote counts and source 95% intervals are retained.
- **LiveBench 2.0:** source overall plus seven task suites, separate from the retired LiveBench metric.
- **Terminal-Bench 4.0:** **model + agent system** performance. Different harnesses are not controlled
  comparisons of base models. Release dates are not evaluation dates.

Scores across these boards are **not interchangeable**. A recently observed board does not prove
public model availability, a recent model release, or a recent evaluation. Unknown dates are shown
as unknown, and stale snapshots remain clearly labeled reference data.

## Source-native leaderboards

<!-- leaderboard:start -->

Source-native rankings. **Scores from different boards are not interchangeable.**

### Artificial Analysis — Intelligence Index v5.0

[Source](https://artificialanalysis.ai/leaderboards/models) · 91 scored entries · published: not supplied · observed: 2026-11-03 · **available**

| Rank | Model / configuration | Score |
|---|---|---|
| 1 | Gemini 4 Carbon (high) | 59 |
| 2 | Claude Opus 5.5 (max with fallback) | 58 |
| 2 | Gemini 4 Carbon (medium) | 58 |
| 4 | Claude Opus 5.5 (xhigh with fallback) | 57 |
| 4 | GPT-6 Astra (max) | 57 |
| 6 | GPT-6 Astra (high) | 55 |
| 6 | GPT-6 Astra (xhigh) | 55 |
| 6 | GPT-6.1 Sol (max) | 55 |
| 9 | Claude Sonnet 5.5 (max with fallback) | 54 |
| 9 | Gemini 4 Carbon (low) | 54 |

Source-native Intelligence Index, not a Model Atlas aggregate. Reasoning effort and fallback settings are distinct entries. Public table scores are rounded; equal displayed scores share a rank here. No confidence intervals are published in this table. Cost per task is not API price per million tokens; a rounded $0.00 is not proof of free usage. The source's current-model view is not a guarantee of public availability.

> Evaluation/publication date not supplied by the table; observed date is retrieval only.

> Source table transcribed on 2026-11-03. Retrieval is not an evaluation date. See data/evidence/2026-11-03/README.md.

> Last refresh failed; retaining the last valid snapshot.

### Arena — Text · style-controlled · overall

[Source](https://arena.ai/leaderboard/text) · 419 scored entries · published: 2026-10-28 · observed: not recorded · **stale**

| Rank | Model / configuration | Score |
|---|---|---|
| 1 | Gemini 4 Carbon (High) | 1527.5 |
| 2 | Gemini 4 Argon (High) | 1520.3 |
| 3 | Claude Opus 5.5 (High) | 1508.7 |
| 4 | Muse Wonder (Max) | 1507.1 |
| 5 | Claude Fable 5.1 (Max) | 1504.4 |
| 6 | Claude Fable 5 (High) | 1503.9 |
| 7 | Claude Opus 4.6 (High) | 1503.2 |
| 8 | Claude Opus 4.7 (High) | 1501.0 |
| 9 | Claude Opus 4.6 | 1496.1 |
| 10 | Gemini 3.8 Flash (High) | 1495.9 |

Official text_style_control dataset, overall category only. Not the raw text, coding, or agent board. Retains the full source roster, including historical models. A recent board publication does not mean every model was recently released or re-evaluated. Source 95% intervals and vote counts are preserved; adjacent ranks are not claims of statistical separation.

> Retrieval time was not recorded in this retained snapshot.

> Stale snapshot (17 days); not a current ranking.

> Retained canonical snapshot; original retrieval time is unknown. Raw text and style-control boards must not be conflated.

> Last refresh failed; retaining the last valid snapshot.

### LiveBench — LiveBench 2.0

[Source](https://livebench.ai/) · 32 scored entries · published: not supplied · observed: 2026-11-03 · **available**

| Rank | Model / configuration | Score |
|---|---|---|
| 1 | Claude Fable 5.1 | 85.7 |
| 2 | GPT-6 Astra | 85.6 |
| 3 | Claude Opus 5.5 | 85.1 |
| 4 | GPT-6.1 Sol | 84.1 |
| 5 | Claude Sonnet 5.5 | 80.0 |
| 6 | Gemini 4 Argon | 79.3 |
| 7 | GPT-6.1 Terra | 77.8 |
| 8 | Muse Wonder 1.0 | 74.2 |
| 9 | DeepSeek V4.1 Flash 1017 | 72.9 |
| 10 | Kimi K3.1 Pro | 71.3 |

LiveBench 2.0, NOT the retired LiveBench overall benchmark. Overall is the source's weighted mean (Agentic ×2; Design and Coding ×1.5; other suites ×1). Suites are single runs; effort is highest supported unless the source's expanded row says otherwise. No per-model confidence intervals are supplied. Missing suite results stay missing, not zero. Cost is per successful task.

> Evaluation/publication date not supplied by the table; observed date is retrieval only.

> Source table transcribed on 2026-11-03. Retrieval is not an evaluation date. See data/evidence/2026-11-03/README.md.

> Last refresh failed; retaining the last valid snapshot.

### Terminal-Bench — Terminal-Bench 4.0

[Source](https://www.tbench.ai/) · 23 scored entries · published: not supplied · observed: 2026-11-03 · **available**

| Rank | Model / configuration | Score |
|---|---|---|
| 1 | Opus 5.5 (max) / Claude Code | 64.8 |
| 2 | Sonnet 5.5 (max) / Claude Code | 61.8 |
| 3 | GPT-6 Astra (max) / Codex | 58.2 |
| 3 | GPT-6.1 Sol (max) / Codex | 58.2 |
| 5 | Fable 5.1 (max) / Claude Code | 57.9 |
| 6 | Opus 5 (xhigh) / Claude Code | 53.9 |
| 7 | GPT-6 Sol (max) / Codex | 49.4 |
| 8 | Fable 5 (max) / Claude Code | 44.5 |
| 9 | GLM-5.3 (max) / Claude Code | 41.8 |
| 10 | Grok 4.7 (xhigh) / Grok Build | 37.6 |

SYSTEM ranking: model + reasoning setting + agent harness. Mixed harnesses must not be interpreted as an isolated model comparison. No best-agent cherry-picking or reuse in the legacy Terminal-Bench composite slots. Release dates are model release dates, NOT evaluation dates. Published ± margins are retained without assuming an unstated confidence level.

> Evaluation/publication date not supplied by the table; observed date is retrieval only.

> Source table transcribed on 2026-11-03. Retrieval is not an evaluation date. See data/evidence/2026-11-03/README.md.

> Last refresh failed; retaining the last valid snapshot.


<!-- leaderboard:end -->

## Experimental composite evidence audit

The old five-pillar geometric aggregate lives in `output/leaderboard.json` (singular). It is not
the dashboard default. It requires five distinct measurements across three pillars, at least
five comparator models, and evidence in every capability domain across the cohort before it
publishes rankings. Usage is context-only, split aliases count once, and data gaps are visible.

<!-- composite:start -->

**Experimental composite withheld.**

- No comparable data for entire pillars: agentic, math.

529 models remain in the evidence roster; none are deleted for being absent from a usage top ten. Use the source-native rankings above. Missing data is not a low score.

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

Tier hierarchy (G-score 0-100) — generated 2026-11-03 20:25 UTC — SYNTHETIC DEMO DATA
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
output/leaderboards.{json,csv}    main native-board publication (plural)
output/leaderboard.{json,csv}     experimental composite and evidence audit (singular)
dashboard/                      static, source-aware explorer
METHODOLOGY.md                   current normative specification
docs/RANKING_AUDIT.md             findings and repairs
```

## Automation

The daily workflow fetches, validates, publishes, runs Python tests, and commits its selected
branch's data. Source failures are soft by default but never invisible. Run the Python and
dashboard tests using the commands above. The additional pull-request CI and daily dashboard-test
workflow edits are deferred until workflow-write permission is available.

No secrets are required by the public-source adapters. Sites can change or block scraping;
transparent failure reporting and dated last-good snapshots are part of the ranking, not an
excuse to re-date old results.

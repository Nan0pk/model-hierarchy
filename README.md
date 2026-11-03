# model-hierarchy

**One number per model, every day: a reality-anchored tier hierarchy of frontier models,
aggregated from LMArena, OpenRouter usage, GPQA, LiveBench, SEAL, AIME, HMMT, SWE-bench
Verified, LiveCodeBench, Terminal-Bench and Tau²-bench.**

> Which models are *comprehensively* better than the rest right now — not per-benchmark noise,
> not vibes: a declared-weight aggregate over 5 capability pillars, with confidence intervals,
> tier groupings, and pairwise "confidently better" probabilities.

📖 **The methodology — every weight, every formula, every tradeoff — is specified in
[METHODOLOGY.md](METHODOLOGY.md).** This README shows you how to run it.

## Refresh the live leaderboard

[**Run a full refresh now →**](https://github.com/Nan0pk/model-hierarchy/actions/workflows/daily.yml)

This opens the repository's `daily` workflow. Select **Run workflow** with branch `main` to run
fetch → validate → aggregate → render → tests → auto-commit. When the run succeeds, reload the
[dashboard](https://nan0pk.github.io/model-hierarchy/dashboard/) or README. GitHub requires an
authenticated owner/contributor to start Actions; a static Pages button cannot safely carry a
GitHub token or dispatch jobs directly.

The refresh uses trusted configured sources only. If fresh data does not cover at least five
benchmarks across three pillars, the honest result is still an empty ranked hierarchy—not synthetic
scores presented as current.

## Quickstart

```bash
pip install -r requirements.txt

python -m hierarchy validate   # config ↔ methodology consistency check
python -m hierarchy demo       # end-to-end run on bundled synthetic data (no network)
pytest -q                      # contract tests: weights pinned to METHODOLOGY.md
```

To produce a **real** leaderboard:

```bash
python -m hierarchy fetch --allow-missing   # try live sources (best-effort, soft-fail)
python -m hierarchy run                     # fetch + aggregate + render README/JSON/CSV
```

Automatic adapters currently cover LMArena and OpenRouter, plus Vals AI's independently evaluated
GPQA Diamond, MMLU-Pro, SWE-bench Verified, and LiveCodeBench tables. Vals marks these benchmark boards
archived because it no longer reruns saturated benchmarks on new model releases; each snapshot uses
the evaluation date published on the page (not the scrape date), and the standard 90-day cutoff
excludes older results. SWE-bench is restricted to the fixed `Mini-SWE-agent` harness. Source URLs,
evaluation dates, provider and harness qualifications are retained in the generated JSON and shown
in the dashboard's **Benchmark sources and qualifications** section.

Several metrics remain intentionally manual: LiveBench 2.0 no longer matches the historical metric
in these weights; SEAL's legacy average has no confirmed current endpoint; AIME/HMMT/MATH-500 are
fixed contests/sets without a single comparable live leaderboard; Terminal-Bench mixes agent
harnesses; and Tau² lacks a stable public machine-readable board. Each adapter/manual status is
reported by `python -m hierarchy validate` and `python -m hierarchy fetch` so a missing integration
is visible instead of silently skipped. Never scrape a page's retrieval date as benchmark freshness.

Any automatic source that fails (endpoint moved, schema changed) is logged and skipped — the
hierarchy is computed from valid, sufficiently fresh data only. The **guaranteed** input path is
[`data/manual/scores.csv`](data/manual/scores.csv): provide `benchmark,model,score,as_of,source,notes`
for a methodology-compatible score and the pipeline runs offline. Scrapers rot; manual drops never do.

## Weights at a glance (v1.1.0)

| Pillar | Weight | Benchmarks (global weights) |
|---|---|---|
| Human Preference | **0.35** | LMArena style-controlled Elo (0.25), OpenRouter token share (0.10) |
| Knowledge & Reasoning | **0.20** | GPQA Diamond (0.08), MMLU-Pro (0.06), LiveBench (0.03), Scale SEAL (0.03) |
| Math | **0.15** | AIME 2025 (0.08), HMMT Feb 2025 (0.04), MATH-500 (0.03) |
| Coding | **0.20** | SWE-bench Verified (0.10), LiveCodeBench (0.07), Terminal-Bench coding share (0.03) |
| Agentic | **0.10** | Tau²-bench (0.06), Terminal-Bench agentic share (0.04) |

Aggregation: Borda + clipped min-max normalization per benchmark → arithmetic mean within
pillars → **weighted geometric mean across pillars** (generalists win, specialists place) →
coverage penalty for missing data → 2,000-rep parametric bootstrap → tiers + pairwise
P(A ≻ B). Full spec: [METHODOLOGY.md](METHODOLOGY.md).

Key properties:

- **llmstat is a mirror, not a voice** — it republishes the same underlying benchmarks, so
  scoring it separately would double-count everything (METHODOLOGY.md §4). Use it to source
  manual drops.
- **Tiers, not fake precision** — same tier = statistically indistinguishable on current data.
- **Reproducible** — raw snapshots are committed; every output embeds a `config_hash`.

## Example output (synthetic demo data)

<!-- demo-leaderboard:start -->

> ⚠️ **Synthetic demo data** (see `demo/scores.csv`) — illustrates the output shape only. Run `python -m hierarchy run` for a real leaderboard.

Tier hierarchy (G-score 0-100) — generated 2026-11-01 19:12 UTC — SYNTHETIC DEMO DATA
────────────────────────────────────────────────────────────────
T1 │ claude opus 4.5 · gemini 3 pro · gpt 5.1
T2 │ grok 4.1
T3 │ deepseek v3.2
T4 │ kimi k2.5
T5 │ glm 4.7 · qwen3 max
T6 │ gpt 5 mini
T7 │ llama 4 maverick · minimax m2.5 · mistral large 3
────────────────────────────────────────────────────────────────
Same tier = statistically indistinguishable on current data (METHODOLOGY.md §11).

| # | Model | Tier | G | 95% CI | Hum. | Know. | Math | Code | Agent | Cov. | Flags |
|---|-------|------|---|--------|---|---|---|---|---|------|-------|
| 1 | `gpt 5.1` | T1 | **93.4** | 89.8–95.6 | 91 | 97 | 94 | 96 | 94 | 100% | – |
| 2 | `gemini 3 pro` | T1 | **93.2** | 90.5–95.0 | 96 | 97 | 100 | 89 | 84 | 100% | – |
| 3 | `claude opus 4.5` | T1 | **90.9** | 87.4–94.0 | 93 | 86 | 84 | 95 | 100 | 100% | – |
| 4 | `grok 4.1` | T2 | **71.3** | 67.0–75.7 | 69 | 75 | 75 | 70 | 71 | 100% | – |
| 5 | `deepseek v3.2` | T3 | **65.3** | 61.4–68.9 | 68 | 65 | 69 | 65 | 59 | 100% | – |
| 6 | `kimi k2.5` | T4 | **59.1** | 54.6–63.8 | 56 | 56 | 61 | 69 | 58 | 100% | – |
| 7 | `glm 4.7` | T5 | **50.5** | 46.0–55.6 | 50 | 46 | 53 | 53 | 48 | 100% | – |
| 8 | `qwen3 max` | T5 | **47.8** | 43.6–52.0 | 50 | 45 | 48 | 46 | 42 | 100% | – |
| 9 | `gpt 5 mini` | T6 | **39.6** | 36.3–42.8 | 52 | 32 | 39 | 34 | 33 | 100% | – |
| 10 | `minimax m2.5` | T7 | **29.8** | 25.9–34.3 | 32 | 22 | 34 | 33 | 26 | 96% | – |
| 11 | `mistral large 3` | T7 | **12.4** | 8.8–15.3 | 14 | 11 | 13 | 11 | 11 | 94% | – |
| 12 | `llama 4 maverick` | T7 | **5.0** | 5.0–7.7 | 5 | 5 | 5 | 5 | 5 | 100% | – |

<!-- demo-leaderboard:end -->

*( regenerate with `python -m hierarchy demo` — numbers are synthetic, see
`demo/DATA_IS_SYNTHETIC.md` )*

## Explore the leaderboard

[Open the Model Atlas dashboard](https://nan0pk.github.io/model-hierarchy/dashboard/) (published via GitHub Pages). It displays only eligible live results by default; if none are available, it explains the eligibility gap rather than presenting demo scores as real. Use `?demo=1` to opt into the clearly labeled synthetic demo. GitHub READMEs cannot run or embed the interactive dashboard itself, so the image below is a static preview; use the link for live controls. Serve the repository locally (e.g. `python -m http.server 8000`) and open `/dashboard/` to search models, inspect published confidence intervals, and explore pillar reweighting. Personalized rankings are exploratory; they do not recompute statistical tiers or bootstrap intervals. The dashboard reads the published JSON files without a backend.

> **Preview uses synthetic demo scores** — illustrative only, not the live ranking.
>
> ![Model Atlas dashboard preview with synthetic example rankings](dashboard/preview.svg)

Pairwise tier separations and dominance claims use Benjamini–Hochberg-adjusted bootstrap tail
probabilities to reduce false discoveries across comparisons. This remains a bootstrap heuristic,
not an analytic test or proof of model superiority.

## Live leaderboard

<!-- leaderboard:start -->

Tier hierarchy (G-score 0-100) — generated 2026-11-03 19:36 UTC
────────────────────────────────────────────────────────────────
T1 │ claude opus 4.7 · claude opus 4.8 · gemini 3.1 pro preview · muse spark 1.1
T2 │ gemini 3 pro · gpt 5.5 · grok 4.5
T3 │ claude sonnet 4.6 · gemini 3 flash · glm 5.3 flash · kimi k2.6
T4 │ gemini 3.5 flash lite · glm 5 · glm 5.1 · mimo v2.5 pro
T5 │ gpt 5.1 · grok 4.3 · inkling · minimax m3
T6 │ glm 4.7
────────────────────────────────────────────────────────────────
Same tier = statistically indistinguishable on current data (METHODOLOGY.md §11).

| # | Model | Tier | G | 95% CI | Hum. | Know. | Math | Code | Agent | Cov. | Flags |
|---|-------|------|---|--------|---|---|---|---|---|------|-------|
| 1 | `gemini 3.1 pro preview` | T1 | **73.7** | 68.2–78.0 | 88 | 100 | – | 75 | – | 56% | – |
| 2 | `claude opus 4.7` | T1 | **70.8** | 63.7–77.1 | 100 | 76 | – | 64 | – | 56% | – |
| 3 | `muse spark 1.1` | T1 | **69.7** | 62.0–76.8 | 94 | 73 | – | 71 | – | 56% | – |
| 4 | `claude opus 4.8` | T1 | **66.0** | 59.3–71.8 | 65 | 86 | – | 97 | – | 56% | – |
| 5 | `gemini 3 pro` | T2 | **64.3** | 56.3–71.3 | 85 | 87 | – | 57 | – | 56% | – |
| 6 | `gpt 5.5` | T2 | **61.6** | 54.6–68.2 | 69 | 83 | – | 69 | – | 56% | – |
| 7 | `grok 4.5` | T2 | **57.0** | 50.6–63.4 | 49 | 88 | – | 90 | – | 56% | – |
| 8 | `glm 5.3 flash` | T3 | **48.2** | 39.2–55.8 | 63 | 33 | – | 60 | – | 66% | – |
| 9 | `gemini 3 flash` | T3 | **47.9** | 39.5–55.6 | 62 | 58 | – | 45 | – | 56% | – |
| 10 | `kimi k2.6` | T3 | **41.6** | 34.7–49.0 | 41 | 57 | – | 57 | – | 56% | – |
| 11 | `claude sonnet 4.6` | T3 | **41.2** | 31.7–48.8 | 61 | 38 | – | 39 | – | 56% | – |
| 12 | `glm 5.1` | T4 | **33.4** | 24.5–41.0 | 49 | 32 | – | 31 | – | 56% | – |
| 13 | `mimo v2.5 pro` | T4 | **23.0** | 16.0–32.6 | 51 | 6 | – | 17 | – | 56% | – |
| 14 | `gemini 3.5 flash lite` | T4 | **22.0** | 14.7–29.2 | 31 | 18 | – | 18 | – | 56% | – |
| 15 | `glm 5` | T4 | **21.0** | 13.1–28.7 | 34 | 18 | – | 15 | – | 56% | – |
| 16 | `inkling` | T5 | **17.8** | 12.5–26.1 | 7 | 40 | – | 57 | – | 56% | – |
| 17 | `grok 4.3` | T5 | **15.3** | 11.1–23.1 | 6 | 53 | – | 26 | – | 56% | – |
| 18 | `minimax m3` | T5 | **13.3** | 10.7–18.8 | 5 | 52 | – | 29 | – | 56% | – |
| 19 | `gpt 5.1` | T5 | **12.4** | 9.6–16.7 | 5 | 38 | – | 35 | – | 56% | – |
| 20 | `glm 4.7` | T6 | **6.6** | 4.3–11.4 | 5 | 5 | – | 14 | – | 56% | – |

*Stale (>14d): gpqa_diamond, livecodebench, mmlu_pro, swebench_verified*

*Unranked (insufficient data, §5): `chatgpt 4o latest (20250326)`, `claude 3.5 haiku latest`, `claude 3.5 sonnet latest`, `claude 3.7 sonnet (nonthinking)`, `claude 3.7 sonnet (thinking)`, `claude fable 5`, `claude fable 5 (high)`, `claude fable 5.1`, `claude fable 5.1 (max)`, `claude haiku 4.5 (thinking)`, `claude opus 4 (nonthinking)`, `claude opus 4 (thinking)`, `claude opus 4.1 (20250805)`, `claude opus 4.1 (nonthinking)`, `claude opus 4.1 (thinking 16k, 20250805)` … and 207 more in `output/leaderboard.json`*

<!-- leaderboard:end -->

## Repo layout

```
METHODOLOGY.md            normative spec: weights, formulas, limitations ledger
config/weights.yaml       the authoritative numbers (tests pin them)
config/sources.yaml       where data comes from + per-source fallback notes
hierarchy/                the pipeline (normalize → aggregate → tiers → render)
hierarchy/fetch/          best-effort adapters (LMArena mirror API, OpenRouter, generic JSON)
data/manual/scores.csv    guaranteed manual input path
data/raw/                 committed daily snapshots (reproducibility)
output/                   leaderboard.json / leaderboard.csv
tests/                    contracts from METHODOLOGY.md
.github/workflows/        daily cron job (fetch → aggregate → render → commit)
```

## Daily automation

`.github/workflows/daily.yml` runs at 06:00 UTC: fetch → aggregate → render → auto-commit if
anything changed. Enable Actions on your fork/repo; on public repos this is free. No secrets
are required for v1 (all sources are public pages).

## Roadmap

- `--method pca` report: data-driven g-factor alongside (never replacing) the declared weights
- provenance tagging: orchestrator-run vs vendor-reported scores (credibility multiplier)
- multimodal pillar (v2 candidate)
- GitHub Pages front-end over `output/leaderboard.json`

## Disclaimer

Aggregating benchmarks measures *benchmarks and votes*, not truth. Read the
[limitations ledger](METHODOLOGY.md#13-bias-and-limitations-ledger) before citing any output.
This project is independent of LMArena, OpenRouter, Scale AI, and all benchmark operators;
data belongs to its respective owners and is used under their public terms.

## License

MIT — see [LICENSE](LICENSE).

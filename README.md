# model-hierarchy

**One number per model, every day: a reality-anchored tier hierarchy of frontier models,
aggregated from LMArena, OpenRouter usage, GPQA, LiveBench, SEAL, AIME, HMMT, SWE-bench
Verified, LiveCodeBench, Terminal-Bench and Tau²-bench.**

> Which models are *comprehensively* better than the rest right now — not per-benchmark noise,
> not vibes: a declared-weight aggregate over 5 capability pillars, with confidence intervals,
> tier groupings, and pairwise "confidently better" probabilities.

📖 **The methodology — every weight, every formula, every tradeoff — is specified in
[METHODOLOGY.md](METHODOLOGY.md).** This README shows you how to run it.

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

Any source that fails (endpoint moved, HTML changed) is logged and skipped — the hierarchy is
computed from everything that succeeded, with staleness flags. The **guaranteed** input path is
[`data/manual/scores.csv`](data/manual/scores.csv): paste numbers from llmstat or any
leaderboard page (`benchmark,model,score,as_of,source,notes`) and the full pipeline runs
offline. Scrapers rot; manual drops never do.

## Weights at a glance (v1.0.0)

| Pillar | Weight | Benchmarks (global weights) |
|---|---|---|
| Human Preference | **0.35** | LMArena style-controlled Elo (0.25), OpenRouter token share (0.10) |
| Knowledge & Reasoning | **0.20** | GPQA Diamond (0.08), LiveBench (0.06), Scale SEAL (0.06) |
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

Tier hierarchy (G-score 0-100) — generated 2026-11-01 18:30 UTC — SYNTHETIC DEMO DATA
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
| 1 | `gpt 5.1` | T1 | **93.3** | 90.0–95.7 | 91 | 97 | 94 | 96 | 94 | 100% | – |
| 2 | `gemini 3 pro` | T1 | **93.2** | 90.3–95.0 | 96 | 97 | 100 | 89 | 84 | 100% | – |
| 3 | `claude opus 4.5` | T1 | **90.9** | 87.4–93.9 | 93 | 86 | 84 | 95 | 100 | 100% | – |
| 4 | `grok 4.1` | T2 | **71.2** | 67.2–75.4 | 69 | 75 | 75 | 70 | 71 | 100% | – |
| 5 | `deepseek v3.2` | T3 | **65.3** | 61.8–68.9 | 68 | 65 | 69 | 65 | 59 | 100% | – |
| 6 | `kimi k2.5` | T4 | **59.1** | 54.8–64.0 | 56 | 56 | 61 | 69 | 58 | 100% | – |
| 7 | `glm 4.7` | T5 | **50.5** | 45.9–55.9 | 50 | 46 | 53 | 53 | 48 | 100% | – |
| 8 | `qwen3 max` | T5 | **47.6** | 43.7–52.0 | 50 | 45 | 48 | 46 | 42 | 100% | – |
| 9 | `gpt 5 mini` | T6 | **39.6** | 36.3–42.8 | 52 | 32 | 39 | 34 | 33 | 100% | – |
| 10 | `minimax m2.5` | T7 | **29.8** | 25.8–34.6 | 32 | 22 | 34 | 33 | 26 | 96% | – |
| 11 | `mistral large 3` | T7 | **12.3** | 8.8–15.4 | 14 | 11 | 13 | 11 | 11 | 94% | – |
| 12 | `llama 4 maverick` | T7 | **5.0** | 5.0–7.6 | 5 | 5 | 5 | 5 | 5 | 100% | – |

<!-- demo-leaderboard:end -->

*( regenerate with `python -m hierarchy demo` — numbers are synthetic, see
`demo/DATA_IS_SYNTHETIC.md` )*

## Live leaderboard

<!-- leaderboard:start -->

Tier hierarchy (G-score 0-100) — generated 2026-11-01 18:30 UTC
────────────────────────────────────────────────────────────────
────────────────────────────────────────────────────────────────
Same tier = statistically indistinguishable on current data (METHODOLOGY.md §11).

| # | Model | Tier | G | 95% CI | Hum. | Know. | Math | Code | Agent | Cov. | Flags |
|---|-------|------|---|--------|---|---|---|---|---|------|-------|

*Unranked (insufficient data, §5): `chatgpt 4o latest (20250326)`, `claude fable 5 (high)`, `claude fable 5.1 (max)`, `claude opus 4.1 (20250805)`, `claude opus 4.1 (thinking 16k, 20250805)`, `claude opus 4.5 (20251101)`, `claude opus 4.5 (high, 32k, 20251101)`, `claude opus 4.6`, `claude opus 4.6 (high)`, `claude opus 4.7`, `claude opus 4.7 (high)`, `claude opus 4.8`, `claude opus 4.8 (high)`, `claude opus 5 (high)`, `claude opus 5 (max)` … and 93 more in `output/leaderboard.json`*

*No tiers yet — tier assignment requires data from at least 3 pillars (§5). Fill `data/manual/scores.csv` or wire more sources in `config/sources.yaml`.*

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

# Model Hierarchy — Aggregation Methodology

**Version 1.0.0** · This document is the normative specification of how this repo turns a dozen
public benchmarks into one daily, reality-anchored hierarchy of frontier models.
Every number in the pipeline lives in [`config/weights.yaml`](config/weights.yaml) and must stay
in sync with this document (enforced by `tests/test_weights.py`).

---

## Contents

1. [Purpose](#1-purpose)
2. [Design principles](#2-design-principles)
3. [Pillar architecture](#3-pillar-architecture)
4. [Benchmark registry and global weights](#4-benchmark-registry-and-global-weights)
5. [Cohort and eligibility](#5-cohort-and-eligibility)
6. [Normalization](#6-normalization)
7. [Within-pillar aggregation](#7-within-pillar-aggregation)
8. [Cross-pillar aggregation](#8-cross-pillar-aggregation)
9. [Coverage penalty and the final score](#9-coverage-penalty-and-the-final-score)
10. [Uncertainty: parametric bootstrap](#10-uncertainty-parametric-bootstrap)
11. [Tiers: the hierarchy output](#11-tiers-the-hierarchy-output)
12. [Freshness and daily operation](#12-freshness-and-daily-operation)
13. [Bias and limitations ledger](#13-bias-and-limitations-ledger)
14. [Alternatives considered and rejected](#14-alternatives-considered-and-rejected)
15. [Governance and versioning](#15-governance-and-versioning)
16. [Reference implementation map](#16-reference-implementation-map)

---

## 1. Purpose

Answer one question, every day, with numbers:

> **"Which models are comprehensively better than the rest right now?"**

The premise of this project is that at the top of the leaderboard there exist *generalists* —
models smart enough to be good at everything — and that a cross-benchmark aggregate should make
that dominance visible instead of drowning it in a dozen contradictory single-purpose rankings.

The hierarchy is **reality-anchored**: the largest single weight goes to what humans actually
prefer (LMArena) and what they actually pay to use (OpenRouter token share), then validated by
contamination-resistant capability benchmarks. It is **noise-aware**: because daily Elo wiggles
by more than real gaps between neighbours, the output is a *tier ladder with confidence
intervals and pairwise probabilities*, not a brittle #1/#2/#3.

What this is **not**:

- Not a per-task model selector. If you only need the best coding agent, read SWE-bench.
- Not a vendor eval or a marketing index. All inputs are public, all weights are declared, all
  math is in this repo.
- Not multimodal. v1 covers text/reasoning/agentic ability only (see §13).

---

## 2. Design principles

1. **Reality anchor.** The biggest single voice is human preference and real-world usage.
   Benchmarks validate that preference is not just style; preference keeps benchmarks honest.
2. **Balance.** Aggregation across capability pillars is *geometric*, so one-dimensional
   excellence cannot buy the top spot. Generalists win; specialists place.
3. **Robustness.** Every benchmark score passes through a Borda + clipped min-max blend, so a
   single inflated or broken number cannot dominate. Elo is min-max only (interval scale).
4. **Honesty about missing data.** No imputation, ever. A model missing benchmarks keeps its
   other scores but pays an explicit coverage penalty and carries a visible flag.
5. **Noise-awareness.** Every headline number ships with a bootstrap 95% CI and pairwise
   P(A ≻ B) probabilities. "Better" only gets claimed when separation beats the noise.
6. **Reproducibility.** Raw snapshots are committed, weights are versioned, and every output
   embeds a `config_hash` so any historical ranking can be recomputed exactly.

---

## 3. Pillar architecture

Benchmarks are grouped into five **pillars** so that no single capability domain can dominate
the aggregate. Pillar weights are the top-level knobs of the methodology:

| Pillar | ID | Weight | What it captures | Why this weight |
|---|---|---|---|---|
| Human Preference | `human_preference` | **0.35** | What people actually prefer (LMArena, style-controlled) and actually use (OpenRouter token share) | The question being answered is *subjective superiority*. Preference data is the only signal that directly measures it, so it gets the largest share — but not a majority, so benchmarks still keep it honest. |
| Knowledge & Reasoning | `knowledge_reasoning` | **0.20** | Hard science/knowledge reasoning (GPQA Diamond), contamination-resistant general ability (LiveBench), private held-out evals (Scale SEAL) | Broadest proxy for general intelligence; three independent measurement philosophies. |
| Mathematical Reasoning | `math` | **0.15** | AIME 2025, HMMT Feb 2025, MATH-500 | Frontier math is a strong g-factor signal, but the top of AIME is saturating (less discriminative power per year), so it gets slightly less than coding. |
| Coding & Engineering | `coding` | **0.20** | SWE-bench Verified (real-repo bug fixes), LiveCodeBench (fresh problems), Terminal-Bench (coding share) | Coding is both a capability and a proxy for agentic economic value; among benchmarks it currently separates the top models most cleanly. |
| Agentic & Tool Use | `agentic` | **0.10** | Tau²-bench (multi-domain tool use), Terminal-Bench (agentic share) | The agentic frontier matters and is under-measured: few orchestrator-run sources with consistent frontier coverage. Conservative weight until coverage thickens (tracked in §13). |

**Sum = 1.00.** Weights are intentionally round and few, so the hierarchy is auditable at a
glance and debates about methodology happen at the pillar level, not in the third decimal.

---

## 4. Benchmark registry and global weights

Each benchmark carries a **global effective weight** — its share of the final score. This table
*is* the methodology's answer to "how do arena.ai, llmstat and the other benchmarks work with
each other":

| # | Benchmark | Pillar | Global weight | Normalization | Contamination defence | Role / notes |
|---|---|---|---|---|---|---|
| 1 | LMArena Elo (style-controlled) | Human Preference | **0.25** | `elo` | n/a (human votes) | Anchor signal. Millions of pairwise human votes, Bradley-Terry Elo. Style-controlled variant strips verbosity/markdown bias; raw Elo used only as fallback. |
| 2 | OpenRouter token share | Human Preference | **0.10** | `log_share` | n/a (revealed preference) | What people route real work through, at real cost. Log-transformed because share is heavy-tailed and price-skewed. |
| 3 | GPQA Diamond | Knowledge & Reasoning | **0.08** | `blend` | Hard, recent, expert-written | Diamond subset of graduate-level science MCQ. |
| 4 | LiveBench (overall) | Knowledge & Reasoning | **0.06** | `blend` | Monthly-refreshed questions | Contamination-resistant by design; orchestrator-run, not vendor-reported. |
| 5 | Scale SEAL (average) | Knowledge & Reasoning | **0.06** | `blend` | Private held-out tasks | Contamination-proof: questions are not public. |
| 6 | AIME 2025 (avg, no tools) | Math | **0.08** | `blend` | Post-cutoff competition | Frontier math; averaging across the 2025 sets tames single-sitting variance. |
| 7 | HMMT Feb 2025 | Math | **0.04** | `blend` | Post-cutoff competition | Brutally hard, spreads the top better than AIME. |
| 8 | MATH-500 | Math | **0.03** | `blend` | Legacy (saturating) | Kept as a historical anchor; near-saturation is why its weight is small. |
| 9 | SWE-bench Verified | Coding | **0.10** | `blend` | Human-validated post-cutoff tasks | Real GitHub issues, agentic pipeline; the single most consequential capability benchmark. |
| 10 | LiveCodeBench (current) | Coding | **0.07** | `blend` | Rolling fresh problems | Contamination-resistant competitive coding. |
| 11 | Terminal-Bench — coding share | Coding | **0.03** | `blend` | Post-cutoff tasks | Terminal-native agent tasks; **hybrid benchmark** (see note). |
| 12 | Tau²-bench (domain avg) | Agentic | **0.06** | `blend` | Simulated customers/tools | Tool-use with verifiable success states across domains. |
| 13 | Terminal-Bench — agentic share | Agentic | **0.04** | `blend` | Post-cutoff tasks | Same data as #11, agentic lens; **hybrid benchmark** (see note). |
| | **Total** | | **1.00** | | | |

**Hybrid benchmarks.** Terminal-Bench measures coding *and* agentic skill in one number, so it
carries a split weight: 0.03 via the Coding pillar and 0.04 via the Agentic pillar (total 0.07).
Splitting (instead of duplicating) keeps the global sum at exactly 1.00 and keeps each pillar's
internal logic clean.

**Where llmstat fits.** llmstat is itself an *aggregator* of vendor- and orchestrator-reported
benchmark scores — it republishes the same underlying numbers as rows 3–11. Treating it as an
independent 14th voice would double-count every benchmark it mirrors. It is therefore used as a
**data mirror/fallback fetcher** (and a convenient place to hand-copy numbers into
`data/manual/scores.csv` from), never as a separate scored source.

**Where the Artificial Analysis Intelligence Index fits.** AA's index is an excellent aggregate,
but it already contains GPQA and several other registered benchmarks, so enabling it as a scored
voice double-counts its components. It ships as an **optional, off-by-default** entry
(`artanalysis_index` in `config/sources.yaml`) for users who want to swap P2 wholesale for one
number; document the substitution in any output you publish if you do.

**Why these sources and not others.** MMLU-Pro, GSM8K, HumanEval, and MBPP are excluded from the
default registry: heavily contaminated and/or saturated at the frontier, and their residual
signal is already carried by their modern successors (LiveBench, AIME/HMMT, LiveCodeBench,
SWE-bench Verified). They can be added via config without code changes — the registry is data,
not code.

---

## 5. Cohort and eligibility

**Cohort.** A model enters the cohort for a given day if it appears in the day's snapshots of at
least 3 pillars and at least 5 registered benchmarks. Normalization is computed **within the
cohort**, so adding one weak model changes other models' min-max/borda values — this is
intentional (rankings are relative statements) and why the cohort rule must be stable and
documented, not tuned per day.

**Eligibility flags (visible in every output):**

- `no_preference_signal` — the model is absent from both LMArena and OpenRouter. It is still
  scored and ranked (benchmarks are complete enough), but flagged: its P1 pillar is empty and
  its coverage penalty applies. At the frontier this is rare.
- `insufficient_data` — fewer than 3 pillars or 5 benchmarks. The model is listed in a separate
  *unranked* section with descriptive stats only; it does not enter tiers.
- `stale` — see §12.

**Survivorship bias note.** The cohort rule admits any model with public coverage, including
open-weight ones; there is deliberately no "major labs only" filter. The coverage penalty, not
gatekeeping, handles thin data.

---

## 6. Normalization

Benchmarks report Elo (~1200–1500), percentages (0–100), and shares (0–100%). Before anything is
combined, every benchmark's raw scores are mapped to v ∈ [0.02, 1.00] where 1 = best in cohort.
Three transforms are used, chosen per benchmark in `weights.yaml`:

### 6.1 Borda rank — robustness

```
B_b(m) = (N_b − rank_b(m)) / (N_b − 1)
```

Ties get average ranks. Borda is immune to scale, outliers, and — crucially — to *magnitude
inflation*: if a contaminated benchmark lets a model post 99 instead of 89, its Borda value
moves only by however many neighbours it leapfrogs, not by the fake 10 points.

### 6.2 Clipped min-max — magnitude

Scores are clipped to the cohort's 5th/95th percentiles, then scaled to [0, 1]:

```
M_b(m) = (clip(s) − p5) / (p95 − p5)
```

This preserves the information Borda throws away — *how far ahead* the leader is (a 10-Elo-gap
leader and a 100-Elo-gap leader are both "rank 1", but not equally better). Clipping tames
outliers so one degenerate score cannot stretch the axis for everyone else.

### 6.3 The default blend

```
v_b(m) = 0.5 · B_b(m) + 0.5 · M_b(m)
```

Half rank, half magnitude: robust *and* informative. Pure Borda loses "GPT-x is 8 points clear";
pure min-max is fragile. The blend is the deliberate compromise.

### 6.4 Special cases

- **LMArena Elo (`elo` mode):** min-max only, no Borda, no percentile clipping. Elo differences
  are approximately interval-scaled and peer-reviewed — ranking them wastes the scale. Where a
  model has a published CI, it feeds the noise model (§10).
- **OpenRouter share (`log_share` mode):** min-max over `log10(share + ε)`. Token share is
  heavy-tailed and price-skewed (cheap models get volume); the log keeps the #1-vs-#2 gap
  meaningful without letting a 10× volume leader obliterate everything.
- **Lower-is-better benchmarks:** supported via `direction: lower` (negate before normalizing);
  none are registered in v1 but the path exists so latency/cost pillars can be added later.

### 6.5 Floors

Normalized values are floored at **0.02** and pillar scores at **0.05** before exponentiation.
The aggregate is a geometric mean (§8); an unfloored zero anywhere would zero the whole product,
which would be absurd (no model is *zero* at math). Floors only bind in pathological cases.

---

## 7. Within-pillar aggregation

Within a pillar, a model's score is a **coverage-renormalized weighted arithmetic mean** of the
benchmarks it has data for:

```
P_p(m) = Σ_{b ∈ p, present} (w_b / W_p,present) · v_b(m)
```

where `w_b` is the benchmark's global weight and `W_p,present` renormalizes over the benchmarks
the model actually has. Missing one benchmark in a pillar does not zero the pillar — the other
voices speak, and the absence is paid for exactly once, in §9.

**Why arithmetic within a pillar:** benchmarks inside a pillar measure overlapping facets of the
same capability (they are *substitutes*). If SEAL is missing, GPQA and LiveBench genuinely
partially cover for it. Arithmetic means are the correct aggregator for substitutes.

---

## 8. Cross-pillar aggregation

Across pillars, the aggregate is a **weighted geometric mean** with weight redistribution over
present pillars:

```
g(m) = Π_{p present}  max(P_p(m), 0.05) ^ (W_p / Σ_{p' present} W_{p'})
```

**Why geometric across pillars:** capabilities are *complements*, not substitutes. Brilliance at
math does not partially cover for being disliked by humans or useless at agentic tasks. The
geometric mean encodes the project's founding claim: at the top, the models that dominate are
the ones with no weak pillar. A worked example (two pillars, equal weights):

| Model | P1 | P2 | Arithmetic mean | Geometric mean |
|---|---|---|---|---|
| Generalist | 0.92 | 0.92 | 0.920 | **0.920** |
| Specialist | 1.00 | 0.84 | **0.920** — a perfect tie | 0.917 — strictly behind |
| Very spiky | 1.00 | 0.70 | 0.850 | 0.837 — the deficit compounds |

The specialist row has the *same arithmetic mean* as the generalist: under an arithmetic
aggregate, being ~9% worse on P2 costs nothing as long as P1 compensates. Under the geometric
aggregate, compensation is impossible — the deficit multiplies. A spiky profile can still win,
but only by being strictly better on average, and the spikier it is the larger that margin
must be. That is the claim "at the top, the winners have no weak pillar", made mathematical.

**Weight redistribution:** a model missing an entire pillar has the remaining pillar weights
renormalized, so its geometric mean is computed over what exists. This is not a free pass —
missing pillars are paid for next.

---

## 9. Coverage penalty and the final score

Missing data is never imputed; it is *charged for*. Define coverage as the sum of global weights
of benchmarks the model has data for (since weights sum to 1, this is exact):

```
C(m)   = Σ_{b present} w_b                  ∈ [0, 1]
G(m)   = g(m) × (0.70 + 0.30 · C(m))        ∈ [0, 100] after ×100
```

A fully covered model is untouched (multiplier = 1.00). Example haircuts:

| Situation | C | Multiplier |
|---|---|---|
| All 13 benchmarks | 1.00 | 1.00 |
| Missing all of P5 (0.10) | 0.90 | 0.97 |
| Missing LMArena (0.25) | 0.75 | 0.925 |
| Missing P1 entirely (0.35) | 0.65 | 0.895 |
| Half the registry | ~0.50 | 0.85 |

The penalty is deliberately linear and modest — strong enough that a 3-pillar specialist cannot
top the ladder on partial data, weak enough that a genuinely excellent model with one missing
report isn't buried. Both constants (`base 0.70`, `span 0.30`) are config knobs with the
constraint `base + span = 1.0` enforced by tests.

**Reported score.** The headline number is `G × 100`, called simply the **G-score (0–100)**.

---

## 10. Uncertainty: parametric bootstrap

Point estimates are easy; honest error bars are the product. For each model × benchmark pair we
attach a noise scale σ in *raw* units:

- If the source publishes a 95% CI (LMArena does, per model): `σ = (hi − lo) / 3.92`.
- Otherwise the registry default for that benchmark (`noise_raw`: 8 Elo points for Arena, 1.5
  points for percentage benchmarks, 0.4 pp for OpenRouter share).

Then repeat **2,000 times**: perturb every raw score with independent `N(0, σ)`, re-run the
*entire* pipeline (re-normalize, re-aggregate, re-penalize — normalization cohorts shift under
noise, and that instability belongs in the error bar), and collect the distribution of G.

Outputs per model: **median G** and the **2.5 / 97.5 percentiles**. Outputs per pair:
**P(A ≻ B)** = fraction of draws where A's G exceeds B's G.

**"Confidently better"** is defined as `P(A ≻ B) ≥ 0.95`. Every such directed pair is published
in the `dominance` list of `output/leaderboard.json` — this is the literal, defensible answer to
"which models are subjectively better than the rest", with probabilities instead of vibes.

The bootstrap is parametric and first-order; it models measurement noise, not systematic bias
(polling demographics, contamination shifts). Systematic risks are catalogued in §13 and are
*not* assumed away.

---

## 11. Tiers: the hierarchy output

Sorting by median G would fake precision: daily Elo moves ±5–10 points, which moves G by more
than the gaps between neighbours. The hierarchy is therefore emitted as **tiers**, built greedily
from the top:

1. Sort models by median G (descending). The first model anchors Tier 1.
2. Walk down the list. A **tier boundary** is placed between the current tier's *anchor* and the
   next model when they are *separated*: either their bootstrap 95% CIs are disjoint, or
   `P(anchor ≻ next) ≥ 0.95`.
3. A model that is not separated from the anchor joins the tier (indistinguishable from its top
   on current data).
4. At most **7 tiers**; anything deeper collapses into the last tier.

Interpretation contract, stated on every output:

> Models in the same tier are **statistically indistinguishable** on current data. Their printed
> order within a tier is alphabetical, not a ranking.

Tier labels are neutral (`T1…T7`) rather than S/A/B to avoid implying letter-grade quality gaps
the data cannot support. The rendered output is a tree:

```
T1 │ gemini-3-pro · claude-opus-4.5 · gpt-5.1        ← same tier = same tier, not #1/#2/#3
T2 │ grok-4.1
T3 │ deepseek-v3.2 · kimi-k2.5 · glm-4.7
```

alongside the full table (G-score, CI, pillar subscores, coverage, flags) in
`output/leaderboard.json`, `output/leaderboard.csv`, and the README.

---

## 12. Freshness and daily operation

- Every snapshot records `as_of` (the date the *source* last updated, not the fetch date).
- **Staleness policy:** a benchmark whose newest snapshot is > 14 days old is flagged `stale`
  in output; > 120 days old it is excluded from aggregation (kept in the JSON with
  `excluded_stale: true`). A model's ability doesn't decay — but comparability does, once the
  field has moved.
- **Daily job** (`.github/workflows/daily.yml`, 06:00 UTC): fetch → aggregate → render →
  auto-commit if anything changed. Any single source failing (endpoint moved, HTML changed,
  Cloudflare) is logged and non-fatal: the day's hierarchy is computed from everything that
  succeeded, with staleness flags telling the reader exactly what fell behind.
- **Guaranteed fallback:** `data/manual/scores.csv`. One row per number
  (`benchmark,model,score,as_of,source`) — paste from llmstat or any leaderboard page and the
  full pipeline runs offline. Scrapers rot; manual drops never do. The fetch adapters are
  convenience, the CSV is the contract.
- **Name reconciliation (§12.1):** sources disagree on names — Arena reports display names
  ("Claude Opus 5.5 (High)"), OpenRouter reports slugs ("anthropic/claude-opus-5.5"), benchmark
  pages report vendor names. Matching is **exact after canonicalization** (lowercase, drop the
  provider prefix, unify separators) plus a user-maintained alias table
  (`config/models.yaml`). Fuzzy matching is deliberately absent: a silent wrong merge corrupts
  the hierarchy, while an unmatched name merely shows up in the reconciliation report that
  every `leaderboard.json` carries (`name_reconciliation`). Variant suffixes like "(High)" are
  real Arena entries and are never collapsed into the base model.
- **Reproducibility:** raw snapshots are committed to the repo; every output embeds
  `config_hash` (SHA-256 of the canonicalized config). Any historical leaderboard can be
  recomputed bit-for-bit from the tree.

---

## 13. Bias and limitations ledger

| # | Bias / limitation | Mitigation in v1 | Residual risk |
|---|---|---|---|
| 1 | Arena style effects (verbosity, markdown, confident tone win votes) | Style-controlled Elo is the registered default; raw Elo only as fallback | Style control is itself a model — imperfect |
| 2 | Arena voter demographics skew English/consumer tasks | P1 capped at 0.35; benchmarks counterweight | Non-English & professional workflows underrepresented |
| 3 | Arena gaming / targeted prompting | CI-based tiers make small Elo moves invisible | Organized manipulation would still shift tiers |
| 4 | Benchmark contamination | Registry prefers Live*/SEAL/SWE-bench Verified/post-cutoff sets; MMLU/GSM8K/HumanEval excluded | Vendor-reported rows (mirrored via llmstat) can still be cherry-picked — prefer orchestrator-run sources when both exist |
| 5 | Vendor-reported vs orchestrator-run scores | `source` column in manual CSV; orchestrator-run preferred in fetch adapters | Mixing provenance remains possible; audit `source` before citing |
| 6 | OpenRouter share is price-skewed (cheap ≠ better) | Only 0.10 global weight, log-transformed, capped inside P1 at 0.10/0.35 | Usage measures value-for-money, not pure quality |
| 7 | Thin agentic coverage (few consistent reporters) | Agentic pillar weighted 0.10 with explicit rationale | Agentic ability is the fastest-moving axis and likely under-weighted; revisit at v1.1 |
| 8 | Text-only | Declared out of scope for v1 | Multimodal hierarchy is a v2 candidate |
| 9 | PCA/g-factor weights would drift daily | Fixed, documented weights; comparability across days prioritized | Weights are opinionated — governed per §15 |
| 10 | Double counting (aggregates-of-aggregates) | llmstat = mirror only; AA index off by default with substitution rule documented | A user enabling both AA and its components double-counts — config warns |
| 11 | Cohort-definition sensitivity (min-max depends on who's in) | Cohort rule fixed in §5, tests pin it | Sudden entrants shift normalized scores by design |
| 12 | Hybrid benchmarks span pillars | Terminal-Bench split 0.03/0.04, documented once | Other hybrids (e.g. browsebench-class) need the same treatment |

---

## 14. Alternatives considered and rejected (for v1)

- **Pure Borda across all benchmarks.** Maximally robust, but discards *how much* better the
  leader is — and the question being answered is exactly about magnitude of dominance. Kept as
  50% of the per-benchmark blend instead.
- **Global arithmetic mean of normalized scores.** Cannot distinguish a balanced profile from
  a spiky one with the same mean (§8): one strong pillar buys the top spot; contradicts the
  project's thesis.
- **Merging everything into one Elo.** Requires cross-benchmark comparability assumptions that
  don't hold (an Arena Elo point ≠ a benchmark percentage point).
- **PCA / g-factor extraction** (à la Sam Paech's Misc AI index). Statistically elegant — the
  first principal component *is* a data-driven "smart at everything" axis — but component
  loadings drift as the benchmark mix changes, breaking day-over-day comparability, and the
  weights stop being explainable. Planned as an optional `--method pca` report alongside (never
  replacing) the declared-weight G-score.
- **Adopting one existing mega-index** (e.g. Artificial Analysis alone). Cedes the weight
  decisions to a third party; this repo exists to make them explicit and tunable.

---

## 15. Governance and versioning

- The methodology is semver'd (`1.0.0`). Any change to a weight, pillar, normalization mode, or
  structural formula bumps the version, gets a changelog line below, and updates
  `tests/test_weights.py` in the same commit — CI fails otherwise.
- Weight changes must state the pillar-level rationale in the PR description (which real-world
  question changed?). Cosmetic changes (labels, rendering) don't bump.
- Every published artifact embeds `weights_version` and `config_hash`, so a ranking made under
  v1.0.0 is never silently reinterpreted under v1.1.0.

**Changelog**

- `1.0.0` (2026-11-02) — initial public methodology: 5 pillars, 13 registered benchmark weights
  summing to 1.00, two-level geometric aggregation, 0.70/0.30 coverage penalty, 2,000-rep
  parametric bootstrap, 7-tier anchored separation rule.

---

## 16. Reference implementation map

| Methodology section | Code |
|---|---|
| §4 registry & weights | `config/weights.yaml`, `config/sources.yaml`, `hierarchy/config.py` |
| §5 cohort & eligibility | `hierarchy/aggregate.py` (`pillar_and_g`) |
| §6 normalization | `hierarchy/normalize.py` |
| §7–§9 aggregation & penalty | `hierarchy/aggregate.py` |
| §10 bootstrap | `hierarchy/aggregate.py` (`bootstrap`, `pairwise_probs`) |
| §11 tiers | `hierarchy/tiers.py` |
| §12 freshness & pipeline | `hierarchy/data.py`, `hierarchy/cli.py`, `.github/workflows/daily.yml` |
| §12 name reconciliation | `hierarchy/names.py`, `config/models.yaml` |
| §13 ledger | `tests/` pin the mitigations that are enforceable |

Run it:

```bash
pip install -r requirements.txt
python -m hierarchy validate        # config ↔ methodology consistency
python -m hierarchy demo            # end-to-end run on bundled synthetic data
python -m hierarchy fetch --allow-missing && python -m hierarchy run   # real data
pytest                              # enforces §4, §6–§11 contracts
```

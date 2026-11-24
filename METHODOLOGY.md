# Model Atlas — ranking methodology

**Version 2.1.0 · 2026-11-24**

The dashboard opens on the Atlas model hierarchy. Its inputs are the retained
source snapshots in `output/leaderboards.json`. The four native boards and the
experimental five-pillar composite remain independently inspectable.

## 1. Atlas model and effort ranks

Atlas uses Artificial Analysis, Arena text and LiveBench. Terminal-Bench measures a
model paired with an agent harness and stays in the systems tab. On each dashboard
load, only available snapshots within the registry's freshness window contribute.
A failed refresh can still contribute its last valid snapshot during that window.

- **Model view.** Within each evaluator, take the median of a model's scored
  configurations. Group by the canonical name (case-insensitive, with spaces,
  hyphens and underscores treated alike, then the reviewed aliases in
  `config/models.yaml`, the same rule as `hierarchy/names.py`) after removing a
  recognized parenthesized reasoning setting and its default-fallback qualifier. A trailing standalone `xHigh` also denotes effort.
  Preserve model editions, dates and other qualifiers. A model with many settings
  still contributes one value per evaluator.
- **Effort view.** Key each entry by canonical model name plus its exact setting. Artificial
  Analysis's "Default Fallback" qualifier joins the plain setting: it marks Anthropic's default
  API fallback to an older model, which AA observed in ~0.1% of tasks
  ([source](https://x.com/ArtificialAnlys/status/2104640155843989864)). The label stays visible.
  Treat a trailing `xHigh` and `(xHigh)` as the same explicit setting. Rank explicitly identified settings. An unspecified effort supplies no evidence
  for an explicit setting. Distinct vendor spellings may yield separate entries.
- **Within-board standing.** The reference field is the set of entries that appear
  on at least two current evaluators. Each board ranks the shared models it scored,
  so padding a board with single-board entries cannot inflate them. A model is still
  averaged over only the evaluators that scored it. An entry's
  percentile is 100 × (field members strictly below + half the tied *other* members)
  / (number of other field members). Entries outside the field are placed against
  it the same way. The effort view uses only explicitly identified settings as its field.
- **Field offsets.** Shared fields differ in strength: LiveBench scores mostly frontier
  models, so its percentiles are harder to earn. Fit percentile ≈ ability + board offset
  over ranked entries by alternating least squares, with offsets summing to zero. In a
  leave-one-board-out check on the 22 models scored by all three evaluators (2026-11-24,
  in-sample), the average signed shift from dropping AA/Arena/LiveBench went from
  −3.6/+1.2/+2.4 points to −0.9/+1.9/−1.0: 7.2 → 3.8 in total, though Arena's rose slightly.
  A pairwise win-rate alternative did worse (−1.4/+2.6/−1.2).
- **Atlas score.** Average the available evaluator percentiles minus their board offsets.
  A model scored by every evaluator therefore keeps its plain average; only models missing
  an evaluator are adjusted. Scores can fall slightly outside 0–100. Require
  at least two contributing evaluators, round to one decimal and give ties a
  shared competition rank. One-source observations remain searchable with their
  source percentile and an empty Atlas score. Expand any row for the input scores.

The model view shows the median reported Artificial Analysis dollar cost per task
across scored configurations with a price. Expand the row for the individual prices.
The effort view uses the matching setting. Missing costs stay blank (a dash), and a
reported zero is rounded to cents. LiveBench cost per successful task has a separate
denominator and is labeled in the evidence. Sorting by price preserves capability ranks.

An Atlas score measures standing among the models each evaluator tested. Source
rosters, tested settings and coverage differ. Small score gaps have no associated
confidence guarantee. The number is neither a task success probability nor a
prediction for an untested effort setting.

### Reading a native board

Ranks are descending competition ranks: `1, 2, 2, 4`. Equal supplied scores share a rank.
For rounded public scores, we do **not** invent hidden decimal precision to break ties.
Search, filtering, cost sorting, and pagination retain the within-source score rank.
Missing scores are `null`, never zero; missing costs are not free. A source's model list
can include historical, preview, or restricted-access systems. “Observed recently” does
not mean “recently released,” “publicly available,” or “recently evaluated.”

### Source selection and refresh reliability

Atlas polls daily. A successful retrieval confirms that the board could be read.
Only a source publication date dates the board itself. The 14-day freshness
window is an Atlas policy; an evaluator can publish less frequently. Coverage
and rank can change when a source ages out, even with identical model scores.

| Source | Reason to include it | Main limitation |
|---|---|---|
| [Artificial Analysis](https://artificialanalysis.ai/methodology/intelligence-benchmarking) | Broad, versioned suite with explicit effort settings. | The index packages multiple evaluations, including Terminal-Bench 4.0. Its table supplies an observation date through our collector and no per-entry evaluation date. |
| [Arena](https://arena.ai/blog/ranking-method) | Human preferences, vote counts and source uncertainty intervals complement task scores. | Participation, prompts and release selection affect the population. Style control addresses only part of this bias. [Independent analysis](https://papers.nips.cc/paper_files/paper/2025/file/70a93f260a51123b3c0e33ecd1b4de97-Paper-Datasets_and_Benchmarks_Track.pdf) |
| [LiveBench 2.0](https://livebench.ai/) | Dated releases with inspectable task-level results and suite weights. | Scores use single runs; many published labels omit the effort. A release date can predate a successful fetch by weeks. |
| [Terminal-Bench](https://www.tbench.ai/) | Publishes the harness, resolution rate and uncertainty for agent work. | Changing the harness changes the system being compared. Keep this as a separate systems view. |

For a cross-check on general capability, [Epoch's ECI](https://epoch.ai/data/eci-documentation/methodology)
accounts for benchmark difficulty and uncertainty. Its input set spans many benchmarks,
so including it as another equally weighted vote would require checking overlap.
For an engineering-specific comparison, [SWE-rebench](https://swe-rebench.com/)
makes the issue window, agent/model distinction and cost visible. Its narrower scope
fits a dedicated engineering view. For field reliability, maintainer acceptance
provides another check. In a [METR study](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/),
four maintainers reviewed 296 model-generated patches from three repositories.
Passing benchmark tests and satisfying maintainer review were distinct outcomes.

## 2. Current source registry

Authoritative metadata and version pins live in [`config/leaderboards.yaml`](config/leaderboards.yaml).

| View | Metric | Unit of comparison | Important qualification |
|---|---|---|---|
| [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models) | Intelligence Index **v5.0.1** | Exact model + effort + fallback configuration | Already an aggregate (CritPt v2 regrade across the 9-benchmark v5 suite). Public table has rounded scores, no model-level CIs; grouped effort variants are retained. Cost/task is not $/million tokens. |
| [Arena](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset) | `text_style_control`, `latest`, `overall` | Exact model/configuration | Official paginated dataset, not raw text Elo or the agent board. Includes historical models. Preserve source 95% intervals and votes. |
| [LiveBench](https://livebench.ai/) | **LiveBench 2.0** overall and seven suites | Source evaluation configuration | Official release CSV/JSON feed, not legacy LiveBench overall. Overall uses Long Agentic ×2, Design/Coding ×1.5, other suites ×1 over measured suites. Single runs; no invented CIs. |
| [Terminal-Bench](https://www.tbench.ai/) | **4.1** resolution rate | Model + effort + **agent harness** | Systems, not isolated models. Preserve the published ± 95% confidence margin across evaluation trials. Model release dates are not evaluation dates. |

Source methods: [AA](https://artificialanalysis.ai/methodology/intelligence-benchmarking),
[LiveBench](https://livebench.ai/#/methodology), [Terminal-Bench](https://www.tbench.ai/run).
SWE-bench's [official board](https://www.swebench.com/) was also reviewed: results span
agents and releases. It is not silently promoted into a current, fixed-harness model score.

The registry pins versions. An AA index revision, LiveBench suite migration, or
Terminal-Bench task revision requires deliberate review, a new version/ID where appropriate,
fixtures, and a changelog entry. Historical dated snapshots from superseded versions listed
in `previous_versions` remain archived on disk for reproducibility without being pooled into
current boards or treated as corrupt files. The native boards are **never** injected into
the old composite slots. In particular, LiveBench 2.0 is not `livebench_overall`, and
Terminal-Bench 4.1 systems are not the composite's legacy `terminal_bench` observation.

## 3. Identity and coverage

- Keep the original display name. `high`, `max`, `xhigh`, fallback policies, release dates,
  preview labels, quantization, and harnesses can change results and are not stripped.
- Canonical identity normalizes case and separators and applies reviewed exact aliases in
  `config/models.yaml`. It never fuzzily merges a family, a base model, and its reasoning variants.
- Native duplicate identity = canonical full name + harness. Conflicting duplicates fail
  validation rather than silently taking the last row or best score.
- The catalogue (`output/catalogue.json`) is the **union** of source entries, not an intersection with OpenRouter's
  visible top ten. Exact-name catalogue matches are discovery aids, not permission to pool
  results across evaluators or settings.
- There is no hardcoded allowlist of “frontier” names. New valid rows flow through adapters.
- `open_weights` is a source label, not a legal/license audit. Do not infer availability from
  a brand, score, or absence of an open badge. Search can show matches on other boards.

## 4. Provenance, dates, and freshness

Each native snapshot records:

- `board`, `version`, `source`, original `rows` and any source-supplied uncertainty;
- `published_at`: a date actually supplied for the board; `null` if not supplied;
- `observed_at`: when the table was retrieved; `null` for old snapshots lacking that record;
- `retrieval_method`, `scope`, and, for the initial audited imports, evidence filename/hash.

**Retrieval is never manufactured into evaluation.** The initial AA, LiveBench, and
Terminal-Bench tables did not supply a board evaluation/publication date in the retrieved
view; they therefore have `published_at: null`. Terminal-Bench release dates stay on rows
as `release_date`. The retained Arena dataset keeps its actual `2026-10-28` publication date,
not the `2026-11-03` date of this repair. See [the capture record](data/evidence/2026-11-03/README.md).

For status only, use publication date when known, otherwise observation date. Over **14 days**
is `stale`; over **90 days** is `expired`. Unknown evaluation dates always remain disclosed.
Old native boards remain browsable for reference with warnings; they are not advertised as
current. The static dashboard recalculates age in the browser, so a stopped refresh job
cannot leave a permanently green “fresh” label. `generated_at` is a build timestamp only.

Every published board carries a SHA-256 data fingerprint. Output configuration hashes include
versioned source/metric definitions; composite config hashes also include the identity aliases.
A rebuild does not renew source dates.

## 5. Acquisition and failure policy

Automatic native adapters use the official Arena dataset and the public source-owned tables
for AA, LiveBench and Terminal-Bench. AA also checks the current index version in the source's
methodology. No paid API keys or private credentials are required by these adapters.

They fail closed on missing headers/version markers, invalid/non-finite numbers, unknown
source URLs, duplicate identities, future/invalid dates, invalid CIs, inadequate row counts,
source date regression, or a scored-roster shrink greater than 20% from the previous valid
snapshot. A legitimate large pruning needs review rather than an automatic overwrite.
Arena pagination must be complete; a first-100-rows or raw-Elo mirror is not an equivalent
fallback. Tables that become client-rendered or blocked produce an actionable failure,
not fabricated data. Parsers have offline fixtures; this does not guarantee future page stability.

Fetch status is persisted separately from observations. A failed refresh retains the last
valid snapshot **without changing its source or observation dates**, displays the failure,
and continues other boards. `fetch --strict` / `run --strict` return nonzero if any automatic
source fails. Default best-effort mode publishes explicit missing/stale/failure states.
There is never a silent synthetic fallback.

## 6. Experimental composite (not the default ranking)

`output/leaderboard.json` retains the geometric composite for research and the synthetic demo.
It must not be described as a comprehensive current ranking when publication gates fail.
`output/leaderboards.json` (plural) is the main native-board deliverable.

### Weights

Authoritative numbers: [`config/weights.yaml`](config/weights.yaml).
OpenRouter usage is **context only**: neither capability evidence nor eligibility.
Its former 0.10 weight is reassigned to Arena, preserving the 0.35 human-preference pillar.

| Pillar | Weight | Benchmark global weights |
|---|---:|---|
| Human preference | 0.35 | Arena style-controlled rating 0.35 |
| Knowledge & reasoning | 0.20 | GPQA Diamond 0.08; MMLU-Pro 0.06; legacy LiveBench 0.03; legacy SEAL 0.03 |
| Math | 0.15 | AIME 2025 0.08; HMMT Feb 2025 0.04; MATH-500 0.03 |
| Coding | 0.20 | SWE-bench Verified 0.10; LiveCodeBench 0.07; legacy Terminal-Bench coding share 0.03 |
| Agentic | 0.10 | Tau²-bench 0.06; legacy Terminal-Bench agentic share 0.04 |

There are 13 weighted slots but **12 distinct underlying measurements**. Terminal-Bench's
0.03/0.04 split is one observation and counts once for eligibility. The two slots receive
the **same bootstrap noise draw**, not independent measurement noise.

### Publication gates

1. Remove individual expired (>90 days), invalid-date, and future-date observations.
   Flag observations older than 14 days. One fresh row cannot redate a whole benchmark.
2. Candidate models need **5 distinct measurements across 3 pillars**.
3. Each used benchmark needs **3 comparator models within the eligible cohort**. Remove
   sparse metrics and recompute eligibility until stable. Non-cohort entries never change
   composite normalization, but remain in the visible evidence audit.
4. At least **5 comparable models** are required to publish any composite ranking or tiers.
5. Every configured pillar must have comparable evidence somewhere in the cohort. An entire
   missing math/agentic domain blocks a purported generalist hierarchy.

When blocked, publish `quality.status = withheld`, reasons, cohort/roster counts, unranked
observations, sparse metrics, and rejected-date records. **No single-model T1 or manufactured
zero-width confidence interval.** Missing evidence is not evidence that a model is weak.
As of this audit, math and agentic evidence are absent from the live composite, so it is
withheld. Source-native rankings remain useful and visible independently of these gates.

### Arithmetic and uncertainty

Within the eligible cohort, normalize each benchmark to [0.02, 1]:

- Standard benchmarks: 50% descending Borda rank + 50% min-max after 5th/95th percentile clipping.
- Arena rating: min-max without percentile clipping.
- Equal values map to a neutral 0.5; sparse/singleton metrics are not scored in production.

Within pillars: arithmetic mean weighted by available benchmark global weights. Pillar floor:
0.05. Across available pillars: geometric mean weighted by renormalized pillar weights.
Coverage `C` is the sum of present global slot weights. Final `G = geometric × (0.70 + 0.30 C)`.
This is a declared heuristic, not a measured latent intelligence scale or an absolute score
that is comparable across different cohorts.

Use 2,000 parametric bootstrap repetitions, seed 42 by default. Convert genuine source 95%
interval width to sigma with `/3.92`; otherwise use the declared raw-noise assumption (Arena 8,
other metrics 1.5). Re-run normalization and aggregation in each draw. Publish the median and
2.5/97.5 percentiles plus actual seed/repetition count and evidence/config hashes.

Pairwise probability is `P(A > B) + 0.5 P(A = B)`: identical draws give 0.5, not a false
significant difference. Two-sided bootstrap tail probabilities get Benjamini–Hochberg
adjustment. A tier can separate from its anchor only with directional confidence ≥0.95 and
adjusted tail ≤0.05. Disjoint intervals do **not** bypass the multiplicity rule. Maximum 7
tiers; a capped final tier can contain separated models. These are heuristic groupings,
**not proof of equivalence, formal p-values, or validated real-world superiority**.

### Composite manual data

`data/manual/scores.csv` accepts `benchmark,model,score,as_of,source,notes[,ci95_lo,ci95_hi]`.
Use evaluation/publication dates, exact configurations, a source citation and compatible
benchmark/harness semantics. Each row retains its date, source, notes and optional CI.
Manual rows augment the latest automatic roster; newest observation per canonical model wins,
manual wins on equal dates. A row cannot delete all other benchmark models. Invalid rows and
conflicting duplicate identities are errors. Raw snapshots are selected by published date,
not directory/retrieval time. The synthetic demo is explicitly labeled and re-dated only in
its isolated demo path.

## 7. Limitations

- A faithful leaderboard explorer does not fix selection bias, contamination, evaluator
  error, inadequate sample sizes, or cost/effort differences in the underlying evaluations.
- The native boards disagree legitimately. A narrow lead, especially with rounded scores or
  overlapping intervals, is not proof of meaningful superiority.
- Cross-source names/settings frequently do not match. We prefer separate visible evidence
  to aggressively merging enough rows to manufacture a composite.
- Original source CIs do not automatically support cross-source significance testing. No CI
  is estimated for source-native boards that do not supply one.
- Saturated and archived legacy tests cannot establish coverage of new frontier releases.
- HTTP/table parsers need maintenance; fetch-health and stale-state visibility are part of
  ranking quality, not optional diagnostics.

## 8. Version history

- **2.1.0 — 2026-11-24:** Migrate Artificial Analysis native registry to Intelligence Index
  v5.0.1 and parse full uncollapsed model configurations from Next.js RSC payloads; replace
  LiveBench's broken HTML table scrape with LiveBench 2.0's official `/data/<release>/` CSV/JSON
  feed and explicit release dates; migrate Terminal-Bench native registry to 4.1 with full RSC
  display rosters and board update timestamps; retain superseded `previous_versions` snapshots
  as clean historical archives; make output generation idempotent and wire full Python + JSDOM
  CI workflows while suppressing timestamp-only daily commits.
- **2.0.0 — 2026-11-03:** Source-native current rankings become the default; independently
  versioned AA v5.0 / Arena / LiveBench 2.0 / Terminal-Bench 4.0 views and audited initial
  snapshots; removal of usage roster gate and usage capability weight; composite sample and
  domain gates; row-level freshness/provenance and manual union; distinct-observation
  eligibility/shared alias noise; tie-safe pairwise probabilities; BH-only tier separation;
  visible refresh failures; browser-side aging and source-preserving search/sort/export.
- **1.1.0:** Historical geometric hierarchy, retained in the archived specification.

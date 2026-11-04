# Ranking quality audit — 2026-11-03

## What was broken

The input revision published one model (`glm 5.3 flash`) as T1 at G=55.7 with a 55.7–55.7
interval. That was a pipeline artifact, not evidence it was the strongest current model.

| Failure | Effect | Repair |
|---|---|---|
| Fresh OpenRouter top-ten roster used as a mandatory allowlist | Deleted frontier variants and every model outside the scraped popularity list before eligibility | No usage gate. Source-native union of rosters; complete composite evidence roster retained. |
| Usage carried 10% of the capability score | Popular/cheap/routed models could beat more capable models for unrelated reasons | Usage context-only; composite human preference is Arena alone at 0.35. |
| Archived/manual 2025-era capability registry was the only ranking route | Current models with real public evaluations disappeared because legacy slots were absent | Native AA v5.0, LiveBench 2.0, Arena and Terminal-Bench 4.0 views; no silent metric-version substitution. |
| One-model normalization and bootstrap | Artificial point score, zero-width interval, and T1 without competitors | Minimum cohort, per-benchmark comparator, and whole-domain publication gates. |
| AA optional/off; new LiveBench intentionally blocked with no alternative view | Two major current model rosters invisible | Separate source views, not double-counted components of the old composite. |
| Split Terminal-Bench alias counted and jittered twice | Inflated eligibility and understated dependence | Count distinct underlying measurements; shared perturbation for aliases. |
| Two tied bootstrap distributions produced zero win probabilities both ways | False two-sided significance | Half-credit ties; identical distributions produce q=1. |
| Disjoint intervals bypassed the BH tier adjustment | Tier boundaries could violate the stated multiplicity policy | Tier separation only through the adjusted directional evidence. |
| Manual CSV replaced whole benchmark; newest date applied to all rows | Lost coverage and stale-data laundering | Row union with per-observation date/source/notes/CI. |
| Arena raw mirror/first-row fallback | Different score semantics or truncated cohort could masquerade as complete style control | Complete canonical dataset only; explicit failures. |
| Dashboard's default personal score omitted coverage penalty and differed from published G | Displayed order was not even the published methodology | Remove misleading slider ranking; source-native raw ranks, evidence details, and honest composite audit. |
| No durable refresh-health report; generated timestamp looked like freshness | Failures and old data were hard to see | Persist per-board refresh attempts; retain dated last-good snapshots; browser recalculates age. |

## Primary-source comparison

See the [dated evidence record](../data/evidence/2026-11-03/README.md) for all source URLs,
version checks, capture scope, and limitations. No secondary blog's model list or score is
used as a benchmark input.

The initial native publication contains **565 scored source entries**, not 565 distinct model
families: 91 Artificial Analysis configurations, 419 Arena configurations, 32 LiveBench rows,
and 23 Terminal-Bench model+agent systems. Settings remain distinct. Source names and raw scores
are preserved. The static dashboard defaults to AA's current-model view, with other evaluators
one click away. It does not claim all Arena's historical entries are new releases.

After removing the usage gate, the retained composite data has 529 named evidence entries and
31 models with enough comparable legacy measurements. **Math and agentic are entirely missing**,
so a comprehensive composite remains withheld rather than advertising those 31 as the current
frontier. This is not solved by reducing eligibility until a desired winner appears.

## Operational limits

Initial new tables are explicitly labeled manual public-table transcriptions and have unknown
evaluation dates. They are useful, auditable source observations, not a claim that the new HTTP
adapters have completed an unattended production refresh. Subsequent adapter outcomes are
recorded in `data/leaderboards/fetch_status.json` and displayed per board. Version/header guards,
last-good retention, minimum roster sizes, and regression tests protect the publication if a
source becomes blocked, client-rendered, or changes its evaluation suite.

### Sandbox HTTP verification

The native automatic adapters were exercised with a short timeout in this environment on
2026-11-03. All four direct HTTP fetches failed with `SSLError`; no new observations were
published from those attempts. The actual outcomes are recorded in
`data/leaderboards/fetch_status.json`. The primary pages used for the dated transcriptions
were accessible through the research page-retrieval tools. This is why the initial imports
are labeled manual source-table transcriptions rather than a successful unattended refresh.
Do not disable TLS verification to make a fetch appear successful. Recheck in the scheduled
runner; until it succeeds the dashboard explicitly retains and labels the audited snapshots.

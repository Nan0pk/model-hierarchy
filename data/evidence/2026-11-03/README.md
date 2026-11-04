# Source capture record — 2026-11-03

These CSVs are **real public source-table transcriptions**, not model-generated benchmark
estimates or synthetic demo data. They bootstrap the new source-native views reproducibly.
They were transcribed from the readable source pages retrieved during the ranking audit;
they are not original upstream HTML. Production HTML adapters are independently fixture-tested.

| CSV / retained input | Source | Capture scope |
|---|---|---|
| `artificial_analysis.csv` | https://artificialanalysis.ai/leaderboards/models | All **91 scored** entries of the current-model Intelligence Index table, plus creator/context/cost/task/speed fields. Unscored rows below the table are not in this initial transcription. Original integer score precision retained. |
| `livebench.csv` | https://livebench.ai/ | All **32** visible LiveBench 2.0 rows, seven suite scores, cost per successful task, and the source's open-weight badge (absence does not establish proprietary status). |
| `terminal_bench.csv` | https://www.tbench.ai/ | All **23** visible Terminal-Bench 4.0 system entries, exact reasoning labels, harness, resolution rate, ± margin and model release date. No confidence level inferred for the margin. |
| `../../raw/2026-10-28/lm_arena_elo.json` | https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset | Retained official **419-row** `text_style_control / latest / overall` snapshot already in the repository; source date 2026-10-28. Original scores, intervals, and votes unchanged. Its original retrieval timestamp was not recorded. |

Version checks:
- AA: https://artificialanalysis.ai/methodology/intelligence-benchmarking — current heading
  `Artificial Analysis Intelligence Index v5.0`. Older index scores must not be combined with v5.
- LiveBench: https://livebench.ai/#/methodology — **2.0**, seven suites, single runs, highest
  supported effort unless the expanded model row says otherwise. Not the old six-category board.
- Terminal-Bench: the public page displays **4.0** and names the agent harness for each row.

The three transcribed tables do not supply a board evaluation/publication date in the
retrieved view. Their native snapshots therefore have **`published_at: null`** and
`observed_at: 2026-11-03`. Release dates on Terminal-Bench do not fill that gap. A subsequent
successful automatic scrape may update observation time; a failed scrape must not.

Native JSON files in `data/leaderboards/` include the evidence paths and SHA-256 checksums.
Tests verify that every transcribed name and score agrees with the committed initial snapshots.
Do not replace these dated audit inputs with a new scrape; add a dated snapshot instead.

Additional comparisons reviewed:
- Arena raw text: https://arena.ai/leaderboard/text (not interchangeable with style control).
- SWE-bench: https://www.swebench.com/ (mixed model/agent/release results; not relabeled as current
  fixed-harness model measurements).

**This is an observation of the sources, not an independent rerun of their evaluations.**

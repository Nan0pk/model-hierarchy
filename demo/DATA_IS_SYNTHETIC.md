# Demo data is SYNTHETIC

Every number in `scores.csv` is **made up** to exercise the full pipeline with
realistic shapes (12 models, 13 benchmark weights, gaps + two holes for
missing-data paths). It is NOT a real leaderboard and must never be cited as one.

- To see the real thing: `python -m hierarchy run`
- To add real numbers by hand: `data/manual/scores.csv` (same columns)
- Column contract: `benchmark,model,score,as_of,source,notes[,ci95_lo,ci95_hi]`
- `terminal_bench_agentic` needs no rows — it is an alias of `terminal_bench`
  with a split weight (METHODOLOGY.md §4)

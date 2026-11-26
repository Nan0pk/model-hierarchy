# Contributing to Model Atlas

Thanks for helping keep AI rankings honest. This repo's rule is simple:
**every number published here stays attributable to its original source, date,
and configuration.** If a change would make a number less attributable, it is a
bug regardless of how good the ranking looks.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
npm ci

python -m hierarchy validate   # config ↔ methodology consistency
pytest -q                      # Python suite
npm test                       # dashboard regression suite
```

Python ≥ 3.10 and Node ≥ 20 are required. There is no runtime dependency for
the dashboard; `jsdom` is a dev/test dependency only.

## Kinds of changes

- **Data** — produced by `python -m hierarchy run` (fetch → publish → export).
  Never hand-edit `output/` or `data/leaderboards/`: snapshots are dated, and a
  rebuild must not renew a source date. Fix the adapter, then re-run.
- **Adapters** (`hierarchy/fetch/`) — must fail closed. A page-shape change,
  metric-version bump, truncated roster, or future date is an error, not a
  fallback. Every parser gets an offline fixture test in `tests/`.
- **Methodology** (`METHODOLOGY.md`, `config/*.yaml`, `hierarchy/`) — normative.
  A weight or eligibility change requires: bump `version` in `config/weights.yaml`,
  a changelog line in `METHODOLOGY.md`, updated pins in `tests/test_weights.py`,
  and `METHOD_VERSION`/package version kept in step (`tests/test_docs.py` guards this).
- **Dashboard** (`dashboard/`) — static and dependency-free. If you touch
  `styles.css` or `app.js`, run `make stamps` to rewrite the cache-busting
  `?v=` hashes (CI runs it too, so a forgotten stamp heals on the next daily
  build). Missing data must render as a dash, never as zero.

## Tests

```bash
pytest -q && ruff check hierarchy tests && npm test
```

All three must pass before you open a pull request. CI runs the same set plus
an offline build smoke check on every push and PR.

## Reviewing a ranking claim

When changing anything that can move a published rank, state in the PR
description: which scores moved, why the evidence still supports the new
output, and which test pins the behavior. Screenshots of the dashboard before
and after are welcome.

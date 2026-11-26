.PHONY: demo validate test check run fetch stamps sync-version

demo:
	python -m hierarchy demo

validate:
	python -m hierarchy validate

test:
	pytest -q

check:
	python -m hierarchy validate && pytest -q && ruff check hierarchy tests && npm test

stamps:
	node dashboard/stamps.mjs

sync-version:
	python scripts/sync_version.py

fetch:
	python -m hierarchy fetch --allow-missing

run:
	python -m hierarchy run
	node dashboard/export.mjs

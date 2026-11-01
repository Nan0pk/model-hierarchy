.PHONY: demo validate test run fetch

demo:
	python -m hierarchy demo

validate:
	python -m hierarchy validate

test:
	pytest -q

fetch:
	python -m hierarchy fetch --allow-missing

run:
	python -m hierarchy run

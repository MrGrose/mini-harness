.PHONY: help install test lint eval run

help:
	@echo "install test lint eval run"

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check src tests evals

eval:
	python evals/run_eval.py --max-steps 6

run:
	mini-harness run "$(TASK)" --root "$(ROOT)" --trace traces/run.jsonl

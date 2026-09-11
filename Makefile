.PHONY: install corpus extract stability verify report test all

install:
	uv sync --all-extras

corpus:
	uv run python scripts/generate_corpus.py --tier clean_digital --tier scanned --tier handwritten_fields --tier incomplete --tier ambiguous

extract:
	uv run python scripts/run_extraction.py --limit 5

stability:
	uv run python scripts/run_stability.py

verify:
	uv run python scripts/run_verify.py --self-check

report:
	uv run python scripts/make_report.py

test:
	uv run pytest -q

all: corpus test extract stability report

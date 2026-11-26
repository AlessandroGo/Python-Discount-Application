.PHONY: setup dev build test lint format typecheck check audit

setup:
	uv sync
	git config core.hooksPath .githooks

dev:
	uv run python -m pc_loan_discount

build:
	uv run --group build pyinstaller --onefile --windowed --noconfirm --name pc-loan-discount --paths src --specpath build --hidden-import pc_loan_discount.gui src/pc_loan_discount/__main__.py

test:
	uv run pytest --cov --cov-report=term-missing:skip-covered

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format . && uv run ruff check --fix .

typecheck:
	uv run pyright

audit:
	uv run pip-audit

check: lint typecheck test

# Python Discount Application (`pc-loan-discount`)

Desktop Python application that discounts simple or compound interest loans against projected PC component price trends (such as RAM, GPU, CPU, and SSD) to show whether taking a loan to build a PC now is net worth it and by how much.

## Stack
- Language: Python 3.12
- Package manager: uv
- UI: `tkinter` (Python standard library, zero runtime dependencies)
- Quality tools: ruff, pyright (strict), pytest + pytest-cov, pip-audit, pre-commit (ruff + gitleaks)

## Commands
All tasks go through `make`. Prefer these over calling tools directly.
- Setup: `make setup` (required after every clone to sync deps and activate `.githooks/`)
- Run locally: `make dev`
- Test (all): `make test`
- Test (one): `uv run pytest tests/test_calculator.py::test_simple_interest -q`
- Lint / format: `make lint` / `make format`
- Typecheck: `make typecheck`
- Dependency audit: `make audit` (CI runs it weekly and on dependency PRs)
- Everything CI runs: `make check`. **Run this before every commit.**

## Architecture
- `src/pc_loan_discount/__main__.py`: CLI / GUI entry point (`python -m pc_loan_discount`)
- `src/pc_loan_discount/models.py`: typed dataclasses, enums, and component trend presets
- `src/pc_loan_discount/calculator.py`: pure financial discounting, loan schedules, PC price projection, and break-even math
- `src/pc_loan_discount/gui.py`: `tkinter` desktop interface (thin presentation layer calling `calculator`)
- `tests/`: mirrors `src/pc_loan_discount/`

## Conventions
- Follow `ruff format` and `ruff check`; don't hand-format.
- Strict pyright type annotations on all public functions; avoid `Any` without a justifying comment.
- Keep financial calculations pure and UI-independent in `calculator.py`.
- Every bug fix comes with a regression test.

## Workflow
- Branch per task: `feat/…`, `fix/…`, `chore/…`
- Conventional Commits (`feat: …`, `fix: …`).
- Direct commits and pushes to `main` are blocked by `.githooks/`; work on branches.

## Gotchas
- Activate nothing manually; always use `uv run` (or `make` targets).
- On Windows, `.githooks/*` must keep LF line endings (`.gitattributes` enforces this).

## Do not
- Read or modify `.env*` files.
- Add new dependencies without asking.
- Modify tests just to make them pass.

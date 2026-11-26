# Python Discount Application (`pc-loan-discount`)

Desktop Python application to discount simple or compound interest loans over a period and compare them against projected PC component price trends (such as RAM, GPU, CPU, and SSD) to evaluate whether taking out a loan to build a PC now is net worth it and by how much.

## Setup

Required after every clone (syncs dependencies and activates the repository's `.githooks/`):

```bash
make setup
```

## Run

```bash
make dev
```

## Test & Quality Checks

```bash
make test       # run pytest with coverage
make lint       # ruff check + format check
make typecheck  # pyright (strict)
make audit      # pip-audit dependency vulnerability scan
make check      # lint + typecheck + test (same as CI)
```

# Python Discount Application (`pc-loan-discount`)

Desktop Python application to discount simple or compound interest loans over a period and compare them against projected PC component price trends (such as RAM, GPU, CPU, and SSD) to evaluate whether taking out a loan to build a PC now is net worth it and by how much.

## Features

- **Loan discounting**: Supports Simple Interest (monthly instalments or lump sum), Compound Interest (amortized monthly), and Compound Interest (lump sum at maturity) with selectable compounding frequency (monthly, quarterly, semi-annually, annually, daily).
- **PC component price trends**: Itemize your build (RAM, GPU, CPU, NVMe SSD, Motherboard/PSU/Case, or custom parts) with per-component annual price trend forecasts and built-in market presets (e.g., *RAM & AI Supply Squeeze*, *Severe RAM & GPU Spike*, *Normal Hardware Deflation*, *Flat Prices*).
- **Net Present Value (NPV) verdict**: Discounts every future loan payment and the projected future PC price back to today's money using your discount rate / opportunity cost, plus optional monthly early-use value.
- **Break-even analysis & sensitivity**: Computes the exact break-even loan APR, break-even uniform PC price trend, component-by-component forecast, full repayment schedule, and APR sensitivity table.

## Setup

Required after every clone (syncs dependencies and activates the repository's `.githooks/`):

```bash
make setup
```

## Run

Desktop GUI (`tkinter`, Python stdlib — zero extra runtime dependencies):

```bash
make dev
```

Quick terminal summary report:

```bash
uv run python -m pc_loan_discount --cli --loan-rate 12 --term-months 12 --discount-rate 6
```

## Test & Quality Checks

```bash
make test       # run pytest with coverage
make lint       # ruff check + format check
make typecheck  # pyright (strict)
make audit      # pip-audit dependency vulnerability scan
make check      # lint + typecheck + test (same as CI)
```

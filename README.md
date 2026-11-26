# Python Discount Application (`pc-loan-discount`)

Desktop Python application (defaulting to South African Rand `ZAR`) to discount simple or compound interest loans over a period and compare them against projected landed PC component costs—accounting for South African import tax (SARS 15% VAT on 110% ATV = 16.5% effective + optional customs duty + courier clearance/shipping), Rand FX weakening, and per-component hardware price trends (RAM, GPU, CPU, NVMe SSD).

## Features

- **South African Rand (`ZAR`) default & multi-currency**: Built-in locale profiles for `ZAR (R)`, `USD ($)`, `EUR (€)`, and `GBP (£)`.
- **South African import tax & FX model**: Models SARS customs valuation (`Customs Duty + VAT × (110% ATV + Duty) + Shipping/Clearance`) plus annual ZAR weakening against USD so both today's and future landed costs reflect real local prices. Can be toggled off if entering all-in local retail shelf prices.
- **Loan discounting**: Supports Simple Interest (monthly instalments or lump sum), Compound Interest (amortized monthly), and Compound Interest (lump sum at maturity) with selectable compounding frequency (monthly, quarterly, semi-annually, annually, daily).
- **PC component price trends**: Itemize your build (RAM, GPU, CPU, NVMe SSD, Motherboard/PSU/Case, or custom parts) with per-component annual price trends and built-in market presets (*RAM & AI Supply Squeeze*, *Severe RAM & GPU Spike*, *Moderate Inflation*, *Normal Hardware Deflation*, *Flat Prices*).
- **Net Present Value (NPV) verdict & thresholds**: Discounts every loan payment and future landed PC cost back to today's money using your discount rate / opportunity cost, plus optional monthly early-use value, break-even loan APR, break-even global component trend, payment schedule, and APR sensitivity table.

## Setup

Required after every clone (syncs dependencies and activates the repository's `.githooks/`):

```bash
make setup
```

## Run

Desktop GUI (`tkinter`, Python stdlib — zero runtime dependencies):

```bash
make dev
```

Quick terminal summary report (defaults to `ZAR` with SARS import tax enabled):

```bash
uv run python -m pc_loan_discount --cli
uv run python -m pc_loan_discount --cli --currency ZAR --loan-rate 15.5 --duty-pct 15
uv run python -m pc_loan_discount --cli --currency USD --no-import-tax --loan-rate 12
```

## Build Standalone Executable

Creates a single-file desktop executable in `dist/pc-loan-discount.exe` (Windows) using PyInstaller:

```bash
make build
```

## Test & Quality Checks

```bash
make test       # run pytest with coverage
make lint       # ruff check + format check
make typecheck  # pyright (strict)
make audit      # pip-audit dependency vulnerability scan
make check      # lint + typecheck + test (same as CI)
```

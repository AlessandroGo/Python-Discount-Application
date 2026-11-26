"""PC loan and component price trend discounting application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pc_loan_discount.calculator import analyze_pc_loan, format_text_report
from pc_loan_discount.models import (
    DEFAULT_COMPONENTS,
    AnalysisInputs,
    CompoundingFrequency,
    InterestType,
)

__version__ = "0.1.0"


def get_version() -> str:
    """Return the package version."""
    return __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pc-loan-discount",
        description="Compare a discounted PC build loan against projected component price trends.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Print a text analysis report in the terminal instead of opening the desktop GUI.",
    )
    parser.add_argument(
        "--interest-type",
        choices=[t.value for t in InterestType],
        default=InterestType.COMPOUND_AMORTIZED.value,
        help="Loan interest method (default: compound_amortized).",
    )
    parser.add_argument(
        "--compounding",
        choices=[c.value for c in CompoundingFrequency],
        default=CompoundingFrequency.MONTHLY.value,
        help="Compounding frequency for compound loans (default: monthly).",
    )
    parser.add_argument(
        "--simple-lump-sum",
        action="store_true",
        help="Pay a simple-interest loan as one lump sum at maturity.",
    )
    parser.add_argument("--loan-rate", type=float, default=12.0, help="Loan APR in percent.")
    parser.add_argument("--term-months", type=int, default=12, help="Loan term in months.")
    parser.add_argument(
        "--wait-months",
        type=int,
        default=None,
        help="Months waited before buying in cash (defaults to --term-months).",
    )
    parser.add_argument(
        "--discount-rate",
        type=float,
        default=6.0,
        help="Annual discount rate / opportunity cost in percent.",
    )
    parser.add_argument("--down-payment", type=float, default=0.0, help="Upfront down payment ($).")
    parser.add_argument(
        "--early-use",
        type=float,
        default=0.0,
        help="Optional monthly value ($) of having the PC earlier.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Launch the desktop GUI, or print a CLI report when `--cli` is passed."""
    args = _build_parser().parse_args(argv)
    if args.cli:
        inputs = AnalysisInputs(
            components=DEFAULT_COMPONENTS,
            loan_annual_rate_pct=args.loan_rate,
            term_months=args.term_months,
            discount_rate_pct=args.discount_rate,
            interest_type=InterestType(args.interest_type),
            compounding_frequency=CompoundingFrequency(args.compounding),
            simple_lump_sum=args.simple_lump_sum,
            down_payment=args.down_payment,
            wait_months=args.wait_months,
            monthly_early_use_value=args.early_use,
        )
        result = analyze_pc_loan(inputs)
        print(format_text_report(inputs, result))
        return

    from pc_loan_discount.gui import launch_gui

    launch_gui()

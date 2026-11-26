"""PC loan and component price trend discounting application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pc_loan_discount.calculator import analyze_pc_loan, format_text_report
from pc_loan_discount.models import (
    CURRENCY_PROFILES,
    DEFAULT_COMPONENTS,
    AnalysisInputs,
    CompoundingFrequency,
    CurrencyCode,
    ImportTaxConfig,
    InterestType,
    scale_components_for_currency,
)

__version__ = "0.1.0"


def get_version() -> str:
    """Return the package version."""
    return __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pc-loan-discount",
        description="Compare a discounted PC build loan against projected landed component costs.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Print a text analysis report in the terminal instead of opening the desktop GUI.",
    )
    parser.add_argument(
        "--currency",
        choices=[c.value for c in CurrencyCode],
        default=CurrencyCode.ZAR.value,
        help="Currency / locale preset (default: ZAR).",
    )
    parser.add_argument(
        "--no-import-tax",
        action="store_true",
        help="Disable import tax & clearance fees (use if prices already include local VAT).",
    )
    parser.add_argument(
        "--vat-pct",
        type=float,
        default=None,
        help="Override import VAT percentage (default depends on --currency; 15%% for ZAR).",
    )
    parser.add_argument(
        "--uplift-pct",
        type=float,
        default=None,
        help="Override customs ATV uplift percentage (default: 10%% for ZAR, 0%% elsewhere).",
    )
    parser.add_argument(
        "--duty-pct",
        type=float,
        default=None,
        help="Override customs duty percentage (default: 0%%).",
    )
    parser.add_argument(
        "--shipping-fee",
        type=float,
        default=None,
        help="Override flat shipping & customs clearance fee in selected currency.",
    )
    parser.add_argument(
        "--fx-depreciation",
        type=float,
        default=None,
        help="Override annual local currency weakening vs USD in percent (default: 5%% for ZAR).",
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
    parser.add_argument(
        "--loan-rate",
        type=float,
        default=None,
        help="Loan APR in percent (defaults to locale profile, e.g. 15.5%% for ZAR).",
    )
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
        default=None,
        help="Annual discount rate in percent (defaults to locale profile, e.g. 8.5%% for ZAR).",
    )
    parser.add_argument("--down-payment", type=float, default=0.0, help="Upfront down payment.")
    parser.add_argument(
        "--early-use",
        type=float,
        default=0.0,
        help="Optional monthly value of having the PC earlier.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Launch the desktop GUI, or print a CLI report when `--cli` is passed."""
    args = _build_parser().parse_args(argv)
    if args.cli:
        currency = CurrencyCode(args.currency)
        profile = CURRENCY_PROFILES[currency]
        base_tax = profile.default_import_tax
        import_tax = ImportTaxConfig(
            enabled=not args.no_import_tax and base_tax.enabled,
            vat_pct=base_tax.vat_pct if args.vat_pct is None else args.vat_pct,
            customs_uplift_pct=(
                base_tax.customs_uplift_pct if args.uplift_pct is None else args.uplift_pct
            ),
            customs_duty_pct=(
                base_tax.customs_duty_pct if args.duty_pct is None else args.duty_pct
            ),
            shipping_and_clearance_fee=(
                base_tax.shipping_and_clearance_fee
                if args.shipping_fee is None
                else args.shipping_fee
            ),
        )
        inputs = AnalysisInputs(
            components=scale_components_for_currency(DEFAULT_COMPONENTS, currency),
            loan_annual_rate_pct=(
                profile.default_loan_rate_pct if args.loan_rate is None else args.loan_rate
            ),
            term_months=args.term_months,
            discount_rate_pct=(
                profile.default_discount_rate_pct
                if args.discount_rate is None
                else args.discount_rate
            ),
            currency=currency,
            import_tax=import_tax,
            fx_annual_depreciation_pct=(
                profile.default_fx_depreciation_pct
                if args.fx_depreciation is None
                else args.fx_depreciation
            ),
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

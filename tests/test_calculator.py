"""Unit tests for loan discounting, SA import taxes, PC trends, and CLI reporting."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from pc_loan_discount import main
from pc_loan_discount.calculator import (
    analyze_pc_loan,
    compute_import_tax,
    discount_to_present,
    effective_monthly_rate,
    format_text_report,
)
from pc_loan_discount.models import (
    DEFAULT_COMPONENTS,
    MARKET_PRESETS,
    AnalysisInputs,
    ComponentItem,
    CompoundingFrequency,
    CurrencyCode,
    ImportTaxConfig,
    InterestType,
    format_currency,
    scale_components_for_currency,
)

_NO_TAX = ImportTaxConfig(
    enabled=False,
    vat_pct=0.0,
    customs_uplift_pct=0.0,
    customs_duty_pct=0.0,
    shipping_and_clearance_fee=0.0,
)


def _single_part_inputs(
    *,
    price: float = 12000.0,
    trend_pct: float = 0.0,
    loan_rate: float = 12.0,
    term_months: int = 12,
    discount_rate: float = 6.0,
    interest_type: InterestType = InterestType.COMPOUND_AMORTIZED,
    compounding: CompoundingFrequency = CompoundingFrequency.MONTHLY,
    simple_lump_sum: bool = False,
    down_payment: float = 0.0,
    wait_months: int | None = None,
    early_use: float = 0.0,
    currency: CurrencyCode = CurrencyCode.ZAR,
    import_tax: ImportTaxConfig = _NO_TAX,
    fx_depreciation_pct: float = 0.0,
) -> AnalysisInputs:
    return AnalysisInputs(
        components=(ComponentItem(name="PC", current_price=price, annual_trend_pct=trend_pct),),
        loan_annual_rate_pct=loan_rate,
        term_months=term_months,
        discount_rate_pct=discount_rate,
        currency=currency,
        import_tax=import_tax,
        fx_annual_depreciation_pct=fx_depreciation_pct,
        interest_type=interest_type,
        compounding_frequency=compounding,
        simple_lump_sum=simple_lump_sum,
        down_payment=down_payment,
        wait_months=wait_months,
        monthly_early_use_value=early_use,
    )


def test_discount_to_present_exact_one_year() -> None:
    assert discount_to_present(1060.0, annual_discount_rate_pct=6.0, months=12) == pytest.approx(
        1000.0
    )
    assert discount_to_present(500.0, annual_discount_rate_pct=10.0, months=0) == 500.0


def test_sars_import_tax_atv_uplift_and_duty() -> None:
    # SARS standard PC part: 0% duty, 10% ATV uplift, 15% VAT => 16.5% effective tax
    sa_pc_tax = ImportTaxConfig(
        enabled=True,
        vat_pct=15.0,
        customs_uplift_pct=10.0,
        customs_duty_pct=0.0,
        shipping_and_clearance_fee=1200.0,
    )
    assert sa_pc_tax.effective_tax_rate_pct == pytest.approx(16.5)
    assert compute_import_tax(10000.0, sa_pc_tax) == pytest.approx(1650.0)

    # Dutiable item (15% customs duty): ATV = 1.10 + 0.15 = 1.25 => VAT = 18.75%, total = 33.75%
    dutiable = replace(sa_pc_tax, customs_duty_pct=15.0)
    assert dutiable.effective_tax_rate_pct == pytest.approx(33.75)
    assert compute_import_tax(10000.0, dutiable) == pytest.approx(3375.0)


def test_sa_landed_cost_and_fx_weakening_compound_future_price() -> None:
    sa_tax = ImportTaxConfig(
        enabled=True,
        vat_pct=15.0,
        customs_uplift_pct=10.0,
        customs_duty_pct=0.0,
        shipping_and_clearance_fee=1000.0,
    )
    inputs = _single_part_inputs(
        price=20000.0,
        trend_pct=10.0,
        loan_rate=15.0,
        term_months=12,
        discount_rate=8.0,
        import_tax=sa_tax,
        fx_depreciation_pct=6.0,
    )
    result = analyze_pc_loan(inputs)

    assert result.import_tax_today == pytest.approx(3300.0)
    assert result.pc_price_today == pytest.approx(24300.0)
    # Future base = 20000 * 1.10 * 1.06 = 23320; future tax = 16.5% of 23320; future shipping = 1060
    expected_future_base = 20000.0 * 1.10 * 1.06
    expected_future_tax = expected_future_base * 0.165
    expected_future_landed = expected_future_base + expected_future_tax + 1060.0
    assert result.pc_base_price_future_nominal == pytest.approx(expected_future_base)
    assert result.import_tax_future_nominal == pytest.approx(expected_future_tax)
    assert result.pc_price_future_nominal == pytest.approx(expected_future_landed)


def test_simple_interest_monthly_installments() -> None:
    inputs = _single_part_inputs(
        price=1200.0,
        loan_rate=10.0,
        term_months=12,
        discount_rate=0.0,
        interest_type=InterestType.SIMPLE,
        simple_lump_sum=False,
    )
    result = analyze_pc_loan(inputs)

    assert result.total_interest_nominal == pytest.approx(120.0)
    assert result.total_outlay_loan_nominal == pytest.approx(1320.0)
    assert result.monthly_payment == pytest.approx(110.0)
    assert result.pv_loan_option == pytest.approx(1320.0)
    assert result.schedule[-1].remaining_balance == 0.0


def test_simple_interest_lump_sum_discounted() -> None:
    inputs = _single_part_inputs(
        price=1000.0,
        trend_pct=0.0,
        loan_rate=10.0,
        term_months=12,
        discount_rate=10.0,
        interest_type=InterestType.SIMPLE,
        simple_lump_sum=True,
    )
    result = analyze_pc_loan(inputs)

    assert result.monthly_payment == 0.0
    assert result.total_outlay_loan_nominal == pytest.approx(1100.0)
    assert result.pv_loan_option == pytest.approx(1000.0)
    assert all(row.payment == 0.0 for row in result.schedule[:-1])
    assert result.schedule[-1].payment == pytest.approx(1100.0)


def test_compound_amortized_monthly_standard_formula() -> None:
    inputs = _single_part_inputs(
        price=20000.0,
        loan_rate=12.0,
        term_months=24,
        discount_rate=6.0,
        interest_type=InterestType.COMPOUND_AMORTIZED,
        compounding=CompoundingFrequency.MONTHLY,
    )
    result = analyze_pc_loan(inputs)

    r = 0.01
    expected_pmt = 20000.0 * (r * (1.0 + r) ** 24) / ((1.0 + r) ** 24 - 1.0)
    assert result.monthly_payment == pytest.approx(expected_pmt, rel=1e-6)
    assert result.schedule[-1].remaining_balance == pytest.approx(0.0, abs=1e-9)
    assert result.pv_loan_option < result.total_outlay_loan_nominal


def test_compound_lump_sum_quarterly_compounding() -> None:
    inputs = _single_part_inputs(
        price=10000.0,
        loan_rate=12.0,
        term_months=12,
        discount_rate=0.0,
        interest_type=InterestType.COMPOUND_LUMP_SUM,
        compounding=CompoundingFrequency.QUARTERLY,
    )
    result = analyze_pc_loan(inputs)

    expected = 10000.0 * ((1.0 + 0.12 / 4.0) ** 4)
    assert result.total_outlay_loan_nominal == pytest.approx(expected, rel=1e-9)
    assert result.monthly_payment == 0.0


def test_zero_percent_amortized_loan() -> None:
    inputs = _single_part_inputs(
        price=12000.0,
        trend_pct=0.0,
        loan_rate=0.0,
        term_months=12,
        discount_rate=6.0,
        interest_type=InterestType.COMPOUND_AMORTIZED,
    )
    result = analyze_pc_loan(inputs)

    assert result.monthly_payment == pytest.approx(1000.0)
    assert result.total_interest_nominal == pytest.approx(0.0)
    assert result.pv_loan_option < 12000.0


def test_ram_spike_plus_rand_weakening_vs_deflation() -> None:
    rising = AnalysisInputs(
        components=DEFAULT_COMPONENTS,
        loan_annual_rate_pct=15.5,
        term_months=12,
        discount_rate_pct=8.5,
        currency=CurrencyCode.ZAR,
        fx_annual_depreciation_pct=5.0,
        interest_type=InterestType.COMPOUND_AMORTIZED,
    )
    deflating = replace(
        rising,
        components=MARKET_PRESETS[3].components,
        fx_annual_depreciation_pct=0.0,
    )

    rising_res = analyze_pc_loan(rising)
    deflating_res = analyze_pc_loan(deflating)

    assert rising_res.effective_component_cagr_pct > 10.0
    assert rising_res.worth_it is True
    assert rising_res.net_financial_advantage > 0.0

    assert deflating_res.effective_component_cagr_pct < 0.0
    assert deflating_res.worth_it is False
    assert deflating_res.net_financial_advantage < 0.0


def test_break_even_thresholds_reproduce_zero_npv() -> None:
    inputs = AnalysisInputs(
        components=DEFAULT_COMPONENTS,
        loan_annual_rate_pct=15.5,
        term_months=18,
        discount_rate_pct=8.5,
        currency=CurrencyCode.ZAR,
        fx_annual_depreciation_pct=5.0,
        interest_type=InterestType.COMPOUND_AMORTIZED,
    )
    result = analyze_pc_loan(inputs)

    assert result.break_even_loan_rate_pct is not None
    at_be_rate = analyze_pc_loan(
        replace(inputs, loan_annual_rate_pct=result.break_even_loan_rate_pct)
    )
    assert at_be_rate.net_total_advantage == pytest.approx(0.0, abs=1e-3)

    assert result.break_even_component_trend_pct is not None
    uniform_parts = tuple(
        ComponentItem(
            name=item.name,
            current_price=item.current_price,
            annual_trend_pct=result.break_even_component_trend_pct,
        )
        for item in inputs.components
    )
    at_be_trend = analyze_pc_loan(replace(inputs, components=uniform_parts))
    assert at_be_trend.net_total_advantage == pytest.approx(0.0, abs=1e-3)


def test_down_payment_full_cash_and_early_use_value() -> None:
    cash_inputs = _single_part_inputs(
        price=15000.0,
        trend_pct=6.0,
        loan_rate=15.0,
        term_months=12,
        discount_rate=6.0,
        down_payment=15000.0,
        early_use=500.0,
    )
    result = analyze_pc_loan(cash_inputs)

    assert result.loan_principal == 0.0
    assert result.total_interest_nominal == 0.0
    assert result.pv_loan_option == pytest.approx(15000.0)
    assert result.pv_wait_option == pytest.approx(15000.0)
    assert result.net_financial_advantage == pytest.approx(0.0, abs=1e-9)
    assert result.pv_early_use_benefit > 0.0
    assert result.net_total_advantage == pytest.approx(result.pv_early_use_benefit)
    assert result.break_even_loan_rate_pct is None


def test_currency_formatting_and_scaling() -> None:
    assert format_currency(34500.5, CurrencyCode.ZAR) == "R34,500.50"
    assert format_currency(-120.0, CurrencyCode.ZAR, signed=True) == "-R120.00"
    assert format_currency(120.0, CurrencyCode.USD, signed=True) == "+$120.00"
    assert format_currency(-50.0, CurrencyCode.EUR) == "-€50.00"

    usd_parts = scale_components_for_currency(DEFAULT_COMPONENTS, CurrencyCode.USD)
    assert usd_parts[0].current_price < DEFAULT_COMPONENTS[0].current_price
    assert scale_components_for_currency(DEFAULT_COMPONENTS, CurrencyCode.ZAR) == DEFAULT_COMPONENTS


def test_separate_wait_horizon_and_compounding_monotonicity() -> None:
    annual_r = effective_monthly_rate(12.0, CompoundingFrequency.ANNUALLY)
    monthly_r = effective_monthly_rate(12.0, CompoundingFrequency.MONTHLY)
    daily_r = effective_monthly_rate(12.0, CompoundingFrequency.DAILY)
    assert annual_r < monthly_r < daily_r

    inputs = _single_part_inputs(
        price=10000.0,
        trend_pct=20.0,
        loan_rate=10.0,
        term_months=12,
        wait_months=24,
        discount_rate=5.0,
    )
    result = analyze_pc_loan(inputs)
    assert result.wait_months == 24
    assert result.pc_price_future_nominal == pytest.approx(10000.0 * math.pow(1.2, 2.0))


@pytest.mark.parametrize(
    "bad_inputs",
    [
        AnalysisInputs(
            components=(), loan_annual_rate_pct=10.0, term_months=12, discount_rate_pct=5.0
        ),
        _single_part_inputs(price=-10.0),
        _single_part_inputs(trend_pct=-100.0),
        _single_part_inputs(price=1000.0, down_payment=1200.0),
        _single_part_inputs(down_payment=-5.0),
        _single_part_inputs(loan_rate=-1.0),
        _single_part_inputs(term_months=0),
        _single_part_inputs(wait_months=0),
        _single_part_inputs(discount_rate=-100.0),
        _single_part_inputs(early_use=-1.0),
        _single_part_inputs(fx_depreciation_pct=-100.0),
        _single_part_inputs(import_tax=ImportTaxConfig(vat_pct=-1.0)),
        _single_part_inputs(import_tax=ImportTaxConfig(customs_uplift_pct=-1.0)),
        _single_part_inputs(import_tax=ImportTaxConfig(customs_duty_pct=-1.0)),
        _single_part_inputs(import_tax=ImportTaxConfig(shipping_and_clearance_fee=-10.0)),
    ],
)
def test_validation_rejects_invalid_inputs(bad_inputs: AnalysisInputs) -> None:
    with pytest.raises(ValueError):
        analyze_pc_loan(bad_inputs)


def test_cli_report_defaults_to_zar_and_supports_other_currencies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["--cli"])
    zar_out = capsys.readouterr().out
    assert "(ZAR)" in zar_out
    assert "R" in zar_out
    assert "Effective Import Tax:  16.50%" in zar_out

    main(["--cli", "--currency", "USD", "--no-import-tax"])
    usd_out = capsys.readouterr().out
    assert "(USD)" in usd_out
    assert "Effective Import Tax:  0.00%" in usd_out

    sample_inputs = _single_part_inputs()
    report = format_text_report(sample_inputs, analyze_pc_loan(sample_inputs))
    assert "Break-Even Loan APR" in report

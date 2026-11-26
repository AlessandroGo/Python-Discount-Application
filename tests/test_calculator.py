"""Unit tests for loan discounting, PC component price trends, and CLI reporting."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from pc_loan_discount import main
from pc_loan_discount.calculator import (
    analyze_pc_loan,
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
    InterestType,
)


def _single_part_inputs(
    *,
    price: float = 1200.0,
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
) -> AnalysisInputs:
    return AnalysisInputs(
        components=(ComponentItem(name="PC", current_price=price, annual_trend_pct=trend_pct),),
        loan_annual_rate_pct=loan_rate,
        term_months=term_months,
        discount_rate_pct=discount_rate,
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
        price=2000.0,
        loan_rate=12.0,
        term_months=24,
        discount_rate=6.0,
        interest_type=InterestType.COMPOUND_AMORTIZED,
        compounding=CompoundingFrequency.MONTHLY,
    )
    result = analyze_pc_loan(inputs)

    r = 0.01
    expected_pmt = 2000.0 * (r * (1.0 + r) ** 24) / ((1.0 + r) ** 24 - 1.0)
    assert result.monthly_payment == pytest.approx(expected_pmt, rel=1e-6)
    assert result.schedule[-1].remaining_balance == pytest.approx(0.0, abs=1e-9)
    assert result.pv_loan_option < result.total_outlay_loan_nominal


def test_compound_lump_sum_quarterly_compounding() -> None:
    inputs = _single_part_inputs(
        price=1000.0,
        loan_rate=12.0,
        term_months=12,
        discount_rate=0.0,
        interest_type=InterestType.COMPOUND_LUMP_SUM,
        compounding=CompoundingFrequency.QUARTERLY,
    )
    result = analyze_pc_loan(inputs)

    expected = 1000.0 * ((1.0 + 0.12 / 4.0) ** 4)
    assert result.total_outlay_loan_nominal == pytest.approx(expected, rel=1e-9)
    assert result.monthly_payment == 0.0


def test_zero_percent_amortized_loan() -> None:
    inputs = _single_part_inputs(
        price=1200.0,
        trend_pct=0.0,
        loan_rate=0.0,
        term_months=12,
        discount_rate=6.0,
        interest_type=InterestType.COMPOUND_AMORTIZED,
    )
    result = analyze_pc_loan(inputs)

    assert result.monthly_payment == pytest.approx(100.0)
    assert result.total_interest_nominal == pytest.approx(0.0)
    assert result.pv_loan_option < 1200.0


def test_ram_price_spike_makes_moderate_loan_worth_it() -> None:
    rising = AnalysisInputs(
        components=DEFAULT_COMPONENTS,
        loan_annual_rate_pct=10.0,
        term_months=12,
        discount_rate_pct=5.0,
        interest_type=InterestType.COMPOUND_AMORTIZED,
    )
    deflating = replace(rising, components=MARKET_PRESETS[3].components)

    rising_res = analyze_pc_loan(rising)
    deflating_res = analyze_pc_loan(deflating)

    assert rising_res.effective_component_cagr_pct > 0.0
    assert rising_res.worth_it is True
    assert rising_res.net_financial_advantage > 0.0

    assert deflating_res.effective_component_cagr_pct < 0.0
    assert deflating_res.worth_it is False
    assert deflating_res.net_financial_advantage < 0.0


def test_break_even_thresholds_reproduce_zero_npv() -> None:
    inputs = AnalysisInputs(
        components=DEFAULT_COMPONENTS,
        loan_annual_rate_pct=12.0,
        term_months=18,
        discount_rate_pct=6.0,
        interest_type=InterestType.COMPOUND_AMORTIZED,
    )
    result = analyze_pc_loan(inputs)

    assert result.break_even_loan_rate_pct is not None
    at_be_rate = analyze_pc_loan(
        replace(inputs, loan_annual_rate_pct=result.break_even_loan_rate_pct)
    )
    assert at_be_rate.net_total_advantage == pytest.approx(0.0, abs=1e-4)

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
    assert at_be_trend.net_total_advantage == pytest.approx(0.0, abs=1e-4)


def test_down_payment_full_cash_and_early_use_value() -> None:
    cash_inputs = _single_part_inputs(
        price=1500.0,
        trend_pct=6.0,
        loan_rate=15.0,
        term_months=12,
        discount_rate=6.0,
        down_payment=1500.0,
        early_use=25.0,
    )
    result = analyze_pc_loan(cash_inputs)

    assert result.loan_principal == 0.0
    assert result.total_interest_nominal == 0.0
    assert result.pv_loan_option == pytest.approx(1500.0)
    assert result.pv_wait_option == pytest.approx(1500.0)
    assert result.net_financial_advantage == pytest.approx(0.0, abs=1e-9)
    assert result.pv_early_use_benefit > 0.0
    assert result.net_total_advantage == pytest.approx(result.pv_early_use_benefit)
    assert result.break_even_loan_rate_pct is None


def test_separate_wait_horizon_and_compounding_monotonicity() -> None:
    annual_r = effective_monthly_rate(12.0, CompoundingFrequency.ANNUALLY)
    monthly_r = effective_monthly_rate(12.0, CompoundingFrequency.MONTHLY)
    daily_r = effective_monthly_rate(12.0, CompoundingFrequency.DAILY)
    assert annual_r < monthly_r < daily_r

    inputs = _single_part_inputs(
        price=1000.0,
        trend_pct=20.0,
        loan_rate=10.0,
        term_months=12,
        wait_months=24,
        discount_rate=5.0,
    )
    result = analyze_pc_loan(inputs)
    assert result.wait_months == 24
    assert result.pc_price_future_nominal == pytest.approx(1000.0 * math.pow(1.2, 2.0))


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
    ],
)
def test_validation_rejects_invalid_inputs(bad_inputs: AnalysisInputs) -> None:
    with pytest.raises(ValueError):
        analyze_pc_loan(bad_inputs)


def test_cli_report_runs_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--cli", "--loan-rate", "10", "--term-months", "12", "--discount-rate", "5"])
    captured = capsys.readouterr().out
    assert "PC Loan vs. Wait Discount Analysis" in captured
    assert "Verdict:" in captured

    sample_inputs = _single_part_inputs()
    report = format_text_report(sample_inputs, analyze_pc_loan(sample_inputs))
    assert "Break-Even Loan APR" in report

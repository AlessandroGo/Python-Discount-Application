"""Pure financial discounting, import tax, loan schedules, and PC trend valuation engine."""

from __future__ import annotations

from dataclasses import replace

from pc_loan_discount.models import (
    CURRENCY_PROFILES,
    AnalysisInputs,
    AnalysisResult,
    ComponentItem,
    ComponentProjection,
    CompoundingFrequency,
    ImportTaxConfig,
    InterestType,
    MonthlyCashFlow,
    format_currency,
)

_BISECTION_STEPS = 60
_MAX_BREAK_EVEN_RATE_PCT = 500.0
_MIN_BREAK_EVEN_TREND_PCT = -95.0
_MAX_BREAK_EVEN_TREND_PCT = 500.0


def compute_import_tax(base_value: float, config: ImportTaxConfig) -> float:
    """Calculate import tax (customs duty + VAT on uplifted ATV) on a base customs value."""
    if not config.enabled or base_value <= 0.0:
        return 0.0
    duty = base_value * (config.customs_duty_pct / 100.0)
    taxable_value = base_value * (1.0 + config.customs_uplift_pct / 100.0) + duty
    vat = taxable_value * (config.vat_pct / 100.0)
    return duty + vat


def compute_landed_total(
    base_total: float,
    config: ImportTaxConfig,
    *,
    shipping_multiplier: float = 1.0,
) -> tuple[float, float, float]:
    """Return `(import_tax, shipping_fee, landed_total)` for a build's base customs value."""
    if not config.enabled:
        return 0.0, 0.0, base_total
    tax = compute_import_tax(base_total, config)
    shipping = config.shipping_and_clearance_fee * shipping_multiplier
    return tax, shipping, base_total + tax + shipping


def validate_inputs(inputs: AnalysisInputs) -> int:
    """Validate all analysis inputs and return the resolved wait horizon in months."""
    if not inputs.components:
        raise ValueError("At least one PC component is required.")

    for item in inputs.components:
        if not item.name.strip():
            raise ValueError("Every component must have a non-empty name.")
        if item.current_price < 0.0:
            raise ValueError(f"Component '{item.name}' price cannot be negative.")
        if item.annual_trend_pct <= -100.0:
            raise ValueError(f"Component '{item.name}' annual trend must be greater than -100%.")

    tax = inputs.import_tax
    if tax.vat_pct < 0.0:
        raise ValueError("Import VAT percentage cannot be negative.")
    if tax.customs_uplift_pct < 0.0:
        raise ValueError("Customs ATV uplift percentage cannot be negative.")
    if tax.customs_duty_pct < 0.0:
        raise ValueError("Customs duty percentage cannot be negative.")
    if tax.shipping_and_clearance_fee < 0.0:
        raise ValueError("Shipping and clearance fee cannot be negative.")

    if inputs.fx_annual_depreciation_pct <= -100.0:
        raise ValueError("FX annual depreciation rate must be greater than -100%.")

    base_total = sum(item.current_price for item in inputs.components)
    if base_total <= 0.0:
        raise ValueError("Total PC build price must be greater than 0.")

    _, _, landed_today = compute_landed_total(base_total, tax)
    if inputs.down_payment < 0.0:
        raise ValueError("Down payment cannot be negative.")
    if inputs.down_payment > landed_today:
        raise ValueError("Down payment cannot exceed the landed PC build price.")
    if inputs.loan_annual_rate_pct < 0.0:
        raise ValueError("Loan interest rate cannot be negative.")
    if inputs.term_months < 1:
        raise ValueError("Loan term must be at least 1 month.")
    if inputs.discount_rate_pct <= -100.0:
        raise ValueError("Discount rate must be greater than -100%.")
    if inputs.monthly_early_use_value < 0.0:
        raise ValueError("Monthly early-use value cannot be negative.")

    wait_months = inputs.term_months if inputs.wait_months is None else inputs.wait_months
    if wait_months < 1:
        raise ValueError("Wait horizon must be at least 1 month.")
    return wait_months


def discount_to_present(amount: float, annual_discount_rate_pct: float, months: int) -> float:
    """Discount a future cash flow occurring at `months` back to present value."""
    if months <= 0 or amount == 0.0:
        return amount
    annual_rate = annual_discount_rate_pct / 100.0
    factor = (1.0 + annual_rate) ** (months / 12.0)
    return amount / factor


def effective_monthly_rate(
    annual_rate_pct: float,
    compounding: CompoundingFrequency,
) -> float:
    """Convert a nominal annual rate and compounding frequency to an effective monthly rate."""
    nominal = annual_rate_pct / 100.0
    if nominal == 0.0:
        return 0.0
    periods = compounding.periods_per_year
    effective_annual = (1.0 + nominal / periods) ** periods - 1.0
    return float((1.0 + effective_annual) ** (1.0 / 12.0) - 1.0)


def build_loan_schedule(
    principal: float,
    loan_annual_rate_pct: float,
    term_months: int,
    discount_rate_pct: float,
    interest_type: InterestType,
    compounding_frequency: CompoundingFrequency,
    simple_lump_sum: bool = False,
) -> tuple[MonthlyCashFlow, ...]:
    """Generate the month-by-month repayment and discounted cash-flow schedule."""
    if principal == 0.0:
        return tuple(
            MonthlyCashFlow(
                month=month,
                payment=0.0,
                interest_portion=0.0,
                principal_portion=0.0,
                remaining_balance=0.0,
                present_value=0.0,
            )
            for month in range(1, term_months + 1)
        )

    if interest_type == InterestType.SIMPLE:
        return _build_simple_schedule(
            principal=principal,
            loan_annual_rate_pct=loan_annual_rate_pct,
            term_months=term_months,
            discount_rate_pct=discount_rate_pct,
            lump_sum=simple_lump_sum,
        )

    if interest_type == InterestType.COMPOUND_AMORTIZED:
        return _build_compound_amortized_schedule(
            principal=principal,
            loan_annual_rate_pct=loan_annual_rate_pct,
            term_months=term_months,
            discount_rate_pct=discount_rate_pct,
            compounding_frequency=compounding_frequency,
        )

    return _build_compound_lump_sum_schedule(
        principal=principal,
        loan_annual_rate_pct=loan_annual_rate_pct,
        term_months=term_months,
        discount_rate_pct=discount_rate_pct,
        compounding_frequency=compounding_frequency,
    )


def _build_simple_schedule(
    principal: float,
    loan_annual_rate_pct: float,
    term_months: int,
    discount_rate_pct: float,
    lump_sum: bool,
) -> tuple[MonthlyCashFlow, ...]:
    years = term_months / 12.0
    total_interest = principal * (loan_annual_rate_pct / 100.0) * years
    total_repayment = principal + total_interest

    rows: list[MonthlyCashFlow] = []
    if lump_sum:
        for month in range(1, term_months + 1):
            if month < term_months:
                rows.append(
                    MonthlyCashFlow(
                        month=month,
                        payment=0.0,
                        interest_portion=0.0,
                        principal_portion=0.0,
                        remaining_balance=principal,
                        present_value=0.0,
                    )
                )
            else:
                rows.append(
                    MonthlyCashFlow(
                        month=month,
                        payment=total_repayment,
                        interest_portion=total_interest,
                        principal_portion=principal,
                        remaining_balance=0.0,
                        present_value=discount_to_present(
                            total_repayment, discount_rate_pct, month
                        ),
                    )
                )
        return tuple(rows)

    monthly_payment = total_repayment / term_months
    monthly_interest = total_interest / term_months
    monthly_principal = principal / term_months
    balance = principal
    for month in range(1, term_months + 1):
        balance = max(0.0, balance - monthly_principal)
        if month == term_months:
            balance = 0.0
        rows.append(
            MonthlyCashFlow(
                month=month,
                payment=monthly_payment,
                interest_portion=monthly_interest,
                principal_portion=monthly_principal,
                remaining_balance=balance,
                present_value=discount_to_present(monthly_payment, discount_rate_pct, month),
            )
        )
    return tuple(rows)


def _build_compound_amortized_schedule(
    principal: float,
    loan_annual_rate_pct: float,
    term_months: int,
    discount_rate_pct: float,
    compounding_frequency: CompoundingFrequency,
) -> tuple[MonthlyCashFlow, ...]:
    monthly_rate = effective_monthly_rate(loan_annual_rate_pct, compounding_frequency)
    if monthly_rate == 0.0:
        payment = principal / term_months
    else:
        growth = (1.0 + monthly_rate) ** term_months
        payment = principal * (monthly_rate * growth) / (growth - 1.0)

    rows: list[MonthlyCashFlow] = []
    balance = principal
    for month in range(1, term_months + 1):
        interest = balance * monthly_rate
        if month == term_months:
            principal_paid = balance
            actual_payment = principal_paid + interest
            balance = 0.0
        else:
            principal_paid = payment - interest
            actual_payment = payment
            balance = max(0.0, balance - principal_paid)
        rows.append(
            MonthlyCashFlow(
                month=month,
                payment=actual_payment,
                interest_portion=interest,
                principal_portion=principal_paid,
                remaining_balance=balance,
                present_value=discount_to_present(actual_payment, discount_rate_pct, month),
            )
        )
    return tuple(rows)


def _build_compound_lump_sum_schedule(
    principal: float,
    loan_annual_rate_pct: float,
    term_months: int,
    discount_rate_pct: float,
    compounding_frequency: CompoundingFrequency,
) -> tuple[MonthlyCashFlow, ...]:
    monthly_rate = effective_monthly_rate(loan_annual_rate_pct, compounding_frequency)
    years = term_months / 12.0
    periods = compounding_frequency.periods_per_year
    maturity_amount = principal * (
        (1.0 + (loan_annual_rate_pct / 100.0) / periods) ** (periods * years)
    )
    total_interest = maturity_amount - principal

    rows: list[MonthlyCashFlow] = []
    accrued_balance = principal
    for month in range(1, term_months + 1):
        if month < term_months:
            accrued_balance *= 1.0 + monthly_rate
            rows.append(
                MonthlyCashFlow(
                    month=month,
                    payment=0.0,
                    interest_portion=0.0,
                    principal_portion=0.0,
                    remaining_balance=accrued_balance,
                    present_value=0.0,
                )
            )
        else:
            rows.append(
                MonthlyCashFlow(
                    month=month,
                    payment=maturity_amount,
                    interest_portion=total_interest,
                    principal_portion=principal,
                    remaining_balance=0.0,
                    present_value=discount_to_present(maturity_amount, discount_rate_pct, month),
                )
            )
    return tuple(rows)


def project_components(
    components: tuple[ComponentItem, ...],
    wait_months: int,
    discount_rate_pct: float,
    import_tax: ImportTaxConfig,
    fx_annual_depreciation_pct: float,
) -> tuple[ComponentProjection, ...]:
    """Project each component's future base, landed (post-tax), and discounted prices."""
    years = wait_months / 12.0
    fx_factor = (1.0 + fx_annual_depreciation_pct / 100.0) ** years
    projections: list[ComponentProjection] = []
    for item in components:
        landed_today = item.current_price + compute_import_tax(item.current_price, import_tax)
        future_base = (
            item.current_price * ((1.0 + item.annual_trend_pct / 100.0) ** years) * fx_factor
        )
        future_landed = future_base + compute_import_tax(future_base, import_tax)
        discounted = discount_to_present(future_landed, discount_rate_pct, wait_months)
        projections.append(
            ComponentProjection(
                name=item.name,
                base_price_today=item.current_price,
                landed_price_today=landed_today,
                annual_trend_pct=item.annual_trend_pct,
                projected_base_price=future_base,
                projected_landed_price=future_landed,
                price_change=future_landed - landed_today,
                discounted_future_price=discounted,
            )
        )
    return tuple(projections)


def _evaluate_net_advantage(inputs: AnalysisInputs) -> float:
    """Fast helper computing net total advantage without recursive break-even solves."""
    wait_months = validate_inputs(inputs)
    years = wait_months / 12.0
    fx_factor = (1.0 + inputs.fx_annual_depreciation_pct / 100.0) ** years

    base_today = sum(item.current_price for item in inputs.components)
    _, _, landed_today = compute_landed_total(base_today, inputs.import_tax)
    principal = landed_today - inputs.down_payment

    schedule = build_loan_schedule(
        principal=principal,
        loan_annual_rate_pct=inputs.loan_annual_rate_pct,
        term_months=inputs.term_months,
        discount_rate_pct=inputs.discount_rate_pct,
        interest_type=inputs.interest_type,
        compounding_frequency=inputs.compounding_frequency,
        simple_lump_sum=inputs.simple_lump_sum,
    )
    pv_loan_option = inputs.down_payment + sum(row.present_value for row in schedule)

    projections = project_components(
        inputs.components,
        wait_months,
        inputs.discount_rate_pct,
        inputs.import_tax,
        inputs.fx_annual_depreciation_pct,
    )
    future_base_total = sum(proj.projected_base_price for proj in projections)
    _, _, future_landed_total = compute_landed_total(
        future_base_total,
        inputs.import_tax,
        shipping_multiplier=fx_factor,
    )
    pv_wait_option = discount_to_present(future_landed_total, inputs.discount_rate_pct, wait_months)

    pv_early_use = sum(
        discount_to_present(inputs.monthly_early_use_value, inputs.discount_rate_pct, month)
        for month in range(1, wait_months + 1)
    )
    return (pv_wait_option - pv_loan_option) + pv_early_use


def find_break_even_loan_rate(inputs: AnalysisInputs) -> float | None:
    """Return the loan APR (%) where taking the loan breaks even with waiting, if in [0, 500]%."""
    base_today = sum(item.current_price for item in inputs.components)
    _, _, landed_today = compute_landed_total(base_today, inputs.import_tax)
    if landed_today - inputs.down_payment <= 0.0:
        return None

    low = 0.0
    high = _MAX_BREAK_EVEN_RATE_PCT
    val_low = _evaluate_net_advantage(replace(inputs, loan_annual_rate_pct=low))
    val_high = _evaluate_net_advantage(replace(inputs, loan_annual_rate_pct=high))

    if val_low < 0.0 or val_high > 0.0:
        return None

    for _ in range(_BISECTION_STEPS):
        mid = (low + high) / 2.0
        val_mid = _evaluate_net_advantage(replace(inputs, loan_annual_rate_pct=mid))
        if val_mid >= 0.0:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def find_break_even_component_trend(inputs: AnalysisInputs) -> float | None:
    """Return the uniform global annual PC price trend (%) needed for the loan to break even."""

    def with_uniform_trend(trend_pct: float) -> AnalysisInputs:
        uniform = tuple(
            ComponentItem(
                name=item.name,
                current_price=item.current_price,
                annual_trend_pct=trend_pct,
            )
            for item in inputs.components
        )
        return replace(inputs, components=uniform)

    low = _MIN_BREAK_EVEN_TREND_PCT
    high = _MAX_BREAK_EVEN_TREND_PCT
    val_low = _evaluate_net_advantage(with_uniform_trend(low))
    val_high = _evaluate_net_advantage(with_uniform_trend(high))

    if val_low > 0.0 or val_high < 0.0:
        return None

    for _ in range(_BISECTION_STEPS):
        mid = (low + high) / 2.0
        val_mid = _evaluate_net_advantage(with_uniform_trend(mid))
        if val_mid <= 0.0:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def analyze_pc_loan(inputs: AnalysisInputs) -> AnalysisResult:
    """Run the complete discounted loan vs. future landed PC cost analysis."""
    wait_months = validate_inputs(inputs)
    years = wait_months / 12.0
    fx_factor = (1.0 + inputs.fx_annual_depreciation_pct / 100.0) ** years

    pc_base_price_today = sum(item.current_price for item in inputs.components)
    import_tax_today, shipping_today, pc_price_today = compute_landed_total(
        pc_base_price_today,
        inputs.import_tax,
    )
    principal = pc_price_today - inputs.down_payment

    schedule = build_loan_schedule(
        principal=principal,
        loan_annual_rate_pct=inputs.loan_annual_rate_pct,
        term_months=inputs.term_months,
        discount_rate_pct=inputs.discount_rate_pct,
        interest_type=inputs.interest_type,
        compounding_frequency=inputs.compounding_frequency,
        simple_lump_sum=inputs.simple_lump_sum,
    )

    total_loan_payments_nominal = sum(row.payment for row in schedule)
    total_interest_nominal = total_loan_payments_nominal - principal
    total_outlay_loan_nominal = inputs.down_payment + total_loan_payments_nominal
    pv_loan_option = inputs.down_payment + sum(row.present_value for row in schedule)

    is_lump_sum = inputs.interest_type == InterestType.COMPOUND_LUMP_SUM or (
        inputs.interest_type == InterestType.SIMPLE and inputs.simple_lump_sum
    )
    monthly_payment = 0.0 if is_lump_sum else schedule[0].payment

    projections = project_components(
        inputs.components,
        wait_months,
        inputs.discount_rate_pct,
        inputs.import_tax,
        inputs.fx_annual_depreciation_pct,
    )
    pc_base_price_future_nominal = sum(proj.projected_base_price for proj in projections)
    import_tax_future_nominal, shipping_future_nominal, pc_price_future_nominal = (
        compute_landed_total(
            pc_base_price_future_nominal,
            inputs.import_tax,
            shipping_multiplier=fx_factor,
        )
    )
    pv_wait_option = discount_to_present(
        pc_price_future_nominal,
        inputs.discount_rate_pct,
        wait_months,
    )

    pv_early_use_benefit = sum(
        discount_to_present(inputs.monthly_early_use_value, inputs.discount_rate_pct, month)
        for month in range(1, wait_months + 1)
    )

    net_financial_advantage = pv_wait_option - pv_loan_option
    net_total_advantage = net_financial_advantage + pv_early_use_benefit
    nominal_savings_vs_waiting = pc_price_future_nominal - total_outlay_loan_nominal

    effective_component_cagr_pct = (
        (pc_price_future_nominal / pc_price_today) ** (1.0 / years) - 1.0
    ) * 100.0

    break_even_loan_rate_pct = find_break_even_loan_rate(inputs)
    break_even_component_trend_pct = find_break_even_component_trend(inputs)
    symbol = CURRENCY_PROFILES[inputs.currency].symbol

    return AnalysisResult(
        currency=inputs.currency,
        currency_symbol=symbol,
        pc_base_price_today=pc_base_price_today,
        import_tax_today=import_tax_today,
        shipping_today=shipping_today,
        pc_price_today=pc_price_today,
        down_payment=inputs.down_payment,
        loan_principal=principal,
        term_months=inputs.term_months,
        wait_months=wait_months,
        monthly_payment=monthly_payment,
        total_loan_payments_nominal=total_loan_payments_nominal,
        total_interest_nominal=total_interest_nominal,
        total_outlay_loan_nominal=total_outlay_loan_nominal,
        pv_loan_option=pv_loan_option,
        pc_base_price_future_nominal=pc_base_price_future_nominal,
        import_tax_future_nominal=import_tax_future_nominal,
        shipping_future_nominal=shipping_future_nominal,
        pc_price_future_nominal=pc_price_future_nominal,
        pv_wait_option=pv_wait_option,
        pv_early_use_benefit=pv_early_use_benefit,
        net_financial_advantage=net_financial_advantage,
        net_total_advantage=net_total_advantage,
        nominal_savings_vs_waiting=nominal_savings_vs_waiting,
        effective_component_cagr_pct=effective_component_cagr_pct,
        effective_import_tax_rate_pct=inputs.import_tax.effective_tax_rate_pct,
        break_even_loan_rate_pct=break_even_loan_rate_pct,
        break_even_component_trend_pct=break_even_component_trend_pct,
        worth_it=net_total_advantage > 0.0,
        component_projections=projections,
        schedule=schedule,
    )


def format_text_report(inputs: AnalysisInputs, result: AnalysisResult) -> str:
    """Render a concise plain-text summary report for CLI output or export."""
    cur = result.currency
    verdict = "WORTH IT" if result.worth_it else "NOT WORTH IT"
    be_rate = (
        f"{result.break_even_loan_rate_pct:.2f}%"
        if result.break_even_loan_rate_pct is not None
        else "N/A"
    )
    be_trend = (
        f"{result.break_even_component_trend_pct:+.2f}%/yr"
        if result.break_even_component_trend_pct is not None
        else "N/A"
    )

    interest_desc = f"{inputs.interest_type.value} ({inputs.loan_annual_rate_pct:.2f}% APR)"
    npv_text = format_currency(result.net_total_advantage, cur, signed=True)
    fin_text = format_currency(result.net_financial_advantage, cur, signed=True)

    lines = [
        f"=== PC Loan vs. Wait Discount Analysis ({cur.value}) ===",
        f"Verdict: {verdict} ({npv_text} Net Present Value)",
        f"  Interest Type:         {interest_desc}",
        f"  Loan Term / Wait:      {result.term_months} mo / {result.wait_months} mo",
        f"  Discount Rate:         {inputs.discount_rate_pct:.2f}%/yr",
        f"  FX Weakening Rate:     {inputs.fx_annual_depreciation_pct:+.2f}%/yr",
        f"  Effective Import Tax:  {result.effective_import_tax_rate_pct:.2f}%",
        "",
        "--- Buy Now with Loan ---",
        f"  Base PC Cost Today:    {format_currency(result.pc_base_price_today, cur)}",
        f"  Import Tax Today:      {format_currency(result.import_tax_today, cur)}",
        f"  Shipping & Clearance:  {format_currency(result.shipping_today, cur)}",
        f"  Landed PC Cost Today:  {format_currency(result.pc_price_today, cur)}",
        (
            f"  Down Payment / Loan:   {format_currency(result.down_payment, cur)} / "
            f"{format_currency(result.loan_principal, cur)}"
        ),
        f"  Monthly Payment:       {format_currency(result.monthly_payment, cur)}",
        f"  Total Interest:        {format_currency(result.total_interest_nominal, cur)}",
        f"  Total Nominal Outlay:  {format_currency(result.total_outlay_loan_nominal, cur)}",
        f"  Discounted Cost (PV):  {format_currency(result.pv_loan_option, cur)}",
        "",
        "--- Wait & Buy Later ---",
        f"  Effective Local Trend: {result.effective_component_cagr_pct:+.2f}%/yr",
        f"  Future Base Cost:      {format_currency(result.pc_base_price_future_nominal, cur)}",
        f"  Future Import Tax:     {format_currency(result.import_tax_future_nominal, cur)}",
        f"  Future Shipping:       {format_currency(result.shipping_future_nominal, cur)}",
        f"  Future Landed Cost:    {format_currency(result.pc_price_future_nominal, cur)}",
        f"  Discounted Cost (PV):  {format_currency(result.pv_wait_option, cur)}",
        f"  Early-Use Value (PV):  {format_currency(result.pv_early_use_benefit, cur)}",
        "",
        "--- Decision Thresholds ---",
        f"  Financial NPV Diff:    {fin_text}",
        f"  Total NPV Diff:        {npv_text}",
        f"  Break-Even Loan APR:   {be_rate}",
        f"  Break-Even Global %:   {be_trend}",
    ]
    return "\n".join(lines)

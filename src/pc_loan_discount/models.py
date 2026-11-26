"""Domain models, regional currency/tax presets, and PC market trend presets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InterestType(StrEnum):
    """Supported loan interest calculation methods."""

    SIMPLE = "simple"
    COMPOUND_AMORTIZED = "compound_amortized"
    COMPOUND_LUMP_SUM = "compound_lump_sum"


class CompoundingFrequency(StrEnum):
    """Compounding frequency for compound-interest loans."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUALLY = "semi_annually"
    ANNUALLY = "annually"
    DAILY = "daily"

    @property
    def periods_per_year(self) -> int:
        """Number of compounding periods per year."""
        mapping: dict[CompoundingFrequency, int] = {
            CompoundingFrequency.MONTHLY: 12,
            CompoundingFrequency.QUARTERLY: 4,
            CompoundingFrequency.SEMI_ANNUALLY: 2,
            CompoundingFrequency.ANNUALLY: 1,
            CompoundingFrequency.DAILY: 365,
        }
        return mapping[self]


class CurrencyCode(StrEnum):
    """Supported display and pricing currencies."""

    ZAR = "ZAR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


@dataclass(frozen=True, slots=True)
class ImportTaxConfig:
    """Import tax, customs uplift (e.g. SARS 10% ATV), and shipping/clearance rules.

    Formula applied to base component price `P`:
      - customs_duty = P * (customs_duty_pct / 100)
      - taxable_value (ATV) = P * (1 + customs_uplift_pct / 100) + customs_duty
      - vat = taxable_value * (vat_pct / 100)
      - landed_cost = P + customs_duty + vat + shipping_and_clearance_fee
    """

    enabled: bool = True
    vat_pct: float = 15.0
    customs_uplift_pct: float = 10.0
    customs_duty_pct: float = 0.0
    shipping_and_clearance_fee: float = 1200.0

    @property
    def effective_tax_rate_pct(self) -> float:
        """Combined percentage added on top of base value (excluding flat shipping/clearance)."""
        if not self.enabled:
            return 0.0
        duty = self.customs_duty_pct / 100.0
        uplift = self.customs_uplift_pct / 100.0
        vat = self.vat_pct / 100.0
        total_rate = duty + vat * (1.0 + uplift + duty)
        return total_rate * 100.0


@dataclass(frozen=True, slots=True)
class CurrencyProfile:
    """Locale defaults for currency symbol, import tax rules, rates, and typical prices."""

    code: CurrencyCode
    name: str
    symbol: str
    zar_per_unit: float
    default_loan_rate_pct: float
    default_discount_rate_pct: float
    default_fx_depreciation_pct: float
    default_import_tax: ImportTaxConfig
    tax_note: str


CURRENCY_PROFILES: dict[CurrencyCode, CurrencyProfile] = {
    CurrencyCode.ZAR: CurrencyProfile(
        code=CurrencyCode.ZAR,
        name="South African Rand (ZAR)",
        symbol="R",
        zar_per_unit=1.0,
        default_loan_rate_pct=15.5,
        default_discount_rate_pct=8.5,
        default_fx_depreciation_pct=5.0,
        default_import_tax=ImportTaxConfig(
            enabled=True,
            vat_pct=15.0,
            customs_uplift_pct=10.0,
            customs_duty_pct=0.0,
            shipping_and_clearance_fee=1200.0,
        ),
        tax_note=(
            "SARS import tax: 15% VAT on 110% ATV (16.5% effective on 0%-duty PC parts) "
            "+ optional customs duty + courier clearance/shipping."
        ),
    ),
    CurrencyCode.USD: CurrencyProfile(
        code=CurrencyCode.USD,
        name="US Dollar (USD)",
        symbol="$",
        zar_per_unit=18.5,
        default_loan_rate_pct=12.0,
        default_discount_rate_pct=5.0,
        default_fx_depreciation_pct=0.0,
        default_import_tax=ImportTaxConfig(
            enabled=True,
            vat_pct=8.0,
            customs_uplift_pct=0.0,
            customs_duty_pct=0.0,
            shipping_and_clearance_fee=0.0,
        ),
        tax_note="Typical US state sales tax (~8%) with no customs uplift.",
    ),
    CurrencyCode.EUR: CurrencyProfile(
        code=CurrencyCode.EUR,
        name="Euro (EUR)",
        symbol="€",
        zar_per_unit=20.0,
        default_loan_rate_pct=9.5,
        default_discount_rate_pct=4.0,
        default_fx_depreciation_pct=0.0,
        default_import_tax=ImportTaxConfig(
            enabled=True,
            vat_pct=20.0,
            customs_uplift_pct=0.0,
            customs_duty_pct=0.0,
            shipping_and_clearance_fee=25.0,
        ),
        tax_note="Standard EU import VAT (~20%) + courier handling.",
    ),
    CurrencyCode.GBP: CurrencyProfile(
        code=CurrencyCode.GBP,
        name="British Pound (GBP)",
        symbol="£",
        zar_per_unit=23.5,
        default_loan_rate_pct=10.5,
        default_discount_rate_pct=4.5,
        default_fx_depreciation_pct=0.0,
        default_import_tax=ImportTaxConfig(
            enabled=True,
            vat_pct=20.0,
            customs_uplift_pct=0.0,
            customs_duty_pct=0.0,
            shipping_and_clearance_fee=20.0,
        ),
        tax_note="Standard UK import VAT (20%) + courier handling.",
    ),
}


@dataclass(frozen=True, slots=True)
class ComponentItem:
    """A single PC build component with base price and expected annual USD/global trend."""

    name: str
    current_price: float
    annual_trend_pct: float


@dataclass(frozen=True, slots=True)
class MarketPreset:
    """Named preset of realistic PC component prices (in ZAR) and annual trend assumptions."""

    name: str
    description: str
    components: tuple[ComponentItem, ...]


@dataclass(frozen=True, slots=True)
class AnalysisInputs:
    """Inputs for comparing a financed PC build now vs. waiting to buy later."""

    components: tuple[ComponentItem, ...]
    loan_annual_rate_pct: float
    term_months: int
    discount_rate_pct: float
    currency: CurrencyCode = CurrencyCode.ZAR
    import_tax: ImportTaxConfig = ImportTaxConfig()
    fx_annual_depreciation_pct: float = 5.0
    interest_type: InterestType = InterestType.COMPOUND_AMORTIZED
    compounding_frequency: CompoundingFrequency = CompoundingFrequency.MONTHLY
    simple_lump_sum: bool = False
    down_payment: float = 0.0
    wait_months: int | None = None
    monthly_early_use_value: float = 0.0


@dataclass(frozen=True, slots=True)
class ComponentProjection:
    """Projected nominal and discounted future cost for one PC component."""

    name: str
    base_price_today: float
    landed_price_today: float
    annual_trend_pct: float
    projected_base_price: float
    projected_landed_price: float
    price_change: float
    discounted_future_price: float


@dataclass(frozen=True, slots=True)
class MonthlyCashFlow:
    """Single month entry in the loan repayment and discounting schedule."""

    month: int
    payment: float
    interest_portion: float
    principal_portion: float
    remaining_balance: float
    present_value: float


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Full comparison output answering whether taking a PC loan is net worth it."""

    currency: CurrencyCode
    currency_symbol: str
    pc_base_price_today: float
    import_tax_today: float
    shipping_today: float
    pc_price_today: float
    down_payment: float
    loan_principal: float
    term_months: int
    wait_months: int
    monthly_payment: float
    total_loan_payments_nominal: float
    total_interest_nominal: float
    total_outlay_loan_nominal: float
    pv_loan_option: float
    pc_base_price_future_nominal: float
    import_tax_future_nominal: float
    shipping_future_nominal: float
    pc_price_future_nominal: float
    pv_wait_option: float
    pv_early_use_benefit: float
    net_financial_advantage: float
    net_total_advantage: float
    nominal_savings_vs_waiting: float
    effective_component_cagr_pct: float
    effective_import_tax_rate_pct: float
    break_even_loan_rate_pct: float | None
    break_even_component_trend_pct: float | None
    worth_it: bool
    component_projections: tuple[ComponentProjection, ...]
    schedule: tuple[MonthlyCashFlow, ...]


def format_currency(amount: float, currency: CurrencyCode, *, signed: bool = False) -> str:
    """Format a monetary value using the locale currency symbol (e.g. R34,500.00)."""
    symbol = CURRENCY_PROFILES[currency].symbol
    if signed:
        prefix = "+" if amount >= 0.0 else "-"
        return f"{prefix}{symbol}{abs(amount):,.2f}"
    if amount < 0.0:
        return f"-{symbol}{abs(amount):,.2f}"
    return f"{symbol}{amount:,.2f}"


def scale_components_for_currency(
    components: tuple[ComponentItem, ...],
    currency: CurrencyCode,
) -> tuple[ComponentItem, ...]:
    """Scale ZAR-denominated preset prices cleanly into the selected currency."""
    divisor = CURRENCY_PROFILES[currency].zar_per_unit
    if divisor == 1.0:
        return components
    return tuple(
        ComponentItem(
            name=item.name,
            current_price=round(item.current_price / divisor, 0),
            annual_trend_pct=item.annual_trend_pct,
        )
        for item in components
    )


DEFAULT_COMPONENTS: tuple[ComponentItem, ...] = (
    ComponentItem(name="RAM (DDR5 32GB)", current_price=3200.0, annual_trend_pct=25.0),
    ComponentItem(name="GPU", current_price=14500.0, annual_trend_pct=12.0),
    ComponentItem(name="CPU", current_price=6500.0, annual_trend_pct=-3.0),
    ComponentItem(name="NVMe SSD (2TB)", current_price=2900.0, annual_trend_pct=15.0),
    ComponentItem(name="Motherboard / PSU / Case", current_price=7400.0, annual_trend_pct=3.0),
)


MARKET_PRESETS: tuple[MarketPreset, ...] = (
    MarketPreset(
        name="RAM & AI Supply Squeeze",
        description="Tight DRAM/NAND and GPU supply pushing memory and graphics prices up.",
        components=DEFAULT_COMPONENTS,
    ),
    MarketPreset(
        name="Severe RAM & GPU Spike",
        description="Sharp shortage scenario for memory, storage, and graphics cards.",
        components=(
            ComponentItem(name="RAM (DDR5 32GB)", current_price=3200.0, annual_trend_pct=38.0),
            ComponentItem(name="GPU", current_price=14500.0, annual_trend_pct=25.0),
            ComponentItem(name="CPU", current_price=6500.0, annual_trend_pct=5.0),
            ComponentItem(name="NVMe SSD (2TB)", current_price=2900.0, annual_trend_pct=22.0),
            ComponentItem(
                name="Motherboard / PSU / Case", current_price=7400.0, annual_trend_pct=5.0
            ),
        ),
    ),
    MarketPreset(
        name="Moderate Inflation",
        description="Steady single-digit hardware price drift across components.",
        components=(
            ComponentItem(name="RAM (DDR5 32GB)", current_price=3200.0, annual_trend_pct=8.0),
            ComponentItem(name="GPU", current_price=14500.0, annual_trend_pct=6.0),
            ComponentItem(name="CPU", current_price=6500.0, annual_trend_pct=2.0),
            ComponentItem(name="NVMe SSD (2TB)", current_price=2900.0, annual_trend_pct=5.0),
            ComponentItem(
                name="Motherboard / PSU / Case", current_price=7400.0, annual_trend_pct=3.0
            ),
        ),
    ),
    MarketPreset(
        name="Normal Hardware Deflation",
        description="Typical tech depreciation where waiting buys the same tier for less.",
        components=(
            ComponentItem(name="RAM (DDR5 32GB)", current_price=3200.0, annual_trend_pct=-8.0),
            ComponentItem(name="GPU", current_price=14500.0, annual_trend_pct=-10.0),
            ComponentItem(name="CPU", current_price=6500.0, annual_trend_pct=-10.0),
            ComponentItem(name="NVMe SSD (2TB)", current_price=2900.0, annual_trend_pct=-12.0),
            ComponentItem(
                name="Motherboard / PSU / Case", current_price=7400.0, annual_trend_pct=-2.0
            ),
        ),
    ),
    MarketPreset(
        name="Flat Prices (0% Trend)",
        description="No global component price changes; isolates loan interest, FX, and taxes.",
        components=(
            ComponentItem(name="RAM (DDR5 32GB)", current_price=3200.0, annual_trend_pct=0.0),
            ComponentItem(name="GPU", current_price=14500.0, annual_trend_pct=0.0),
            ComponentItem(name="CPU", current_price=6500.0, annual_trend_pct=0.0),
            ComponentItem(name="NVMe SSD (2TB)", current_price=2900.0, annual_trend_pct=0.0),
            ComponentItem(
                name="Motherboard / PSU / Case", current_price=7400.0, annual_trend_pct=0.0
            ),
        ),
    ),
)

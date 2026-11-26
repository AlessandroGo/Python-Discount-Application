"""Domain models and PC hardware market presets for loan vs. wait analysis."""

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


@dataclass(frozen=True, slots=True)
class ComponentItem:
    """A single PC build component with current cost and expected annual price trend."""

    name: str
    current_price: float
    annual_trend_pct: float


@dataclass(frozen=True, slots=True)
class MarketPreset:
    """Named preset of realistic PC component prices and annual trend assumptions."""

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
    current_price: float
    annual_trend_pct: float
    projected_future_price: float
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
    pc_price_future_nominal: float
    pv_wait_option: float
    pv_early_use_benefit: float
    net_financial_advantage: float
    net_total_advantage: float
    nominal_savings_vs_waiting: float
    effective_component_cagr_pct: float
    break_even_loan_rate_pct: float | None
    break_even_component_trend_pct: float | None
    worth_it: bool
    component_projections: tuple[ComponentProjection, ...]
    schedule: tuple[MonthlyCashFlow, ...]


DEFAULT_COMPONENTS: tuple[ComponentItem, ...] = (
    ComponentItem(name="RAM (DDR5 32GB)", current_price=160.0, annual_trend_pct=25.0),
    ComponentItem(name="GPU", current_price=750.0, annual_trend_pct=12.0),
    ComponentItem(name="CPU", current_price=350.0, annual_trend_pct=-3.0),
    ComponentItem(name="NVMe SSD (2TB)", current_price=160.0, annual_trend_pct=15.0),
    ComponentItem(name="Motherboard / PSU / Case", current_price=380.0, annual_trend_pct=3.0),
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
            ComponentItem(name="RAM (DDR5 32GB)", current_price=160.0, annual_trend_pct=38.0),
            ComponentItem(name="GPU", current_price=750.0, annual_trend_pct=25.0),
            ComponentItem(name="CPU", current_price=350.0, annual_trend_pct=5.0),
            ComponentItem(name="NVMe SSD (2TB)", current_price=160.0, annual_trend_pct=22.0),
            ComponentItem(
                name="Motherboard / PSU / Case", current_price=380.0, annual_trend_pct=5.0
            ),
        ),
    ),
    MarketPreset(
        name="Moderate Inflation",
        description="Steady single-digit hardware price drift across components.",
        components=(
            ComponentItem(name="RAM (DDR5 32GB)", current_price=160.0, annual_trend_pct=8.0),
            ComponentItem(name="GPU", current_price=750.0, annual_trend_pct=6.0),
            ComponentItem(name="CPU", current_price=350.0, annual_trend_pct=2.0),
            ComponentItem(name="NVMe SSD (2TB)", current_price=160.0, annual_trend_pct=5.0),
            ComponentItem(
                name="Motherboard / PSU / Case", current_price=380.0, annual_trend_pct=3.0
            ),
        ),
    ),
    MarketPreset(
        name="Normal Hardware Deflation",
        description="Typical tech depreciation where waiting buys the same tier for less.",
        components=(
            ComponentItem(name="RAM (DDR5 32GB)", current_price=160.0, annual_trend_pct=-8.0),
            ComponentItem(name="GPU", current_price=750.0, annual_trend_pct=-10.0),
            ComponentItem(name="CPU", current_price=350.0, annual_trend_pct=-10.0),
            ComponentItem(name="NVMe SSD (2TB)", current_price=160.0, annual_trend_pct=-12.0),
            ComponentItem(
                name="Motherboard / PSU / Case", current_price=380.0, annual_trend_pct=-2.0
            ),
        ),
    ),
    MarketPreset(
        name="Flat Prices (0% Trend)",
        description="No component price changes; pure loan interest vs. discount rate check.",
        components=(
            ComponentItem(name="RAM (DDR5 32GB)", current_price=160.0, annual_trend_pct=0.0),
            ComponentItem(name="GPU", current_price=750.0, annual_trend_pct=0.0),
            ComponentItem(name="CPU", current_price=350.0, annual_trend_pct=0.0),
            ComponentItem(name="NVMe SSD (2TB)", current_price=160.0, annual_trend_pct=0.0),
            ComponentItem(
                name="Motherboard / PSU / Case", current_price=380.0, annual_trend_pct=0.0
            ),
        ),
    ),
)

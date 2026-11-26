"""Tkinter desktop GUI for PC loan discounting, SA import tax, and component trend analysis."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, replace
from tkinter import messagebox, ttk
from typing import Literal

from pc_loan_discount.calculator import analyze_pc_loan
from pc_loan_discount.models import (
    CURRENCY_PROFILES,
    MARKET_PRESETS,
    AnalysisInputs,
    AnalysisResult,
    ComponentItem,
    CompoundingFrequency,
    CurrencyCode,
    ImportTaxConfig,
    InterestType,
    format_currency,
    scale_components_for_currency,
)

type _Anchor = Literal["w", "e", "center"]

_INTEREST_LABELS: dict[str, InterestType] = {
    "Simple Interest": InterestType.SIMPLE,
    "Compound (Amortized Monthly)": InterestType.COMPOUND_AMORTIZED,
    "Compound (Lump Sum at End)": InterestType.COMPOUND_LUMP_SUM,
}

_COMPOUNDING_LABELS: dict[str, CompoundingFrequency] = {
    "Monthly (12/yr)": CompoundingFrequency.MONTHLY,
    "Quarterly (4/yr)": CompoundingFrequency.QUARTERLY,
    "Semi-Annually (2/yr)": CompoundingFrequency.SEMI_ANNUALLY,
    "Annually (1/yr)": CompoundingFrequency.ANNUALLY,
    "Daily (365/yr)": CompoundingFrequency.DAILY,
}

_CURRENCY_LABELS: dict[str, CurrencyCode] = {
    profile.name: code for code, profile in CURRENCY_PROFILES.items()
}

_SENSITIVITY_RATES: tuple[float, ...] = (0.0, 6.0, 10.0, 12.5, 15.5, 18.5, 22.0, 27.5)


@dataclass
class _ComponentRowWidgets:
    """Widget references for one editable PC component row."""

    frame: ttk.Frame
    name_var: tk.StringVar
    price_var: tk.StringVar
    trend_var: tk.StringVar


class PCLoanDiscountApp:
    """Desktop application comparing a financed PC build against projected landed costs."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PC Loan & Component Trend Discount Calculator (South Africa / Multi-FX)")
        self.root.geometry("1240x830")
        self.root.minsize(1040, 700)

        self._component_rows: list[_ComponentRowWidgets] = []
        default_profile = CURRENCY_PROFILES[CurrencyCode.ZAR]
        default_tax = default_profile.default_import_tax

        # Currency & locale variables
        self._currency_label_var = tk.StringVar(value=default_profile.name)
        self._tax_enabled_var = tk.BooleanVar(value=default_tax.enabled)
        self._vat_pct_var = tk.StringVar(value=f"{default_tax.vat_pct:.1f}")
        self._uplift_pct_var = tk.StringVar(value=f"{default_tax.customs_uplift_pct:.1f}")
        self._duty_pct_var = tk.StringVar(value=f"{default_tax.customs_duty_pct:.1f}")
        self._shipping_fee_var = tk.StringVar(value=f"{default_tax.shipping_and_clearance_fee:.0f}")
        self._fx_depreciation_var = tk.StringVar(
            value=f"{default_profile.default_fx_depreciation_pct:.1f}"
        )
        self._tax_note_var = tk.StringVar(value=default_profile.tax_note)

        # Loan & discounting input variables
        self._interest_label_var = tk.StringVar(value="Compound (Amortized Monthly)")
        self._compounding_label_var = tk.StringVar(value="Monthly (12/yr)")
        self._simple_lump_sum_var = tk.BooleanVar(value=False)
        self._loan_rate_var = tk.StringVar(value=f"{default_profile.default_loan_rate_pct:.1f}")
        self._term_months_var = tk.StringVar(value="12")
        self._sync_wait_var = tk.BooleanVar(value=True)
        self._wait_months_var = tk.StringVar(value="12")
        self._down_payment_var = tk.StringVar(value="0")
        self._discount_rate_var = tk.StringVar(
            value=f"{default_profile.default_discount_rate_pct:.1f}"
        )
        self._early_use_var = tk.StringVar(value="0")
        self._preset_var = tk.StringVar(value=MARKET_PRESETS[0].name)
        self._preset_desc_var = tk.StringVar(value=MARKET_PRESETS[0].description)
        self._status_var = tk.StringVar(value="")

        # Dynamic currency-labeled headers
        self._down_lbl_var = tk.StringVar()
        self._early_lbl_var = tk.StringVar()
        self._ship_lbl_var = tk.StringVar()
        self._price_hdr_var = tk.StringVar()

        # Verdict display variables
        self._verdict_title_var = tk.StringVar(value="Enter inputs and click Calculate")
        self._verdict_sub_var = tk.StringVar(value="")

        self._build_ui()
        self._update_currency_labels(CurrencyCode.ZAR)
        self._load_preset(MARKET_PRESETS[0].name)
        self._on_interest_type_change()
        self._on_sync_wait_toggle()
        self._on_tax_toggle()
        self.calculate()

    def _current_currency(self) -> CurrencyCode:
        return _CURRENCY_LABELS[self._currency_label_var.get()]

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        # Top verdict banner
        self._verdict_frame = tk.Frame(outer, bg="#1e293b", padx=16, pady=10)
        self._verdict_frame.pack(fill=tk.X, pady=(0, 8))

        self._verdict_title_lbl = tk.Label(
            self._verdict_frame,
            textvariable=self._verdict_title_var,
            font=("Segoe UI", 13, "bold"),
            fg="#ffffff",
            bg="#1e293b",
            anchor="w",
        )
        self._verdict_title_lbl.pack(fill=tk.X)

        self._verdict_sub_lbl = tk.Label(
            self._verdict_frame,
            textvariable=self._verdict_sub_var,
            font=("Segoe UI", 9),
            fg="#e2e8f0",
            bg="#1e293b",
            anchor="w",
        )
        self._verdict_sub_lbl.pack(fill=tk.X, pady=(3, 0))

        # Main horizontal split
        body = ttk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=4)
        body.columnconfigure(1, weight=6)
        body.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(body, padding=(0, 0, 8, 0))
        right_panel = ttk.Frame(body, padding=(8, 0, 0, 0))
        left_panel.grid(row=0, column=0, sticky="nsew")
        right_panel.grid(row=0, column=1, sticky="nsew")

        self._build_left_inputs(left_panel)
        self._build_right_outputs(right_panel)

    def _build_left_inputs(self, parent: ttk.Frame) -> None:
        # 1. Currency & Import Tax / FX group
        locale_box = ttk.LabelFrame(parent, text="Locale, Import Tax & FX", padding=8)
        locale_box.pack(fill=tk.X, pady=(0, 8))
        locale_box.columnconfigure(1, weight=1)
        locale_box.columnconfigure(3, weight=1)

        ttk.Label(locale_box, text="Currency:").grid(row=0, column=0, sticky="w", pady=2)
        currency_cb = ttk.Combobox(
            locale_box,
            textvariable=self._currency_label_var,
            values=list(_CURRENCY_LABELS.keys()),
            state="readonly",
        )
        currency_cb.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(6, 0), pady=2)
        currency_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_currency_change())

        ttk.Checkbutton(
            locale_box,
            text="Apply import tax & clearance (uncheck if prices already include VAT)",
            variable=self._tax_enabled_var,
            command=self._on_tax_toggle,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(3, 2))

        ttk.Label(locale_box, text="Import VAT (%):").grid(row=2, column=0, sticky="w", pady=2)
        self._vat_entry = ttk.Entry(locale_box, textvariable=self._vat_pct_var, width=8)
        self._vat_entry.grid(row=2, column=1, sticky="ew", padx=(4, 8), pady=2)

        ttk.Label(locale_box, text="ATV Uplift (%):").grid(row=2, column=2, sticky="w", pady=2)
        self._uplift_entry = ttk.Entry(locale_box, textvariable=self._uplift_pct_var, width=8)
        self._uplift_entry.grid(row=2, column=3, sticky="ew", padx=(4, 0), pady=2)

        ttk.Label(locale_box, text="Customs Duty (%):").grid(row=3, column=0, sticky="w", pady=2)
        self._duty_entry = ttk.Entry(locale_box, textvariable=self._duty_pct_var, width=8)
        self._duty_entry.grid(row=3, column=1, sticky="ew", padx=(4, 8), pady=2)

        ttk.Label(locale_box, textvariable=self._ship_lbl_var).grid(
            row=3, column=2, sticky="w", pady=2
        )
        self._ship_entry = ttk.Entry(locale_box, textvariable=self._shipping_fee_var, width=8)
        self._ship_entry.grid(row=3, column=3, sticky="ew", padx=(4, 0), pady=2)

        ttk.Label(locale_box, text="FX Weakening (%/yr):").grid(row=4, column=0, sticky="w", pady=2)
        fx_entry = ttk.Entry(locale_box, textvariable=self._fx_depreciation_var, width=8)
        fx_entry.grid(row=4, column=1, sticky="ew", padx=(4, 8), pady=2)

        ttk.Label(
            locale_box,
            textvariable=self._tax_note_var,
            foreground="#475569",
            wraplength=420,
            font=("Segoe UI", 8),
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(2, 0))

        for entry in (
            self._vat_entry,
            self._uplift_entry,
            self._duty_entry,
            self._ship_entry,
            fx_entry,
        ):
            entry.bind("<Return>", lambda _e: self.calculate())

        # 2. Loan parameters group
        loan_box = ttk.LabelFrame(parent, text="Loan & Discounting Parameters", padding=8)
        loan_box.pack(fill=tk.X, pady=(0, 8))
        loan_box.columnconfigure(1, weight=1)
        loan_box.columnconfigure(3, weight=1)

        ttk.Label(loan_box, text="Interest Method:").grid(row=0, column=0, sticky="w", pady=2)
        interest_cb = ttk.Combobox(
            loan_box,
            textvariable=self._interest_label_var,
            values=list(_INTEREST_LABELS.keys()),
            state="readonly",
        )
        interest_cb.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(6, 0), pady=2)
        interest_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_interest_type_change())

        ttk.Label(loan_box, text="Compounding:").grid(row=1, column=0, sticky="w", pady=2)
        self._compounding_cb = ttk.Combobox(
            loan_box,
            textvariable=self._compounding_label_var,
            values=list(_COMPOUNDING_LABELS.keys()),
            state="readonly",
        )
        self._compounding_cb.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(6, 0), pady=2)

        self._simple_lump_chk = ttk.Checkbutton(
            loan_box,
            text="Pay simple interest as single lump sum at maturity",
            variable=self._simple_lump_sum_var,
        )
        self._simple_lump_chk.grid(row=2, column=0, columnspan=4, sticky="w", pady=2)

        ttk.Label(loan_box, text="Loan APR (%):").grid(row=3, column=0, sticky="w", pady=2)
        apr_entry = ttk.Entry(loan_box, textvariable=self._loan_rate_var, width=9)
        apr_entry.grid(row=3, column=1, sticky="ew", padx=(4, 8), pady=2)

        ttk.Label(loan_box, text="Term (months):").grid(row=3, column=2, sticky="w", pady=2)
        term_entry = ttk.Entry(loan_box, textvariable=self._term_months_var, width=9)
        term_entry.grid(row=3, column=3, sticky="ew", padx=(4, 0), pady=2)

        ttk.Label(loan_box, textvariable=self._down_lbl_var).grid(
            row=4, column=0, sticky="w", pady=2
        )
        down_entry = ttk.Entry(loan_box, textvariable=self._down_payment_var, width=9)
        down_entry.grid(row=4, column=1, sticky="ew", padx=(4, 8), pady=2)

        ttk.Label(loan_box, text="Discount Rate (%/yr):").grid(row=4, column=2, sticky="w", pady=2)
        disc_entry = ttk.Entry(loan_box, textvariable=self._discount_rate_var, width=9)
        disc_entry.grid(row=4, column=3, sticky="ew", padx=(4, 0), pady=2)

        ttk.Label(loan_box, textvariable=self._early_lbl_var).grid(
            row=5, column=0, sticky="w", pady=2
        )
        early_entry = ttk.Entry(loan_box, textvariable=self._early_use_var, width=9)
        early_entry.grid(row=5, column=1, sticky="ew", padx=(4, 8), pady=2)

        wait_frame = ttk.Frame(loan_box)
        wait_frame.grid(row=5, column=2, columnspan=2, sticky="ew", pady=2)
        ttk.Checkbutton(
            wait_frame,
            text="Wait=Term",
            variable=self._sync_wait_var,
            command=self._on_sync_wait_toggle,
        ).pack(side=tk.LEFT)
        self._wait_entry = ttk.Entry(wait_frame, textvariable=self._wait_months_var, width=5)
        self._wait_entry.pack(side=tk.LEFT, padx=(4, 0), fill=tk.X, expand=True)

        for entry in (apr_entry, term_entry, down_entry, disc_entry, early_entry, self._wait_entry):
            entry.bind("<Return>", lambda _e: self.calculate())

        # 3. PC components & trends group
        comp_box = ttk.LabelFrame(
            parent, text="PC Build Components & Global Price Trends", padding=8
        )
        comp_box.pack(fill=tk.BOTH, expand=True)

        preset_row = ttk.Frame(comp_box)
        preset_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(preset_row, text="Trend Preset:").pack(side=tk.LEFT)
        preset_cb = ttk.Combobox(
            preset_row,
            textvariable=self._preset_var,
            values=[preset.name for preset in MARKET_PRESETS],
            state="readonly",
            width=24,
        )
        preset_cb.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)
        preset_cb.bind("<<ComboboxSelected>>", lambda _e: self._load_preset(self._preset_var.get()))

        ttk.Label(
            comp_box,
            textvariable=self._preset_desc_var,
            foreground="#475569",
            wraplength=420,
            font=("Segoe UI", 8),
        ).pack(fill=tk.X, pady=(0, 4))

        header = ttk.Frame(comp_box)
        header.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(header, text="Component", width=21).pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self._price_hdr_var, width=11).pack(
            side=tk.LEFT, padx=(4, 0)
        )
        ttk.Label(header, text="Trend (%/yr)", width=11).pack(side=tk.LEFT, padx=(4, 0))

        self._rows_container = ttk.Frame(comp_box)
        self._rows_container.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(comp_box)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btn_row, text="+ Add Component", command=self._add_blank_component).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_row, text="Calculate", command=self.calculate).pack(side=tk.RIGHT)

        ttk.Label(parent, textvariable=self._status_var, foreground="#b91c1c").pack(
            fill=tk.X, pady=(4, 0)
        )

    def _build_right_outputs(self, parent: ttk.Frame) -> None:
        summary_box = ttk.LabelFrame(parent, text="Discounted Comparison Summary", padding=8)
        summary_box.pack(fill=tk.X, pady=(0, 8))

        self._summary_tree = ttk.Treeview(
            summary_box,
            columns=("metric", "loan", "wait"),
            show="headings",
            height=7,
        )
        self._summary_tree.heading("metric", text="Metric")
        self._summary_tree.heading("loan", text="Buy Now (Loan)")
        self._summary_tree.heading("wait", text="Wait & Buy Later")
        self._summary_tree.column("metric", width=230, anchor="w")
        self._summary_tree.column("loan", width=185, anchor="e")
        self._summary_tree.column("wait", width=185, anchor="e")
        self._summary_tree.pack(fill=tk.X)

        self._chart_canvas = tk.Canvas(parent, height=90, bg="#f8fafc", highlightthickness=1)
        self._chart_canvas.pack(fill=tk.X, pady=(0, 8))

        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Component projections
        comp_tab = ttk.Frame(notebook, padding=6)
        notebook.add(comp_tab, text="Component Forecast")
        self._comp_tree = ttk.Treeview(
            comp_tab,
            columns=("name", "base", "landed", "trend", "future", "delta", "pv"),
            show="headings",
        )
        comp_cols: tuple[tuple[str, str, int, _Anchor], ...] = (
            ("name", "Component", 145, "w"),
            ("base", "Base Today", 85, "e"),
            ("landed", "Landed Today", 92, "e"),
            ("trend", "Trend/yr", 68, "e"),
            ("future", "Future Landed", 95, "e"),
            ("delta", "Change", 85, "e"),
            ("pv", "Discounted PV", 95, "e"),
        )
        for col, heading, width, anchor in comp_cols:
            self._comp_tree.heading(col, text=heading)
            self._comp_tree.column(col, width=width, anchor=anchor)
        self._comp_tree.pack(fill=tk.BOTH, expand=True)

        # Tab 2: Payment & discount schedule
        sched_tab = ttk.Frame(notebook, padding=6)
        notebook.add(sched_tab, text="Loan Schedule")
        sched_scroll = ttk.Scrollbar(sched_tab, orient=tk.VERTICAL)
        self._sched_tree = ttk.Treeview(
            sched_tab,
            columns=("month", "payment", "interest", "principal", "balance", "pv"),
            show="headings",
            yscrollcommand=sched_scroll.set,
        )
        # typeshed types tk.YView.yview with `*args: Any`
        sched_scroll.config(command=self._sched_tree.yview)  # pyright: ignore
        sched_cols: tuple[tuple[str, str, int, _Anchor], ...] = (
            ("month", "Mo", 42, "e"),
            ("payment", "Payment", 100, "e"),
            ("interest", "Interest", 100, "e"),
            ("principal", "Principal", 100, "e"),
            ("balance", "Balance", 105, "e"),
            ("pv", "Discounted PV", 110, "e"),
        )
        for col, heading, width, anchor in sched_cols:
            self._sched_tree.heading(col, text=heading)
            self._sched_tree.column(col, width=width, anchor=anchor)
        self._sched_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sched_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tab 3: APR sensitivity table
        sens_tab = ttk.Frame(notebook, padding=6)
        notebook.add(sens_tab, text="APR Sensitivity")
        self._sens_tree = ttk.Treeview(
            sens_tab,
            columns=("apr", "monthly", "pv_loan", "net_npv", "verdict"),
            show="headings",
        )
        sens_cols: tuple[tuple[str, str, int, _Anchor], ...] = (
            ("apr", "Loan APR", 80, "e"),
            ("monthly", "Monthly Pmt", 110, "e"),
            ("pv_loan", "Loan Cost (PV)", 120, "e"),
            ("net_npv", "Net Advantage (PV)", 135, "e"),
            ("verdict", "Verdict", 105, "center"),
        )
        for col, heading, width, anchor in sens_cols:
            self._sens_tree.heading(col, text=heading)
            self._sens_tree.column(col, width=width, anchor=anchor)
        self._sens_tree.pack(fill=tk.BOTH, expand=True)

    def _update_currency_labels(self, code: CurrencyCode) -> None:
        sym = CURRENCY_PROFILES[code].symbol
        self._down_lbl_var.set(f"Down Payment ({sym}):")
        self._early_lbl_var.set(f"Early-Use ({sym}/mo):")
        self._ship_lbl_var.set(f"Ship/Clear ({sym}):")
        self._price_hdr_var.set(f"Base ({sym})")

    def _on_currency_change(self) -> None:
        code = self._current_currency()
        profile = CURRENCY_PROFILES[code]
        tax = profile.default_import_tax

        self._update_currency_labels(code)
        self._tax_enabled_var.set(tax.enabled)
        self._vat_pct_var.set(f"{tax.vat_pct:.1f}")
        self._uplift_pct_var.set(f"{tax.customs_uplift_pct:.1f}")
        self._duty_pct_var.set(f"{tax.customs_duty_pct:.1f}")
        self._shipping_fee_var.set(f"{tax.shipping_and_clearance_fee:.0f}")
        self._fx_depreciation_var.set(f"{profile.default_fx_depreciation_pct:.1f}")
        self._loan_rate_var.set(f"{profile.default_loan_rate_pct:.1f}")
        self._discount_rate_var.set(f"{profile.default_discount_rate_pct:.1f}")
        self._tax_note_var.set(profile.tax_note)
        self._on_tax_toggle()
        self._load_preset(self._preset_var.get())

    def _on_tax_toggle(self) -> None:
        state = "normal" if self._tax_enabled_var.get() else "disabled"
        for entry in (self._vat_entry, self._uplift_entry, self._duty_entry, self._ship_entry):
            entry.config(state=state)
        self.calculate()

    def _on_interest_type_change(self) -> None:
        selected = _INTEREST_LABELS[self._interest_label_var.get()]
        if selected == InterestType.SIMPLE:
            self._compounding_cb.config(state="disabled")
            self._simple_lump_chk.config(state="normal")
        else:
            self._compounding_cb.config(state="readonly")
            self._simple_lump_chk.config(state="disabled")

    def _on_sync_wait_toggle(self) -> None:
        if self._sync_wait_var.get():
            self._wait_months_var.set(self._term_months_var.get())
            self._wait_entry.config(state="disabled")
        else:
            self._wait_entry.config(state="normal")

    def _clear_component_rows(self) -> None:
        for row in self._component_rows:
            row.frame.destroy()
        self._component_rows.clear()

    def _add_component_row(self, item: ComponentItem) -> None:
        frame = ttk.Frame(self._rows_container)
        frame.pack(fill=tk.X, pady=2)

        name_var = tk.StringVar(value=item.name)
        price_var = tk.StringVar(value=f"{item.current_price:.0f}")
        trend_var = tk.StringVar(value=f"{item.annual_trend_pct:+.1f}")

        name_entry = ttk.Entry(frame, textvariable=name_var, width=21)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        price_entry = ttk.Entry(frame, textvariable=price_var, width=10)
        price_entry.pack(side=tk.LEFT, padx=(4, 0))
        trend_entry = ttk.Entry(frame, textvariable=trend_var, width=10)
        trend_entry.pack(side=tk.LEFT, padx=(4, 0))

        row_widgets = _ComponentRowWidgets(
            frame=frame,
            name_var=name_var,
            price_var=price_var,
            trend_var=trend_var,
        )

        for entry in (name_entry, price_entry, trend_entry):
            entry.bind("<Return>", lambda _e: self.calculate())

        ttk.Button(
            frame,
            text="×",
            width=3,
            command=lambda rw=row_widgets: self._remove_component_row(rw),
        ).pack(side=tk.LEFT, padx=(4, 0))

        self._component_rows.append(row_widgets)

    def _add_blank_component(self) -> None:
        code = self._current_currency()
        default_amt = round(1500.0 / CURRENCY_PROFILES[code].zar_per_unit, 0)
        self._add_component_row(
            ComponentItem(name="Other Part", current_price=default_amt, annual_trend_pct=0.0)
        )

    def _remove_component_row(self, target: _ComponentRowWidgets) -> None:
        if len(self._component_rows) <= 1:
            messagebox.showwarning("Cannot Remove", "At least one PC component is required.")
            return
        target.frame.destroy()
        self._component_rows.remove(target)
        self.calculate()

    def _load_preset(self, preset_name: str) -> None:
        preset = next((p for p in MARKET_PRESETS if p.name == preset_name), MARKET_PRESETS[0])
        self._preset_desc_var.set(preset.description)
        scaled = scale_components_for_currency(preset.components, self._current_currency())
        self._clear_component_rows()
        for item in scaled:
            self._add_component_row(item)
        self.calculate()

    def _parse_inputs(self) -> AnalysisInputs:
        term_months = int(self._term_months_var.get().strip())
        if self._sync_wait_var.get():
            self._wait_months_var.set(str(term_months))
            wait_months = term_months
        else:
            wait_months = int(self._wait_months_var.get().strip())

        components: list[ComponentItem] = []
        for row in self._component_rows:
            components.append(
                ComponentItem(
                    name=row.name_var.get().strip(),
                    current_price=float(row.price_var.get().strip()),
                    annual_trend_pct=float(row.trend_var.get().strip()),
                )
            )

        import_tax = ImportTaxConfig(
            enabled=self._tax_enabled_var.get(),
            vat_pct=float(self._vat_pct_var.get().strip()),
            customs_uplift_pct=float(self._uplift_pct_var.get().strip()),
            customs_duty_pct=float(self._duty_pct_var.get().strip()),
            shipping_and_clearance_fee=float(self._shipping_fee_var.get().strip()),
        )

        return AnalysisInputs(
            components=tuple(components),
            loan_annual_rate_pct=float(self._loan_rate_var.get().strip()),
            term_months=term_months,
            discount_rate_pct=float(self._discount_rate_var.get().strip()),
            currency=self._current_currency(),
            import_tax=import_tax,
            fx_annual_depreciation_pct=float(self._fx_depreciation_var.get().strip()),
            interest_type=_INTEREST_LABELS[self._interest_label_var.get()],
            compounding_frequency=_COMPOUNDING_LABELS[self._compounding_label_var.get()],
            simple_lump_sum=self._simple_lump_sum_var.get(),
            down_payment=float(self._down_payment_var.get().strip()),
            wait_months=wait_months,
            monthly_early_use_value=float(self._early_use_var.get().strip()),
        )

    def calculate(self) -> None:
        """Parse inputs, run the financial engine, and refresh all output widgets."""
        if not self._component_rows:
            return
        try:
            inputs = self._parse_inputs()
            result = analyze_pc_loan(inputs)
        except ValueError as exc:
            self._status_var.set(f"Input error: {exc}")
            return

        self._status_var.set("")
        self._render_verdict(result)
        self._render_summary(result)
        self._render_bar_chart(result)
        self._render_component_table(result)
        self._render_schedule_table(result)
        self._render_sensitivity_table(inputs)

    def _render_verdict(self, result: AnalysisResult) -> None:
        cur = result.currency
        if result.net_total_advantage > 0.01:
            bg = "#14532d"
            amt = format_currency(result.net_total_advantage, cur, signed=True)
            label = f"NET WORTH IT: Taking the loan saves {amt} (PV)"
        elif result.net_total_advantage < -0.01:
            bg = "#7f1d1d"
            saved = format_currency(abs(result.net_total_advantage), cur)
            loss = format_currency(result.net_total_advantage, cur, signed=True)
            label = f"NOT WORTH IT: Waiting saves {saved} (loan loses {loss} PV)"
        else:
            bg = "#334155"
            label = "BREAK-EVEN: Loan and waiting have effectively equal present value"

        be_rate = (
            f"{result.break_even_loan_rate_pct:.2f}% APR"
            if result.break_even_loan_rate_pct is not None
            else "N/A"
        )
        be_trend = (
            f"{result.break_even_component_trend_pct:+.2f}%/yr"
            if result.break_even_component_trend_pct is not None
            else "N/A"
        )
        fin_npv = format_currency(result.net_financial_advantage, cur, signed=True)
        sub = (
            f"Financial NPV: {fin_npv}  |  "
            f"Eff. Import Tax: {result.effective_import_tax_rate_pct:.2f}%  |  "
            f"Local Trend: {result.effective_component_cagr_pct:+.2f}%/yr  |  "
            f"Break-Even APR: {be_rate}  |  "
            f"Break-Even Global Trend: {be_trend}"
        )

        self._verdict_frame.config(bg=bg)
        self._verdict_title_lbl.config(bg=bg)
        self._verdict_sub_lbl.config(bg=bg)
        self._verdict_title_var.set(label)
        self._verdict_sub_var.set(sub)

    def _render_summary(self, result: AnalysisResult) -> None:
        cur = result.currency
        self._summary_tree.delete(*self._summary_tree.get_children())
        rows = (
            (
                "Base PC Components (Ex-Import Tax)",
                format_currency(result.pc_base_price_today, cur),
                format_currency(result.pc_base_price_future_nominal, cur),
            ),
            (
                "Import Tax + Shipping & Clearance",
                f"{format_currency(result.import_tax_today, cur)} + "
                f"{format_currency(result.shipping_today, cur)}",
                f"{format_currency(result.import_tax_future_nominal, cur)} + "
                f"{format_currency(result.shipping_future_nominal, cur)}",
            ),
            (
                "Total Landed PC Price",
                format_currency(result.pc_price_today, cur),
                format_currency(result.pc_price_future_nominal, cur),
            ),
            (
                "Monthly Payment / Total Interest",
                f"{format_currency(result.monthly_payment, cur)}/mo "
                f"({format_currency(result.total_interest_nominal, cur)} int)",
                format_currency(0.0, cur),
            ),
            (
                "Total Nominal Outlay",
                format_currency(result.total_outlay_loan_nominal, cur),
                format_currency(result.pc_price_future_nominal, cur),
            ),
            (
                "Discounted Present Value (PV) Cost",
                format_currency(result.pv_loan_option, cur),
                format_currency(result.pv_wait_option, cur),
            ),
            (
                "Early-Use Value (PV) / Net Advantage",
                f"+{format_currency(result.pv_early_use_benefit, cur)} early use",
                f"Loan NPV: {format_currency(result.net_total_advantage, cur, signed=True)}",
            ),
        )
        for row in rows:
            self._summary_tree.insert("", tk.END, values=row)

    def _render_bar_chart(self, result: AnalysisResult) -> None:
        cur = result.currency
        canvas = self._chart_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 560)
        max_val = max(result.pv_loan_option, result.pv_wait_option, 1.0)
        bar_max_w = max(width - 280, 120)

        bars = (
            ("Loan Option (PV Cost)", result.pv_loan_option, "#2563eb", 16),
            ("Wait & Buy Later (PV Cost)", result.pv_wait_option, "#d97706", 50),
        )
        for label, value, color, y in bars:
            bar_w = (value / max_val) * bar_max_w
            canvas.create_text(10, y + 12, text=label, anchor="w", font=("Segoe UI", 9, "bold"))
            canvas.create_rectangle(180, y, 180 + bar_w, y + 22, fill=color, outline="")
            canvas.create_text(
                188 + bar_w,
                y + 11,
                text=format_currency(value, cur),
                anchor="w",
                font=("Segoe UI", 9),
            )

    def _render_component_table(self, result: AnalysisResult) -> None:
        cur = result.currency
        self._comp_tree.delete(*self._comp_tree.get_children())
        for proj in result.component_projections:
            self._comp_tree.insert(
                "",
                tk.END,
                values=(
                    proj.name,
                    format_currency(proj.base_price_today, cur),
                    format_currency(proj.landed_price_today, cur),
                    f"{proj.annual_trend_pct:+.1f}%",
                    format_currency(proj.projected_landed_price, cur),
                    format_currency(proj.price_change, cur, signed=True),
                    format_currency(proj.discounted_future_price, cur),
                ),
            )

    def _render_schedule_table(self, result: AnalysisResult) -> None:
        cur = result.currency
        self._sched_tree.delete(*self._sched_tree.get_children())
        for entry in result.schedule:
            self._sched_tree.insert(
                "",
                tk.END,
                values=(
                    entry.month,
                    format_currency(entry.payment, cur),
                    format_currency(entry.interest_portion, cur),
                    format_currency(entry.principal_portion, cur),
                    format_currency(entry.remaining_balance, cur),
                    format_currency(entry.present_value, cur),
                ),
            )

    def _render_sensitivity_table(self, inputs: AnalysisInputs) -> None:
        cur = inputs.currency
        self._sens_tree.delete(*self._sens_tree.get_children())
        for apr in _SENSITIVITY_RATES:
            sim = analyze_pc_loan(replace(inputs, loan_annual_rate_pct=apr))
            verdict = "Worth It" if sim.worth_it else "Wait"
            self._sens_tree.insert(
                "",
                tk.END,
                values=(
                    f"{apr:.1f}%",
                    format_currency(sim.monthly_payment, cur),
                    format_currency(sim.pv_loan_option, cur),
                    format_currency(sim.net_total_advantage, cur, signed=True),
                    verdict,
                ),
            )


def launch_gui() -> None:
    """Create and run the desktop Tkinter application."""
    root = tk.Tk()
    PCLoanDiscountApp(root)
    root.mainloop()

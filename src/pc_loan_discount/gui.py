"""Tkinter desktop GUI for PC loan discounting and component trend analysis."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, replace
from tkinter import messagebox, ttk
from typing import Literal

from pc_loan_discount.calculator import analyze_pc_loan
from pc_loan_discount.models import (
    MARKET_PRESETS,
    AnalysisInputs,
    AnalysisResult,
    ComponentItem,
    CompoundingFrequency,
    InterestType,
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

_SENSITIVITY_RATES: tuple[float, ...] = (0.0, 5.0, 8.0, 12.0, 16.0, 20.0, 25.0, 30.0)


@dataclass
class _ComponentRowWidgets:
    """Widget references for one editable PC component row."""

    frame: ttk.Frame
    name_var: tk.StringVar
    price_var: tk.StringVar
    trend_var: tk.StringVar


class PCLoanDiscountApp:
    """Desktop application comparing a PC build loan against projected component trends."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PC Loan & Component Trend Discount Calculator")
        self.root.geometry("1160x760")
        self.root.minsize(980, 660)

        self._component_rows: list[_ComponentRowWidgets] = []

        # Loan & discounting input variables
        self._interest_label_var = tk.StringVar(value="Compound (Amortized Monthly)")
        self._compounding_label_var = tk.StringVar(value="Monthly (12/yr)")
        self._simple_lump_sum_var = tk.BooleanVar(value=False)
        self._loan_rate_var = tk.StringVar(value="12.0")
        self._term_months_var = tk.StringVar(value="12")
        self._sync_wait_var = tk.BooleanVar(value=True)
        self._wait_months_var = tk.StringVar(value="12")
        self._down_payment_var = tk.StringVar(value="0")
        self._discount_rate_var = tk.StringVar(value="6.0")
        self._early_use_var = tk.StringVar(value="0")
        self._preset_var = tk.StringVar(value=MARKET_PRESETS[0].name)
        self._preset_desc_var = tk.StringVar(value=MARKET_PRESETS[0].description)
        self._status_var = tk.StringVar(value="")

        # Verdict display variables
        self._verdict_title_var = tk.StringVar(value="Enter inputs and click Calculate")
        self._verdict_sub_var = tk.StringVar(value="")

        self._build_ui()
        self._load_preset(MARKET_PRESETS[0].name)
        self._on_interest_type_change()
        self._on_sync_wait_toggle()
        self.calculate()

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        # Top verdict banner
        self._verdict_frame = tk.Frame(outer, bg="#1e293b", padx=16, pady=12)
        self._verdict_frame.pack(fill=tk.X, pady=(0, 10))

        self._verdict_title_lbl = tk.Label(
            self._verdict_frame,
            textvariable=self._verdict_title_var,
            font=("Segoe UI", 14, "bold"),
            fg="#ffffff",
            bg="#1e293b",
            anchor="w",
        )
        self._verdict_title_lbl.pack(fill=tk.X)

        self._verdict_sub_lbl = tk.Label(
            self._verdict_frame,
            textvariable=self._verdict_sub_var,
            font=("Segoe UI", 10),
            fg="#e2e8f0",
            bg="#1e293b",
            anchor="w",
        )
        self._verdict_sub_lbl.pack(fill=tk.X, pady=(4, 0))

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
        # Loan parameters group
        loan_box = ttk.LabelFrame(parent, text="Loan & Discounting Parameters", padding=10)
        loan_box.pack(fill=tk.X, pady=(0, 10))
        loan_box.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(loan_box, text="Interest Method:").grid(row=row, column=0, sticky="w", pady=3)
        interest_cb = ttk.Combobox(
            loan_box,
            textvariable=self._interest_label_var,
            values=list(_INTEREST_LABELS.keys()),
            state="readonly",
        )
        interest_cb.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
        interest_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_interest_type_change())

        row += 1
        ttk.Label(loan_box, text="Compounding:").grid(row=row, column=0, sticky="w", pady=3)
        self._compounding_cb = ttk.Combobox(
            loan_box,
            textvariable=self._compounding_label_var,
            values=list(_COMPOUNDING_LABELS.keys()),
            state="readonly",
        )
        self._compounding_cb.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)

        row += 1
        self._simple_lump_chk = ttk.Checkbutton(
            loan_box,
            text="Pay simple interest as single lump sum at maturity",
            variable=self._simple_lump_sum_var,
        )
        self._simple_lump_chk.grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 4))

        numeric_fields: tuple[tuple[str, tk.StringVar], ...] = (
            ("Loan APR (%):", self._loan_rate_var),
            ("Loan Term (months):", self._term_months_var),
            ("Down Payment ($):", self._down_payment_var),
            ("Discount Rate / Opportunity Cost (%/yr):", self._discount_rate_var),
            ("Optional Early-Use Value ($/mo):", self._early_use_var),
        )
        for label_text, var in numeric_fields:
            row += 1
            ttk.Label(loan_box, text=label_text).grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(loan_box, textvariable=var, width=14)
            entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
            entry.bind("<Return>", lambda _e: self.calculate())

        row += 1
        wait_frame = ttk.Frame(loan_box)
        wait_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Checkbutton(
            wait_frame,
            text="Wait horizon = loan term",
            variable=self._sync_wait_var,
            command=self._on_sync_wait_toggle,
        ).pack(side=tk.LEFT)
        ttk.Label(wait_frame, text="  Wait (mo):").pack(side=tk.LEFT)
        self._wait_entry = ttk.Entry(wait_frame, textvariable=self._wait_months_var, width=6)
        self._wait_entry.pack(side=tk.LEFT, padx=(4, 0))
        self._wait_entry.bind("<Return>", lambda _e: self.calculate())

        # PC components & trends group
        comp_box = ttk.LabelFrame(parent, text="PC Build Components & Future Trends", padding=10)
        comp_box.pack(fill=tk.BOTH, expand=True)

        preset_row = ttk.Frame(comp_box)
        preset_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(preset_row, text="Market Trend Preset:").pack(side=tk.LEFT)
        preset_cb = ttk.Combobox(
            preset_row,
            textvariable=self._preset_var,
            values=[preset.name for preset in MARKET_PRESETS],
            state="readonly",
            width=26,
        )
        preset_cb.pack(side=tk.LEFT, padx=(6, 6), fill=tk.X, expand=True)
        preset_cb.bind("<<ComboboxSelected>>", lambda _e: self._load_preset(self._preset_var.get()))

        ttk.Label(
            comp_box,
            textvariable=self._preset_desc_var,
            foreground="#475569",
            wraplength=400,
        ).pack(fill=tk.X, pady=(0, 6))

        # Column headers
        header = ttk.Frame(comp_box)
        header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(header, text="Component", width=22).pack(side=tk.LEFT)
        ttk.Label(header, text="Today ($)", width=10).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(header, text="Trend (%/yr)", width=11).pack(side=tk.LEFT, padx=(4, 0))

        self._rows_container = ttk.Frame(comp_box)
        self._rows_container.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(comp_box)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="+ Add Component", command=self._add_blank_component).pack(
            side=tk.LEFT
        )
        ttk.Button(btn_row, text="Calculate", command=self.calculate).pack(side=tk.RIGHT)

        ttk.Label(parent, textvariable=self._status_var, foreground="#b91c1c").pack(
            fill=tk.X, pady=(6, 0)
        )

    def _build_right_outputs(self, parent: ttk.Frame) -> None:
        # Key summary metrics grid
        summary_box = ttk.LabelFrame(parent, text="Discounted Comparison Summary", padding=10)
        summary_box.pack(fill=tk.X, pady=(0, 10))

        self._summary_tree = ttk.Treeview(
            summary_box,
            columns=("metric", "loan", "wait"),
            show="headings",
            height=6,
        )
        self._summary_tree.heading("metric", text="Metric")
        self._summary_tree.heading("loan", text="Buy Now (Loan)")
        self._summary_tree.heading("wait", text="Wait & Buy Later")
        self._summary_tree.column("metric", width=220, anchor="w")
        self._summary_tree.column("loan", width=165, anchor="e")
        self._summary_tree.column("wait", width=165, anchor="e")
        self._summary_tree.pack(fill=tk.X)

        # Visual PV comparison bar canvas
        self._chart_canvas = tk.Canvas(parent, height=96, bg="#f8fafc", highlightthickness=1)
        self._chart_canvas.pack(fill=tk.X, pady=(0, 10))

        # Detailed notebook tabs
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Component projections
        comp_tab = ttk.Frame(notebook, padding=6)
        notebook.add(comp_tab, text="Component Forecast")
        self._comp_tree = ttk.Treeview(
            comp_tab,
            columns=("name", "today", "trend", "future", "delta", "pv"),
            show="headings",
        )
        comp_cols: tuple[tuple[str, str, int, _Anchor], ...] = (
            ("name", "Component", 160, "w"),
            ("today", "Today ($)", 85, "e"),
            ("trend", "Trend/yr", 78, "e"),
            ("future", "Future ($)", 85, "e"),
            ("delta", "Change ($)", 85, "e"),
            ("pv", "Discounted PV ($)", 110, "e"),
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
            ("month", "Mo", 45, "e"),
            ("payment", "Payment ($)", 95, "e"),
            ("interest", "Interest ($)", 95, "e"),
            ("principal", "Principal ($)", 95, "e"),
            ("balance", "Balance ($)", 100, "e"),
            ("pv", "Discounted PV ($)", 110, "e"),
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
            ("monthly", "Monthly Pmt", 105, "e"),
            ("pv_loan", "Loan Cost (PV)", 115, "e"),
            ("net_npv", "Net Advantage (PV)", 130, "e"),
            ("verdict", "Verdict", 110, "center"),
        )
        for col, heading, width, anchor in sens_cols:
            self._sens_tree.heading(col, text=heading)
            self._sens_tree.column(col, width=width, anchor=anchor)
        self._sens_tree.pack(fill=tk.BOTH, expand=True)

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

        name_entry = ttk.Entry(frame, textvariable=name_var, width=22)
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
        self._add_component_row(
            ComponentItem(name="Other Part", current_price=100.0, annual_trend_pct=0.0)
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
        self._clear_component_rows()
        for item in preset.components:
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

        return AnalysisInputs(
            components=tuple(components),
            loan_annual_rate_pct=float(self._loan_rate_var.get().strip()),
            term_months=term_months,
            discount_rate_pct=float(self._discount_rate_var.get().strip()),
            interest_type=_INTEREST_LABELS[self._interest_label_var.get()],
            compounding_frequency=_COMPOUNDING_LABELS[self._compounding_label_var.get()],
            simple_lump_sum=self._simple_lump_sum_var.get(),
            down_payment=float(self._down_payment_var.get().strip()),
            wait_months=wait_months,
            monthly_early_use_value=float(self._early_use_var.get().strip()),
        )

    def calculate(self) -> None:
        """Parse inputs, run the financial engine, and refresh all output widgets."""
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
        if result.net_total_advantage > 0.01:
            bg = "#14532d"
            label = f"NET WORTH IT: Taking the loan saves +${result.net_total_advantage:,.2f} (PV)"
        elif result.net_total_advantage < -0.01:
            bg = "#7f1d1d"
            label = (
                f"NOT WORTH IT: Waiting saves +${abs(result.net_total_advantage):,.2f} "
                f"(loan loses -${abs(result.net_total_advantage):,.2f} PV)"
            )
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
        sub = (
            f"Pure Financial NPV: ${result.net_financial_advantage:+,.2f}   |   "
            f"Blended PC Trend: {result.effective_component_cagr_pct:+.2f}%/yr   |   "
            f"Break-Even Loan APR: {be_rate}   |   "
            f"Break-Even PC Trend: {be_trend}"
        )

        self._verdict_frame.config(bg=bg)
        self._verdict_title_lbl.config(bg=bg)
        self._verdict_sub_lbl.config(bg=bg)
        self._verdict_title_var.set(label)
        self._verdict_sub_var.set(sub)

    def _render_summary(self, result: AnalysisResult) -> None:
        self._summary_tree.delete(*self._summary_tree.get_children())
        rows = (
            (
                "PC Price (Today vs. Future Nominal)",
                f"${result.pc_price_today:,.2f}",
                f"${result.pc_price_future_nominal:,.2f}",
            ),
            (
                "Down Payment / Principal Financed",
                f"${result.down_payment:,.2f} / ${result.loan_principal:,.2f}",
                "—",
            ),
            (
                "Monthly Payment / Total Interest",
                f"${result.monthly_payment:,.2f}/mo (${result.total_interest_nominal:,.2f} int)",
                "$0.00",
            ),
            (
                "Total Nominal Outlay",
                f"${result.total_outlay_loan_nominal:,.2f}",
                f"${result.pc_price_future_nominal:,.2f}",
            ),
            (
                "Discounted Present Value (PV) Cost",
                f"${result.pv_loan_option:,.2f}",
                f"${result.pv_wait_option:,.2f}",
            ),
            (
                "Early-Use Value (PV) / Net Advantage",
                f"+${result.pv_early_use_benefit:,.2f} early use",
                f"Loan NPV: ${result.net_total_advantage:+,.2f}",
            ),
        )
        for row in rows:
            self._summary_tree.insert("", tk.END, values=row)

    def _render_bar_chart(self, result: AnalysisResult) -> None:
        canvas = self._chart_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 540)
        max_val = max(result.pv_loan_option, result.pv_wait_option, 1.0)
        bar_max_w = max(width - 260, 120)

        bars = (
            ("Loan Option (PV Cost)", result.pv_loan_option, "#2563eb", 18),
            ("Wait & Buy Later (PV Cost)", result.pv_wait_option, "#d97706", 54),
        )
        for label, value, color, y in bars:
            bar_w = (value / max_val) * bar_max_w
            canvas.create_text(10, y + 12, text=label, anchor="w", font=("Segoe UI", 9, "bold"))
            canvas.create_rectangle(175, y, 175 + bar_w, y + 24, fill=color, outline="")
            canvas.create_text(
                182 + bar_w,
                y + 12,
                text=f"${value:,.2f}",
                anchor="w",
                font=("Segoe UI", 9),
            )

    def _render_component_table(self, result: AnalysisResult) -> None:
        self._comp_tree.delete(*self._comp_tree.get_children())
        for proj in result.component_projections:
            self._comp_tree.insert(
                "",
                tk.END,
                values=(
                    proj.name,
                    f"${proj.current_price:,.2f}",
                    f"{proj.annual_trend_pct:+.1f}%",
                    f"${proj.projected_future_price:,.2f}",
                    f"${proj.price_change:+,.2f}",
                    f"${proj.discounted_future_price:,.2f}",
                ),
            )

    def _render_schedule_table(self, result: AnalysisResult) -> None:
        self._sched_tree.delete(*self._sched_tree.get_children())
        for entry in result.schedule:
            self._sched_tree.insert(
                "",
                tk.END,
                values=(
                    entry.month,
                    f"${entry.payment:,.2f}",
                    f"${entry.interest_portion:,.2f}",
                    f"${entry.principal_portion:,.2f}",
                    f"${entry.remaining_balance:,.2f}",
                    f"${entry.present_value:,.2f}",
                ),
            )

    def _render_sensitivity_table(self, inputs: AnalysisInputs) -> None:
        self._sens_tree.delete(*self._sens_tree.get_children())
        for apr in _SENSITIVITY_RATES:
            sim = analyze_pc_loan(replace(inputs, loan_annual_rate_pct=apr))
            verdict = "Worth It" if sim.worth_it else "Wait"
            self._sens_tree.insert(
                "",
                tk.END,
                values=(
                    f"{apr:.1f}%",
                    f"${sim.monthly_payment:,.2f}",
                    f"${sim.pv_loan_option:,.2f}",
                    f"${sim.net_total_advantage:+,.2f}",
                    verdict,
                ),
            )


def launch_gui() -> None:
    """Create and run the desktop Tkinter application."""
    root = tk.Tk()
    PCLoanDiscountApp(root)
    root.mainloop()

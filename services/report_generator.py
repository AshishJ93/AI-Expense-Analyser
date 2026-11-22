"""Excel and PDF exports built from the same figures as the dashboard."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from services.anomaly_detector import Anomaly
from services.subscription_detector import RecurringPayment
from utils.formatting import format_date, format_inr, format_percent

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
INK = "1C1917"
ACCENT = "312E81"
HEADER_FILL = PatternFill("solid", fgColor=ACCENT)
HEADER_FONT = Font(color="FFFFFF", name="Calibri", bold=True, size=11)
TITLE_FONT = Font(color=INK, name="Calibri", bold=True, size=16)


def build_excel(
    frame: pd.DataFrame,
    kpis,
    categories: pd.DataFrame,
    monthly: pd.DataFrame,
    merchants: pd.DataFrame,
    recurring: list[RecurringPayment],
    anomalies: list[Anomaly],
    recommendations,
    insights,
    demo: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _summary_sheet(writer, kpis, demo)
        _write(writer, "Monthly", _monthly_export(monthly))
        _write(writer, "Categories", _category_export(categories))
        _write(writer, "Merchants", merchants)
        _write(writer, "Recurring", _recurring_export(recurring))
        _write(writer, "Review", _anomaly_export(anomalies))
        _write(writer, "Recommendations", _recommendation_export(recommendations))
        _write(writer, "Insights", _insight_export(insights))
        _write(writer, "Transactions", _transaction_export(frame))
        _style_workbook(writer.book)
    return buffer.getvalue()


def build_pdf(
    frame: pd.DataFrame,
    kpis,
    categories: pd.DataFrame,
    monthly: pd.DataFrame,
    merchants: pd.DataFrame,
    recurring: list[RecurringPayment],
    anomalies: list[Anomaly],
    recommendations,
    insights,
    demo: bool = False,
) -> bytes:
    from fpdf import FPDF

    regular = FONT_DIR / "NotoSans-Regular.ttf"
    bold = FONT_DIR / "NotoSans-SemiBold.ttf"
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_margins(16, 16, 16)
    pdf.set_auto_page_break(auto=True, margin=16)
    uses_noto = regular.exists()
    if uses_noto:
        pdf.add_font("Noto", "", str(regular))
        pdf.add_font("Noto", "B", str(bold if bold.exists() else regular))
        family = "Noto"
    else:
        family = "Helvetica"

    def text(value: str) -> str:
        value = "" if value is None else str(value)
        value = value.replace("\u2013", "-").replace("\u2014", "-").replace("\u00b7", "-")
        if uses_noto:
            return value
        return value.replace("₹", "INR ")

    def write(body: str, size: int = 11, style: str = "", height: float = 6) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font(family, style, size)
        pdf.set_text_color(28, 25, 23)
        pdf.multi_cell(pdf.epw, height, text(body))

    def heading(body: str) -> None:
        pdf.ln(2)
        pdf.set_x(pdf.l_margin)
        pdf.set_font(family, "B", 13)
        pdf.set_text_color(49, 46, 129)
        pdf.multi_cell(pdf.epw, 8, text(body))
        pdf.set_text_color(28, 25, 23)

    pdf.add_page()
    write("HisaabPehle", size=20, style="B", height=10)
    write("Personal spending report", size=12, height=7)
    write(f"Prepared {format_date(date.today())} · {kpis.period_label}", size=10)
    if demo:
        write("This report uses fictional demo transactions.", size=10)
    write(
        "Transfers, income, investments, and duplicate rows are excluded from spending. Refunds reduce the total.",
        size=10,
    )

    heading("Spending summary")
    write(f"Total spending: {format_inr(kpis.total_spending)}")
    write(f"Average complete month: {format_inr(kpis.average_monthly)}. {kpis.average_note}")
    share = format_percent(kpis.top_category_share, signed=False) if kpis.top_category_share is not None else "—"
    write(f"Largest category: {kpis.top_category} · {format_inr(kpis.top_category_amount)} · {share}")
    write(f"Transactions: {kpis.all_transactions} loaded · {kpis.spending_transactions} in the spending total")
    write(f"{kpis.mom_label}: {format_percent(kpis.mom_change)}. {kpis.mom_note}")

    heading("Categories")
    if categories.empty:
        write("No category totals in this view.")
    else:
        for row in categories.head(12).itertuples(index=False):
            write(f"{row.category}: {format_inr(row.spending)} · {format_percent(row.share, signed=False)} · {int(row.transactions)} transactions")

    heading("Monthly trend")
    if monthly.empty:
        write("No monthly totals in this view.")
    else:
        for row in monthly.itertuples(index=False):
            label = pd.to_datetime(row.month_start).strftime("%b %Y")
            write(f"{label}: {format_inr(row.spending)}")

    heading("Top merchants")
    if merchants.empty:
        write("No merchant totals in this view.")
    else:
        for row in merchants.head(10).itertuples(index=False):
            write(f"{row.merchant}: {format_inr(row.spending)} · {int(row.transactions)} transactions")

    heading("Recurring payments")
    if not recurring:
        write("No monthly recurring payments were detected. This needs at least three similar charges about a month apart.")
    else:
        for item in recurring:
            write(
                f"{item.merchant}: {format_inr(item.typical_amount)} · {item.kind} · {item.occurrences} times · {item.note}"
            )

    heading("Items to review")
    if not anomalies:
        write("Nothing in this view stood out as unusual relative to the rest of the history.")
    else:
        for item in anomalies:
            write(f"{item.title}. {item.detail}")

    heading("Observations")
    for item in insights:
        write(f"{item.headline}. {item.explanation} {item.why_it_matters} {item.action}")

    heading("Where to look again")
    if not recommendations:
        write("No specific review point emerged from this history.")
    else:
        for item in recommendations:
            savings = ""
            if item.potential_monthly_savings is not None and item.savings_basis:
                savings = f" Scenario: {item.savings_basis}"
            write(f"{item.priority.title()} · {item.title}. {item.why} {item.action}{savings}")

    heading("Largest transactions")
    largest = frame.assign(_debit=frame["debit"].fillna(0)).sort_values("_debit", ascending=False).head(12)
    for row in largest.itertuples(index=False):
        write(
            f"{format_date(row.date)} · {row.merchant} · {format_inr(row.debit)} · {row.category}"
        )

    pdf.ln(4)
    write(
        "Automated categories can be wrong. Low-confidence rows are suggestions. This report is a personal review aid, not tax, credit, or investment advice.",
        size=9,
    )
    return bytes(pdf.output())


def _summary_sheet(writer, kpis, demo: bool) -> None:
    rows = [
        ("Total spending", kpis.total_spending),
        ("Average monthly spending", kpis.average_monthly),
        ("Largest category", kpis.top_category),
        ("Largest category amount", kpis.top_category_amount),
        ("Spending transactions", kpis.spending_transactions),
        ("All transactions", kpis.all_transactions),
        ("Comparison", kpis.mom_label),
        ("Change", None if kpis.mom_change is None else round(kpis.mom_change, 4)),
        ("Period", kpis.period_label),
        ("Currency", kpis.currency),
        ("Demo data", "Yes" if demo else "No"),
        ("Average note", kpis.average_note),
        ("Comparison note", kpis.mom_note),
    ]
    pd.DataFrame(rows, columns=["Metric", "Value"]).to_excel(writer, sheet_name="Summary", index=False)


def _monthly_export(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame(columns=["Month", "Spending", "Transactions"])
    export = monthly.copy()
    export["Month"] = pd.to_datetime(export["month_start"]).dt.strftime("%b %Y")
    return export[["Month", "spending", "transactions"]].rename(columns={"spending": "Spending", "transactions": "Transactions"})


def _category_export(categories: pd.DataFrame) -> pd.DataFrame:
    if categories.empty:
        return pd.DataFrame(columns=["Category", "Spending", "Transactions", "Share"])
    export = categories.copy()
    export["Share"] = export["share"].map(lambda value: None if pd.isna(value) else round(float(value), 4))
    return export.rename(columns={"category": "Category", "spending": "Spending", "transactions": "Transactions"})[
        ["Category", "Spending", "Transactions", "Share"]
    ]


def _recurring_export(items: list[RecurringPayment]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Merchant": item.merchant,
                "Category": item.category,
                "Monthly amount": item.typical_amount,
                "Occurrences": item.occurrences,
                "Cadence days": item.cadence_days,
                "Kind": item.kind,
                "Last date": item.last_date.isoformat(),
                "Note": item.note,
            }
            for item in items
        ]
    )


def _anomaly_export(items: list[Anomaly]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Kind": item.kind,
                "Title": item.title,
                "Detail": item.detail,
                "Amount": item.amount,
                "Date": None if item.when is None else item.when.isoformat(),
                "Merchant": item.merchant,
            }
            for item in items
        ]
    )


def _recommendation_export(items) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Priority": item.priority,
                "Title": item.title,
                "What": item.what,
                "Amount": item.amount,
                "Change": item.change_text,
                "Why": item.why,
                "Action": item.action,
                "Scenario savings": item.potential_monthly_savings,
                "Scenario basis": item.savings_basis,
            }
            for item in items
        ]
    )


def _insight_export(items) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Headline": item.headline,
                "Explanation": item.explanation,
                "Figures": "; ".join(item.figures),
                "Period": item.period,
                "Why it matters": item.why_it_matters,
                "Action": item.action,
            }
            for item in items
        ]
    )


def _transaction_export(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "merchant",
        "description",
        "debit",
        "credit",
        "currency",
        "category",
        "subcategory",
        "transaction_type",
        "confidence",
        "method",
        "counts_as_spend",
        "needs_review",
        "review_reason",
        "flagged",
        "is_duplicate",
        "account_label",
        "source_file",
    ]
    export = frame.copy()
    export["date"] = pd.to_datetime(export["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return export[[column for column in columns if column in export.columns]]


def _write(writer, name: str, frame: pd.DataFrame) -> None:
    (frame if frame is not None else pd.DataFrame()).to_excel(writer, sheet_name=name[:31], index=False)


def _style_workbook(workbook) -> None:
    for sheet in workbook.worksheets:
        if not sheet.max_row or sheet.max_row < 1 or not sheet.max_column:
            continue
        sheet.freeze_panes = "A2"
        if sheet.dimensions:
            sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(vertical="center")
        for column in sheet.columns:
            letter = get_column_letter(column[0].column)
            width = min(max(len(str(cell.value or "")) for cell in column[:40]) + 2, 48)
            sheet.column_dimensions[letter].width = max(width, 12)
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.sheet_properties.pageSetUpPr.fitToPage = True

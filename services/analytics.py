"""Spending math shared by the dashboard, the insights, and the report.

Totals net refunds. Income, transfers, investments, unclassified credits,
and duplicate rows are tracked separately and kept out of spending.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from utils.formatting import format_date, format_month
from utils.helpers import is_partial_month, safe_divide


@dataclass
class Kpis:
    total_spending: float
    average_monthly: float
    average_note: str
    period_label: str
    top_category: str
    top_category_amount: float
    top_category_share: float | None
    spending_transactions: int
    all_transactions: int
    mom_change: float | None
    mom_label: str
    mom_note: str
    currency: str
    mixed_currency: bool


def spending_view(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows that affect spending, with a signed `spend` column."""
    if frame is None or frame.empty:
        return pd.DataFrame(columns=list(frame.columns) + ["spend"] if frame is not None else ["spend"])
    view = frame[frame["counts_as_spend"].fillna(False)].copy()
    view = view[pd.to_datetime(view["date"], errors="coerce").notna()]
    view["date"] = pd.to_datetime(view["date"])
    view["spend"] = view["debit"].fillna(0).astype(float) - view["credit"].fillna(0).astype(float)
    return view


def filter_by_period(frame: pd.DataFrame, period: str, today: date | None = None) -> pd.DataFrame:
    """Limit a ledger to the period the user picked. Undated rows stay visible."""
    if frame is None or frame.empty or period in {None, "", "All months"}:
        return frame.copy() if frame is not None else pd.DataFrame()

    dated = frame[pd.to_datetime(frame["date"], errors="coerce").notna()].copy()
    if dated.empty:
        return frame.copy()

    latest = pd.to_datetime(dated["date"]).max()
    month_start = latest.replace(day=1)
    if period == "Latest month":
        start, end = month_start, latest
    elif period == "Previous month":
        start = (month_start - pd.DateOffset(months=1)).replace(day=1)
        end = month_start - pd.Timedelta(days=1)
    elif period == "Last 3 months":
        start = (month_start - pd.DateOffset(months=2)).replace(day=1)
        end = latest
    elif period == "Last 6 months":
        start = (month_start - pd.DateOffset(months=5)).replace(day=1)
        end = latest
    else:
        return frame.copy()

    stamps = pd.to_datetime(frame["date"], errors="coerce")
    mask = stamps.isna() | ((stamps >= start) & (stamps <= end))
    return frame.loc[mask].copy()


def dominant_currency(frame: pd.DataFrame) -> tuple[str, bool]:
    if frame is None or frame.empty or "currency" not in frame.columns:
        return "INR", False
    series = frame["currency"].fillna("INR").replace("", "INR")
    counts = series.value_counts()
    if counts.empty:
        return "INR", False
    return str(counts.index[0]), len(counts) > 1


def month_totals(spend: pd.DataFrame) -> pd.DataFrame:
    columns = ["month", "month_start", "spending", "transactions"]
    if spend.empty:
        return pd.DataFrame(columns=columns)
    work = spend.copy()
    work["month_start"] = work["date"].dt.to_period("M").dt.to_timestamp()
    grouped = (
        work.groupby("month_start", as_index=False)
        .agg(spending=("spend", "sum"), transactions=("spend", "size"))
        .sort_values("month_start")
    )
    grouped["month"] = grouped["month_start"].dt.strftime("%Y-%m")
    return grouped[columns]


def category_breakdown(spend: pd.DataFrame) -> pd.DataFrame:
    columns = ["category", "spending", "transactions", "share"]
    if spend.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        spend.groupby("category", as_index=False)
        .agg(spending=("spend", "sum"), transactions=("spend", "size"))
        .sort_values("spending", ascending=False)
    )
    positive = grouped["spending"].clip(lower=0)
    total = float(positive.sum())
    grouped["share"] = positive / total if total else 0.0
    return grouped


def category_by_month(spend: pd.DataFrame) -> pd.DataFrame:
    columns = ["month_start", "month", "category", "spending"]
    if spend.empty:
        return pd.DataFrame(columns=columns)
    work = spend.copy()
    work["month_start"] = work["date"].dt.to_period("M").dt.to_timestamp()
    grouped = work.groupby(["month_start", "category"], as_index=False)["spend"].sum()
    grouped = grouped.rename(columns={"spend": "spending"})
    grouped["month"] = grouped["month_start"].dt.strftime("%Y-%m")
    return grouped.sort_values(["month_start", "spending"], ascending=[True, False])


def daily_totals(spend: pd.DataFrame) -> pd.DataFrame:
    if spend.empty:
        return pd.DataFrame(columns=["date", "spending"])
    grouped = spend.groupby(spend["date"].dt.normalize(), as_index=False)["spend"].sum()
    return grouped.rename(columns={"date": "date", "spend": "spending"})


def merchant_totals(spend: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    columns = ["merchant", "spending", "transactions", "share"]
    if spend.empty:
        return pd.DataFrame(columns=columns)
    work = spend[spend["spend"] > 0]
    if work.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        work.groupby("merchant", as_index=False)
        .agg(spending=("spend", "sum"), transactions=("spend", "size"))
        .sort_values(["spending", "transactions"], ascending=False)
    )
    total = float(grouped["spending"].sum())
    grouped["share"] = grouped["spending"] / total if total else 0
    return grouped.head(limit)


def merchant_frequency(spend: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    columns = ["merchant", "transactions", "spending"]
    if spend.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        spend.groupby("merchant", as_index=False)
        .agg(transactions=("spend", "size"), spending=("spend", "sum"))
        .sort_values(["transactions", "spending"], ascending=False)
    )
    return grouped.head(limit)


def largest_transactions(frame: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work[work["debit"].fillna(0) > 0]
    return work.sort_values("debit", ascending=False).head(limit)


def behavior(spend: pd.DataFrame) -> dict:
    """Weekday and weekend pace across the span of the data, not only active days."""
    empty = {
        "weekend_total": 0.0,
        "weekday_total": 0.0,
        "weekend_daily": None,
        "weekday_daily": None,
        "weekend_days": 0,
        "weekday_days": 0,
        "average_transaction": None,
        "delivery_weekend_daily": None,
        "delivery_weekday_daily": None,
        "delivery_total": 0.0,
        "food_total": 0.0,
    }
    if spend.empty:
        return empty

    start = spend["date"].min().normalize()
    end = spend["date"].max().normalize()
    span = pd.date_range(start, end, freq="D")
    weekend_days = int((span.dayofweek >= 5).sum())
    weekday_days = int((span.dayofweek < 5).sum())
    is_weekend = spend["date"].dt.dayofweek >= 5
    weekend_total = float(spend.loc[is_weekend, "spend"].sum())
    weekday_total = float(spend.loc[~is_weekend, "spend"].sum())
    delivery = spend[spend["subcategory"] == "Food Delivery"]
    delivery_weekend = float(delivery.loc[delivery["date"].dt.dayofweek >= 5, "spend"].sum())
    delivery_weekday = float(delivery.loc[delivery["date"].dt.dayofweek < 5, "spend"].sum())
    positive = spend.loc[spend["spend"] > 0, "spend"]
    return {
        "weekend_total": weekend_total,
        "weekday_total": weekday_total,
        "weekend_daily": safe_divide(weekend_total, weekend_days),
        "weekday_daily": safe_divide(weekday_total, weekday_days),
        "weekend_days": weekend_days,
        "weekday_days": weekday_days,
        "average_transaction": float(positive.mean()) if len(positive) else None,
        "delivery_weekend_daily": safe_divide(delivery_weekend, weekend_days),
        "delivery_weekday_daily": safe_divide(delivery_weekday, weekday_days),
        "delivery_total": float(delivery["spend"].sum()),
        "food_total": float(spend.loc[spend["category"] == "Food & Dining", "spend"].sum()),
    }


def small_purchases(spend: pd.DataFrame, threshold: float) -> dict:
    if spend.empty:
        return {"count": 0, "total": 0.0, "share": None, "threshold": threshold}
    small = spend[(spend["spend"] > 0) & (spend["spend"] < threshold)]
    total_positive = float(spend.loc[spend["spend"] > 0, "spend"].sum())
    small_total = float(small["spend"].sum())
    return {
        "count": int(len(small)),
        "total": small_total,
        "share": safe_divide(small_total, total_positive),
        "threshold": threshold,
    }


def reconciliation(frame: pd.DataFrame, currency: str) -> dict:
    """Explain the gap between bank debits and the spending total."""
    if frame.empty:
        return {
            "spending": 0.0,
            "refunds": 0.0,
            "income": 0.0,
            "investments": 0.0,
            "transfers": 0.0,
            "duplicates": 0,
            "cash": 0.0,
            "needs_review": 0,
        }
    work = frame.copy()
    work = work[work["currency"].fillna("INR") == currency]
    active = work[~work["is_duplicate"].fillna(False)].copy()
    active["signed"] = active["debit"].fillna(0) - active["credit"].fillna(0)

    def _sum(mask) -> float:
        return float(active.loc[mask, "signed"].sum())

    return {
        "spending": _sum(active["counts_as_spend"].fillna(False)),
        "refunds": float(active.loc[active["transaction_type"] == "refund", "credit"].fillna(0).sum()),
        "income": float(active.loc[active["transaction_type"] == "income", "credit"].fillna(0).sum()),
        "investments": float(active.loc[active["transaction_type"] == "investment", "debit"].fillna(0).sum()),
        "transfers": float(active.loc[active["transaction_type"] == "transfer", "debit"].fillna(0).sum()),
        "duplicates": int(work["is_duplicate"].fillna(False).sum()),
        "cash": _sum(active["category"] == "Cash Withdrawals"),
        "needs_review": int(work["needs_review"].fillna(False).sum()),
    }


def consistency(monthly: pd.DataFrame) -> dict:
    if monthly.empty or len(monthly) < 2:
        return {"cv": None, "label": "There is not enough history yet to talk about consistency."}
    values = monthly["spending"].astype(float)
    mean = float(values.mean())
    if abs(mean) < 1e-9:
        return {"cv": None, "label": "Spending totals are too small to judge consistency."}
    cv = float(values.std(ddof=0) / abs(mean))
    if cv < 0.15:
        label = "Month to month, spending stays relatively steady."
    elif cv < 0.35:
        label = "Spending moves around a bit from month to month."
    else:
        label = "Spending swings quite a bit between months."
    return {"cv": cv, "label": label}


def compute_kpis(
    period_df: pd.DataFrame,
    full_df: pd.DataFrame,
    period_name: str,
    today: date | None = None,
) -> Kpis:
    today = today or date.today()
    currency, mixed = dominant_currency(period_df if not period_df.empty else full_df)
    period_spend = spending_view(_currency_slice(period_df, currency))
    full_spend = spending_view(_currency_slice(full_df, currency))

    total = float(period_spend["spend"].sum()) if not period_spend.empty else 0.0
    monthly = month_totals(period_spend)
    full_monthly = month_totals(full_spend)
    average, average_note = _average_monthly(monthly, full_spend, today)
    categories = category_breakdown(period_spend)
    if categories.empty or float(categories.iloc[0]["spending"]) <= 0:
        top_name, top_amount, top_share = "—", 0.0, None
    else:
        top = categories.iloc[0]
        top_name = str(top["category"])
        top_amount = float(top["spending"])
        top_share = float(top["share"]) if pd.notna(top["share"]) else None

    mom_change, mom_label, mom_note = _month_over_month(full_monthly, full_spend, period_name, today)
    period_label = _span_label(period_spend if not period_spend.empty else full_spend)

    return Kpis(
        total_spending=total,
        average_monthly=average,
        average_note=average_note,
        period_label=period_label,
        top_category=top_name,
        top_category_amount=top_amount,
        top_category_share=top_share,
        spending_transactions=int(len(period_spend)),
        all_transactions=int(len(period_df)),
        mom_change=mom_change,
        mom_label=mom_label,
        mom_note=mom_note,
        currency=currency,
        mixed_currency=mixed,
    )


def _currency_slice(frame: pd.DataFrame, currency: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    return frame[frame["currency"].fillna("INR") == currency].copy()


def _span_label(spend: pd.DataFrame) -> str:
    if spend.empty:
        return "No spending in this period"
    start = spend["date"].min().date()
    end = spend["date"].max().date()
    if start == end:
        return format_date(start)
    return f"{format_date(start)} – {format_date(end)}"


def _average_monthly(monthly: pd.DataFrame, full_spend: pd.DataFrame, today: date) -> tuple[float, str]:
    if monthly.empty:
        return 0.0, "No complete or partial month to average yet."
    partial_keys = _partial_keys(full_spend, today)
    complete = monthly[~monthly["month"].isin(partial_keys)]
    if not complete.empty:
        note = f"Average of {len(complete)} complete month(s)."
        if len(complete) != len(monthly):
            note += " The open month is included in total spending, not in this average."
        return float(complete["spending"].mean()), note
    return float(monthly["spending"].mean()), "Only a partial month is available, so this is spending so far."


def _partial_keys(full_spend: pd.DataFrame, today: date) -> set[str]:
    if full_spend.empty:
        return set()
    last_date = full_spend["date"].max().date()
    if is_partial_month(last_date, today):
        return {last_date.strftime("%Y-%m")}
    return set()


def _month_over_month(
    monthly: pd.DataFrame,
    full_spend: pd.DataFrame,
    period_name: str,
    today: date,
) -> tuple[float | None, str, str]:
    if monthly.empty:
        return None, "No prior month", "Upload more than one month to see a comparison."

    partial = _partial_keys(full_spend, today)
    rows = monthly.reset_index(drop=True)
    last_is_partial = str(rows.iloc[-1]["month"]) in partial

    if period_name == "Latest month" and last_is_partial and len(rows) >= 2 and not full_spend.empty:
        current = rows.iloc[-1]
        previous = rows.iloc[-2]
        last_date = full_spend["date"].max().date()
        days_elapsed = max(last_date.day, 1)
        prev_start = previous["month_start"].date() if isinstance(previous["month_start"], datetime) else previous["month_start"]
        days_prev = calendar.monthrange(prev_start.year, prev_start.month)[1]
        pace_now = float(current["spending"]) / days_elapsed
        pace_prev = float(previous["spending"]) / days_prev
        change = safe_divide(pace_now - pace_prev, abs(pace_prev))
        label = f"Pace vs {format_month(previous['month_start'])}"
        note = (
            f"{format_month(current['month_start'])} runs through {format_date(last_date)}, "
            f"so this is daily pace against {format_month(previous['month_start'])}, not a full-month total."
        )
        return change, label, note

    if period_name == "Previous month":
        target_index = -2 if len(rows) >= 2 else None
        prior_index = -3 if len(rows) >= 3 else None
    elif last_is_partial:
        target_index = -2 if len(rows) >= 2 else None
        prior_index = -3 if len(rows) >= 3 else None
    else:
        target_index = -1 if len(rows) >= 1 else None
        prior_index = -2 if len(rows) >= 2 else None

    if target_index is None or prior_index is None:
        if last_is_partial:
            return None, "Not enough complete months", "A change needs two finished months. The latest month is still open."
        return None, "No prior month", "Upload an earlier month to see the change."

    target = rows.iloc[target_index]
    prior = rows.iloc[prior_index]
    change = safe_divide(float(target["spending"]) - float(prior["spending"]), abs(float(prior["spending"])))
    label = f"{format_month(target['month_start'])} vs {format_month(prior['month_start'])}"
    note = ""
    if last_is_partial and period_name != "Previous month":
        last_date = full_spend["date"].max().date()
        note = (
            f"{format_month(rows.iloc[-1]['month_start'])} is still open (through {format_date(last_date)}), "
            "so it is not used in this comparison."
        )
    return change, label, note

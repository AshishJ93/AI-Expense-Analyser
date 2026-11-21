"""Point at transactions and months that deserve a second look.

These are not fraud findings. A large, planned purchase can look unusual
next to everyday spending and still be entirely expected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from services.analytics import category_by_month, spending_view


@dataclass
class Anomaly:
    kind: str
    title: str
    detail: str
    amount: float | None
    when: date | None
    merchant: str | None
    transaction_id: str | None


def detect_anomalies(frame: pd.DataFrame) -> list[Anomaly]:
    if frame is None or frame.empty:
        return []

    found: list[Anomaly] = []
    found.extend(_amount_outliers(frame))
    found.extend(_category_spikes(frame))
    found.extend(_duplicate_rows(frame))
    found.extend(_similar_pairs(frame))
    found.sort(key=lambda item: (item.kind != "unusual_amount", -(item.amount or 0)))
    return found[:12]


def _amount_outliers(frame: pd.DataFrame) -> list[Anomaly]:
    spend = spending_view(frame)
    if spend.empty:
        return []
    results = []
    skipped = {"Rent & Housing", "Insurance", "Investments", "Income"}
    for category, group in spend.groupby("category"):
        if category in skipped:
            continue
        amounts = group.loc[group["spend"] > 0, "spend"]
        if len(amounts) < 6:
            continue
        median = float(amounts.median())
        mad = float((amounts - median).abs().median())
        cutoff = max(median * 3, median + 3 * mad)
        outliers = group[(group["spend"] >= cutoff) & (group["spend"] > 0)]
        for row in outliers.itertuples(index=False):
            when = _as_date(row.date)
            results.append(
                Anomaly(
                    kind="unusual_amount",
                    title=f"{row.merchant} is larger than your usual {category.lower()} spending",
                    detail=(
                        f"{_money(row.spend)} on {when:%d %b %Y}. "
                        f"Your typical {category.lower()} transaction is about {_money(median)}. "
                        "It may be a planned purchase. It is listed so you can confirm it."
                    ),
                    amount=float(row.spend),
                    when=when,
                    merchant=str(row.merchant),
                    transaction_id=str(row.transaction_id),
                )
            )
    return results


def _category_spikes(frame: pd.DataFrame) -> list[Anomaly]:
    spend = spending_view(frame)
    monthly = category_by_month(spend)
    if monthly.empty:
        return []
    results = []
    for category, group in monthly.groupby("category"):
        group = group.sort_values("month_start").reset_index(drop=True)
        if len(group) < 4 or category in {"Rent & Housing", "Insurance", "Income"}:
            continue
        best = None
        for index in range(3, len(group)):
            latest = group.iloc[index]
            prior = group.iloc[:index]["spending"].astype(float)
            baseline = float(prior.median())
            latest_amount = float(latest["spending"])
            if baseline < 1000 or latest_amount < baseline * 2 or latest_amount - baseline < 3000:
                continue
            if best is None or latest_amount > best[0]:
                best = (latest_amount, baseline, latest)
        if best is None:
            continue
        latest_amount, baseline, latest = best
        results.append(
            Anomaly(
                kind="category_spike",
                title=f"{category} jumped in {_month(latest.month_start)}",
                detail=(
                    f"{category} was {_money(latest_amount)} in {_month(latest.month_start)}, "
                    f"against about {_money(baseline)} in a typical earlier month. "
                    "A single planned purchase can cause this. The category page shows whether it is spreading."
                ),
                amount=latest_amount,
                when=_as_date(latest.month_start),
                merchant=None,
                transaction_id=None,
            )
        )
    return results


def _duplicate_rows(frame: pd.DataFrame) -> list[Anomaly]:
    results = []
    duplicates = frame[frame["is_duplicate"].fillna(False)]
    for row in duplicates.itertuples(index=False):
        amount = float(row.debit or 0) or float(row.credit or 0)
        when = _as_date(row.date)
        results.append(
            Anomaly(
                kind="possible_duplicate",
                title=f"Possible repeated import · {row.merchant}",
                detail=(
                    f"Another row already has the same description, amount ({_money(amount)}), and date. "
                    "It is excluded from totals. Restore it in Transactions if both charges were real."
                ),
                amount=amount,
                when=when,
                merchant=str(row.merchant),
                transaction_id=str(row.transaction_id),
            )
        )
    return results


def _similar_pairs(frame: pd.DataFrame) -> list[Anomaly]:
    work = frame[~frame["is_duplicate"].fillna(False)].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work[work["date"].notna() & (work["debit"].fillna(0) > 0)]
    results = []
    for merchant, group in work.groupby("merchant"):
        group = group.sort_values("date")
        rows = list(group.to_dict(orient="records"))
        for left, right in zip(rows, rows[1:]):
            gap = abs((right["date"] - left["date"]).days)
            if gap > 1:
                continue
            if round(float(left["debit"]), 2) != round(float(right["debit"]), 2):
                continue
            if str(left["description"]).strip().lower() == str(right["description"]).strip().lower():
                continue
            results.append(
                Anomaly(
                    kind="similar_pair",
                    title=f"Two similar {merchant} charges, one day apart",
                    detail=(
                        f"Both are {_money(left['debit'])}. The descriptions are not identical, "
                        "so both remain in your spending total. Check whether one is a retry or a second purchase."
                    ),
                    amount=float(left["debit"]),
                    when=_as_date(left["date"]),
                    merchant=str(merchant),
                    transaction_id=str(right["transaction_id"]),
                )
            )
            if len(results) >= 5:
                return results
    return results


def _as_date(value) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if isinstance(parsed, datetime):
        return parsed.date()
    return parsed.date()


def _month(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return "that month"
    return parsed.strftime("%b %Y")


def _money(value: float) -> str:
    from utils.formatting import format_inr

    return format_inr(value)

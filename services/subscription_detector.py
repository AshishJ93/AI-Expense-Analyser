"""Find payments that repeat about once a month.

A repeating amount is a hypothesis about cadence, not proof that a service
is unused.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

import pandas as pd

@dataclass
class RecurringPayment:
    merchant: str
    category: str
    typical_amount: float
    occurrences: int
    cadence_days: float
    last_date: date
    kind: str
    confidence: float
    note: str


def detect_recurring(frame: pd.DataFrame) -> list[RecurringPayment]:
    if frame is None or frame.empty:
        return []

    work = frame[~frame["is_duplicate"].fillna(False)].copy()
    work = work[work["transaction_type"].isin(["purchase", "fee", "investment"])]
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work[work["date"].notna() & (work["debit"].fillna(0) > 0)]
    found: list[RecurringPayment] = []

    for merchant, group in work.groupby(work["merchant"].fillna("Unknown merchant")):
        group = group.sort_values("date")
        if len(group) < 3 or str(merchant).strip() in {"", "Unknown merchant"}:
            continue
        amounts = [float(value) for value in group["debit"]]
        typical = float(statistics.median(amounts))
        if typical <= 0:
            continue
        close_rows = group[group["debit"].sub(typical).abs() / typical <= 0.15]
        if len(close_rows) < 3:
            continue
        dates = list(pd.to_datetime(close_rows["date"]))
        gaps = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates))]
        if not gaps:
            continue
        cadence = float(statistics.median(gaps))
        if cadence < 25 or cadence > 35:
            continue
        category = str(group["category"].mode().iloc[0]) if not group["category"].mode().empty else "Other"
        kind = _kind(category, str(group["transaction_type"].mode().iloc[0]))
        found.append(
            RecurringPayment(
                merchant=str(merchant),
                category=category,
                typical_amount=round(typical, 2),
                occurrences=int(len(close_rows)),
                cadence_days=cadence,
                last_date=dates[-1].date(),
                kind=kind,
                confidence=0.86 if kind == "subscription" else 0.74,
                note=_note(kind),
            )
        )
    return sorted(found, key=lambda item: item.typical_amount, reverse=True)


def subscription_monthly_total(items: list[RecurringPayment]) -> float:
    return float(sum(item.typical_amount for item in items if item.kind == "subscription"))


def _kind(category: str, transaction_type: str) -> str:
    if transaction_type == "investment" or category == "Investments":
        return "investment"
    if category == "Subscriptions":
        return "subscription"
    if category in {"Utilities & Bills", "Rent & Housing", "Insurance"}:
        return "bill"
    return "other"


def _note(kind: str) -> str:
    if kind == "subscription":
        return "The amount and the spacing look monthly. Only you know whether you still use it."
    if kind == "bill":
        return "This looks like a regular bill, not a discretionary subscription."
    if kind == "investment":
        return "This is money set aside on a schedule. It is not counted as spending."
    return "The charges repeat monthly. That alone does not say whether they are optional."

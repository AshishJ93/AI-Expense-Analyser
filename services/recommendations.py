"""Suggestions that stay specific, optional, and free of guilt.

A high amount is not treated as a mistake. Savings figures appear only when
the arithmetic is a scenario the user can check, never as a promise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from config.settings import BANNED_COPY, DISCRETIONARY, ESSENTIAL, VIDEO_MERCHANTS
from services.analytics import category_by_month, small_purchases, spending_view
from services.subscription_detector import RecurringPayment, detect_recurring
from utils.formatting import format_inr, format_month, format_percent
from utils.helpers import is_partial_month, safe_divide


@dataclass
class Recommendation:
    title: str
    priority: str
    what: str
    amount: float
    change_text: str
    why: str
    action: str
    potential_monthly_savings: float | None = None
    savings_basis: str | None = None


def build_recommendations(
    frame: pd.DataFrame,
    today: date | None = None,
    small_threshold: float = 500,
) -> list[Recommendation]:
    today = today or date.today()
    if frame is None or frame.empty:
        return []

    spend = spending_view(frame)
    if spend.empty:
        return []

    items: list[Recommendation] = []
    context = _month_context(spend, today)
    items.extend(_category_moves(spend, context))
    items.extend(_delivery(spend, context))
    items.extend(_overlaps(detect_recurring(frame)))
    items.extend(_small(spend, small_threshold, context))
    items.extend(_habits(frame, context))
    items = _dedupe(items)
    if any(item.what == "Food delivery" for item in items):
        items = [item for item in items if item.what != "Food & Dining"]
    return _limit_priority(items)


def _month_context(spend: pd.DataFrame, today: date) -> dict | None:
    monthly = category_by_month(spend)
    if monthly.empty:
        return None
    months = list(dict.fromkeys(monthly.sort_values("month_start")["month_start"].tolist()))
    last_date = spend["date"].max().date()
    partial = is_partial_month(last_date, today)
    if partial and len(months) >= 2:
        current = months[-2]
        earlier = months[:-2]
        open_month = months[-1]
    elif not partial:
        current = months[-1]
        earlier = months[:-1]
        open_month = None
    else:
        return {
            "current": months[-1],
            "earlier": [],
            "open_month": months[-1],
            "partial_only": True,
            "last_date": last_date,
        }
    baseline_months = earlier[-3:]
    return {
        "current": current,
        "earlier": baseline_months,
        "open_month": open_month,
        "partial_only": False,
        "last_date": last_date,
        "table": monthly,
    }


def _category_amount(table: pd.DataFrame, month, category: str) -> float:
    rows = table[(table["month_start"] == month) & (table["category"] == category)]
    if rows.empty:
        return 0.0
    return float(rows["spending"].sum())


def _category_moves(spend: pd.DataFrame, context: dict | None) -> list[Recommendation]:
    if not context or context.get("partial_only") or not context["earlier"]:
        return []
    table = context["table"]
    current = context["current"]
    current_label = format_month(current)
    baseline_label = _range_label(context["earlier"])
    items = []
    categories = sorted(set(table["category"]))
    for category in categories:
        current_amount = _category_amount(table, current, category)
        baseline_values = [_category_amount(table, month, category) for month in context["earlier"]]
        baseline = sum(baseline_values) / len(baseline_values)
        change = safe_divide(current_amount - baseline, abs(baseline)) if baseline else None
        if current_amount <= 0 and (change is None or change >= 0):
            continue
        increase = current_amount - baseline
        concentrated, top_share, top_merchant, top_amount = _concentration(spend, current, category, increase)

        if change is not None and change <= -0.15 and baseline >= 2000 and category in DISCRETIONARY:
            items.append(
                Recommendation(
                    title=f"{category} has eased",
                    priority="habit",
                    what=category,
                    amount=current_amount,
                    change_text=f"{format_percent(change)} versus {baseline_label}",
                    why=f"In {current_label} this was {format_inr(current_amount)}, compared with about {format_inr(baseline)} before that.",
                    action="No action needed. It is simply a pattern worth keeping in view if it was intentional.",
                )
            )
            continue

        if change is None or change < 0.10 or current_amount < 2000:
            continue

        if category in ESSENTIAL:
            items.append(
                Recommendation(
                    title=f"{category} is higher than your recent months",
                    priority="review",
                    what=category,
                    amount=current_amount,
                    change_text=f"{format_percent(change)} versus {baseline_label}",
                    why=(
                        f"{current_label} was {format_inr(current_amount)}, against about {format_inr(baseline)} "
                        f"in {baseline_label}. Essentials move with prices, household size, and season. "
                        "A higher bill is not a verdict on the spending."
                    ),
                    action="If the increase matches a bill you expected, you can leave it. If it does not, the transaction list will show which charge changed.",
                )
            )
            continue

        if category not in DISCRETIONARY and category not in {"Cash Withdrawals", "Other"}:
            continue

        if concentrated:
            items.append(
                Recommendation(
                    title=f"{category} rose mostly because of one transaction",
                    priority="review",
                    what=category,
                    amount=current_amount,
                    change_text=f"{format_percent(change)} versus {baseline_label}",
                    why=(
                        f"{top_merchant} was {format_inr(top_amount)}, about {format_percent(top_share, signed=False)} of the increase. "
                        f"The rest of {category.lower()} in {current_label} does not show the same jump."
                    ),
                    action="If this was a planned purchase, nothing needs to change. If purchases of this size are becoming frequent, it may be worth a pause before the next one.",
                )
            )
            continue

        priority = "high" if change >= 0.25 and current_amount >= 4000 and category in DISCRETIONARY else "review"
        items.append(
            Recommendation(
                title=f"Consider reviewing {category.lower()}",
                priority=priority,
                what=category,
                amount=current_amount,
                change_text=f"{format_percent(change)} versus {baseline_label}",
                why=(
                    f"You spent {format_inr(current_amount)} on {category.lower()} in {current_label}. "
                    f"The recent average before that was about {format_inr(baseline)}."
                ),
                action="Look at the merchants in this category and decide which ones you want to keep at this level. There is no assumption that the spending is unnecessary.",
            )
        )
    return items


def _delivery(spend: pd.DataFrame, context: dict | None) -> list[Recommendation]:
    if not context or context.get("partial_only") or not context["earlier"]:
        return []
    delivery = spend[spend["subcategory"] == "Food Delivery"].copy()
    if delivery.empty:
        return []
    delivery["month_start"] = delivery["date"].dt.to_period("M").dt.to_timestamp()
    current = context["current"]
    current_amount = float(delivery.loc[delivery["month_start"] == current, "spend"].sum())
    baseline_values = [
        float(delivery.loc[delivery["month_start"] == month, "spend"].sum()) for month in context["earlier"]
    ]
    baseline = sum(baseline_values) / len(baseline_values) if baseline_values else 0
    change = safe_divide(current_amount - baseline, abs(baseline)) if baseline else None
    if current_amount < 2500 or change is None or change < 0.15:
        return []
    food = float(spend.loc[(spend["category"] == "Food & Dining") & (spend["date"].dt.to_period("M").dt.to_timestamp() == current), "spend"].sum())
    share = safe_divide(current_amount, food) if food > 0 else None
    share_text = f" That was {format_percent(share, signed=False)} of food spending that month." if share else ""
    savings = round(current_amount * 0.15, 2)
    return [
        Recommendation(
            title="Food delivery is taking a larger share than it recently did",
            priority="high" if change >= 0.25 and current_amount >= 4000 else "review",
            what="Food delivery",
            amount=current_amount,
            change_text=f"{format_percent(change)} versus {_range_label(context['earlier'])}",
            why=(
                f"Delivery was {format_inr(current_amount)} in {format_month(current)}, "
                f"compared with about {format_inr(baseline)} in the months before.{share_text}"
            ),
            action="You could keep the orders you enjoy and trim the ones that are mostly convenience. A specific target is optional.",
            potential_monthly_savings=savings,
            savings_basis=(
                f"A scenario, not a target: 15% of {format_month(current)} delivery "
                f"({format_inr(current_amount)}) is {format_inr(savings)}. Use it only if that kind of trim feels realistic."
            ),
        )
    ]


def _overlaps(recurring: list[RecurringPayment]) -> list[Recommendation]:
    video = [item for item in recurring if item.merchant.lower() in VIDEO_MERCHANTS and item.kind == "subscription"]
    if len(video) < 2:
        return []
    video = sorted(video, key=lambda item: item.typical_amount)
    smallest = video[0]
    names = ", ".join(item.merchant for item in video)
    return [
        Recommendation(
            title="You may be paying for more than one video service",
            priority="review",
            what="Video subscriptions",
            amount=sum(item.typical_amount for item in video),
            change_text=f"{len(video)} monthly charges",
            why=(
                f"{names} each recur monthly. Together they are about "
                f"{format_inr(sum(item.typical_amount for item in video))} a month. "
                "This is a hypothesis about overlap, not a finding that any of them is unused. "
                "Prime, in particular, is sometimes kept for shipping rather than video."
            ),
            action="If you use all of them, keep them. If one is idle, the smaller bill is the one people usually reconsider first.",
            potential_monthly_savings=smallest.typical_amount,
            savings_basis=(
                f"If {smallest.merchant} ({format_inr(smallest.typical_amount)} a month) were the one you dropped, "
                "that is the monthly difference. It is a scenario, not a recommendation to cancel."
            ),
        )
    ]


def _small(spend: pd.DataFrame, threshold: float, context: dict | None) -> list[Recommendation]:
    summary = small_purchases(spend, threshold)
    if summary["count"] < 12 or summary["total"] < 4000:
        return []
    if summary["total"] < 15000 and (summary["share"] is None or summary["share"] < 0.08):
        return []
    share = format_percent(summary["share"], signed=False) if summary["share"] is not None else "a visible share"
    return [
        Recommendation(
            title="Small purchases are adding up",
            priority="review",
            what=f"Transactions under {format_inr(threshold)}",
            amount=summary["total"],
            change_text=f"{summary['count']} transactions · {share} of spending",
            why=(
                f"Purchases under {format_inr(threshold)} come to {format_inr(summary['total'])} in this view. "
                "Each one is minor. Together they are a line of spending you can actually see."
            ),
            action="Scan the list for the ones you would not miss. There is no reliable way to turn that into a savings promise, so none is shown.",
        )
    ]


def _habits(frame: pd.DataFrame, context: dict | None) -> list[Recommendation]:
    investments = frame[(frame["transaction_type"] == "investment") & ~frame["is_duplicate"].fillna(False)].copy()
    if investments.empty:
        return []
    investments["date"] = pd.to_datetime(investments["date"], errors="coerce")
    months = investments["date"].dt.to_period("M").nunique()
    if months < 3:
        return []
    monthly_amount = float(investments["debit"].sum()) / months
    return [
        Recommendation(
            title="You have been setting money aside",
            priority="habit",
            what="Investments",
            amount=monthly_amount,
            change_text=f"Present in {int(months)} months",
            why=(
                f"Investment transfers average about {format_inr(monthly_amount)} a month across {int(months)} months. "
                "They are kept out of spending totals so they are not mistaken for lifestyle costs."
            ),
            action="If that amount still matches what you meant to set aside, it is a steady habit worth leaving alone.",
        )
    ]


def _concentration(spend: pd.DataFrame, month, category: str, increase: float) -> tuple[bool, float | None, str, float]:
    if increase <= 0:
        return False, None, "", 0.0
    window = spend.copy()
    window["month_start"] = window["date"].dt.to_period("M").dt.to_timestamp()
    rows = window[(window["month_start"] == month) & (window["category"] == category) & (window["spend"] > 0)]
    if rows.empty:
        return False, None, "", 0.0
    top = rows.sort_values("spend", ascending=False).iloc[0]
    top_amount = float(top["spend"])
    share = safe_divide(top_amount, increase)
    concentrated = share is not None and share >= 0.5 and top_amount >= 5000
    return concentrated, share, str(top["merchant"]), top_amount


def _range_label(months: list) -> str:
    if not months:
        return "the earlier months"
    if len(months) == 1:
        return format_month(months[0])
    return f"{format_month(months[0])}–{format_month(months[-1])}"


def _dedupe(items: list[Recommendation]) -> list[Recommendation]:
    seen = set()
    unique = []
    for item in items:
        if item.title in seen:
            continue
        seen.add(item.title)
        unique.append(item)
    return unique


def _limit_priority(items: list[Recommendation]) -> list[Recommendation]:
    high = [item for item in items if item.priority == "high"]
    high.sort(key=lambda item: item.amount, reverse=True)
    kept_high = {item.title for item in high[:2]}
    adjusted = []
    for item in items:
        if item.priority == "high" and item.title not in kept_high:
            item.priority = "review"
        _assert_tone(item)
        adjusted.append(item)
    order = {"high": 0, "review": 1, "habit": 2}
    return sorted(adjusted, key=lambda item: (order.get(item.priority, 9), -item.amount))


def _assert_tone(item: Recommendation) -> None:
    blob = " ".join(
        [
            item.title,
            item.what,
            item.change_text,
            item.why,
            item.action,
            item.savings_basis or "",
        ]
    ).lower()
    for phrase in BANNED_COPY:
        if phrase in blob:
            raise ValueError(f"Recommendation copy contained '{phrase}'.")

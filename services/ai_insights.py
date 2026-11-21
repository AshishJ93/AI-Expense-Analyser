"""Observations computed from the ledger.

Every figure in an insight comes from the analytics functions. The optional
model briefing is allowed to rephrase those insights and is dropped if it
introduces a number that is not in the source.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import date

from config.settings import VIDEO_MERCHANTS
from services.analytics import (
    Kpis,
    behavior,
    category_breakdown,
    category_by_month,
    merchant_totals,
    small_purchases,
    spending_view,
)
from services.recommendations import Recommendation, build_recommendations
from services.subscription_detector import detect_recurring, subscription_monthly_total
from utils.formatting import format_inr, format_month, format_percent
from utils.helpers import is_partial_month, safe_divide


@dataclass
class Insight:
    headline: str
    explanation: str
    figures: list[str]
    period: str
    why_it_matters: str
    action: str
    tone: str


def build_insights(
    frame,
    kpis: Kpis,
    today: date | None = None,
    small_threshold: float = 500,
) -> list[Insight]:
    """Create grounded observations. Returns a limitation note when history is thin."""
    if frame is None or getattr(frame, "empty", True):
        return [_limited("Upload a statement to see observations based on your own transactions.")]

    spend = spending_view(frame)
    if spend.empty:
        return [_limited("None of the loaded rows are counted as spending yet. Check transfers and items marked for review.")]

    insights: list[Insight] = []
    if kpis.mom_note:
        insights.append(
            Insight(
                headline="The latest month is still open",
                explanation=kpis.mom_note,
                figures=[kpis.period_label],
                period=kpis.mom_label,
                why_it_matters="Comparing a partial month with a finished one makes spending look lower than it is.",
                action="Use the month-versus-month figure, which skips the open month, when you want a like-for-like reading.",
                tone="neutral",
            )
        )

    if kpis.top_category != "—":
        share = format_percent(kpis.top_category_share, signed=False) if kpis.top_category_share is not None else "—"
        insights.append(
            Insight(
                headline=f"{kpis.top_category} is your largest spending category",
                explanation=(
                    f"It accounts for {format_inr(kpis.top_category_amount)} "
                    f"({share} of spending in this view)."
                ),
                figures=[format_inr(kpis.top_category_amount), share],
                period=kpis.period_label,
                why_it_matters="The largest category is the clearest answer to where the money went. Size alone does not make it optional.",
                action="Open Categories if you want the merchants inside it.",
                tone="neutral",
            )
        )

    if kpis.mom_change is not None:
        direction = "higher" if kpis.mom_change > 0.005 else "lower" if kpis.mom_change < -0.005 else "about the same"
        insights.append(
            Insight(
                headline=f"Spending was {direction} in {kpis.mom_label}",
                explanation=f"The change is {format_percent(kpis.mom_change)}. {kpis.mom_note}".strip(),
                figures=[format_percent(kpis.mom_change)],
                period=kpis.mom_label,
                why_it_matters="A single month can move because of one bill or one trip. The category breakdown shows which one.",
                action="Treat a small move as noise. Look closer when a discretionary category is doing most of the shifting.",
                tone="attention" if kpis.mom_change >= 0.15 else "positive" if kpis.mom_change <= -0.1 else "neutral",
            )
        )

    insights.extend(_category_changes(spend, today or date.today()))
    insights.extend(_weekend_delivery(spend))
    insights.extend(_subscriptions(frame))
    insights.extend(_small(spend, small_threshold))
    insights.extend(_merchant(spend))
    insights.extend(_cash(spend))

    if len(insights) == 0:
        insights.append(_limited("There is not enough variation in this period to make a specific observation."))
    return insights[:8]


def insight_payload(insights: list[Insight], recommendations: list[Recommendation]) -> str:
    """Aggregated text the optional model is allowed to see. No raw narrations."""
    body = {
        "insights": [asdict(item) for item in insights],
        "recommendations": [
            {
                "title": item.title,
                "priority": item.priority,
                "what": item.what,
                "amount": item.amount,
                "change": item.change_text,
                "why": item.why,
                "action": item.action,
                "scenario_savings": item.potential_monthly_savings,
                "scenario_basis": item.savings_basis,
            }
            for item in recommendations
        ],
    }
    return json.dumps(body, default=str, ensure_ascii=False)


def narrative_is_grounded(narrative: str, source: str) -> bool:
    """Reject a briefing that introduces a number the ledger did not supply."""
    if not narrative or not narrative.strip():
        return False
    # A JSON unicode escape for the rupee sign contains digits. Strip it
    # before scanning, or those digits glue onto the amount that follows.
    source = source.replace("\\u20b9", "")
    narrative = narrative.replace("\\u20b9", "")
    source_numbers = {_normalize_number(value) for value in re.findall(r"\d[\d,]*(?:\.\d+)?", source)}
    for raw in re.findall(r"\d[\d,]*(?:\.\d+)?", narrative):
        if _normalize_number(raw) not in source_numbers:
            return False
    return True


def _category_changes(spend, today: date) -> list[Insight]:
    table = category_by_month(spend)
    if table.empty:
        return []
    months = list(dict.fromkeys(table.sort_values("month_start")["month_start"].tolist()))
    if len(months) < 2:
        return []
    last_date = spend["date"].max().date()
    if is_partial_month(last_date, today):
        if len(months) < 3:
            return []
        latest, prior = months[-2], months[-3]
    else:
        latest, prior = months[-1], months[-2]
    moves = []
    for category in table["category"].unique():
        now = float(table.loc[(table["month_start"] == latest) & (table["category"] == category), "spending"].sum())
        then = float(table.loc[(table["month_start"] == prior) & (table["category"] == category), "spending"].sum())
        if then < 500 and now < 500:
            continue
        change = safe_divide(now - then, abs(then)) if then else None
        if change is None:
            continue
        moves.append((abs(now - then), change, category, now, then))
    if not moves:
        return []
    moves.sort(reverse=True)
    _, change, category, now, then = moves[0]
    if abs(change) < 0.08:
        return []
    direction = "increased" if change > 0 else "decreased"
    tone = "attention" if change > 0 else "positive"
    return [
        Insight(
            headline=f"{category} {direction} from {format_month(prior)} to {format_month(latest)}",
            explanation=(
                f"It moved from {format_inr(then)} to {format_inr(now)}, a change of {format_percent(change)}."
            ),
            figures=[format_inr(then), format_inr(now), format_percent(change)],
            period=f"{format_month(latest)} vs {format_month(prior)}",
            why_it_matters="This is the sharpest category move in the loaded months. It may be one purchase or a real shift.",
            action="Check the largest transactions in that category before deciding it is a new pattern.",
            tone=tone,
        )
    ]


def _weekend_delivery(spend) -> list[Insight]:
    stats = behavior(spend)
    weekend = stats["delivery_weekend_daily"]
    weekday = stats["delivery_weekday_daily"]
    if not weekend or not weekday or weekday <= 0:
        return []
    ratio = weekend / weekday
    if ratio < 1.4 or stats["delivery_total"] < 2000:
        return []
    return [
        Insight(
            headline="Food delivery runs higher on weekends",
            explanation=(
                f"Weekend delivery averages {format_inr(weekend)} a day, against {format_inr(weekday)} on a weekday. "
                f"Delivery overall is {format_inr(stats['delivery_total'])} in this view."
            ),
            figures=[format_inr(weekend), format_inr(weekday), format_inr(stats["delivery_total"])],
            period="Across the loaded dates",
            why_it_matters="The pattern is in when the orders happen, which is more useful than a single monthly total.",
            action="If weekend orders are the ones you value, the weekday ones are the easier place to look.",
            tone="attention",
        )
    ]


def _subscriptions(frame) -> list[Insight]:
    recurring = [item for item in detect_recurring(frame) if item.kind == "subscription"]
    if len(recurring) < 2:
        return []
    total = subscription_monthly_total(detect_recurring(frame))
    names = ", ".join(item.merchant for item in recurring[:6])
    video = [item.merchant for item in recurring if item.merchant.lower() in VIDEO_MERCHANTS]
    extra = ""
    if len(video) >= 2:
        extra = f" {len(video)} of them are video services ({', '.join(video)}). That may be overlap, or you may use each one."
    return [
        Insight(
            headline=f"{len(recurring)} subscriptions recur at about {format_inr(total)} a month",
            explanation=f"Detected from repeating amounts: {names}.{extra}",
            figures=[str(len(recurring)), format_inr(total)],
            period="Months where the charge repeats",
            why_it_matters="Subscriptions are easy to stop noticing because each bill is small and regular.",
            action="Keep the ones you use. The list is a prompt to look, not a list of things to cancel.",
            tone="neutral",
        )
    ]


def _small(spend, threshold: float) -> list[Insight]:
    summary = small_purchases(spend, threshold)
    if summary["count"] < 12 or summary["total"] < 4000:
        return []
    share = format_percent(summary["share"], signed=False) if summary["share"] is not None else "—"
    return [
        Insight(
            headline=f"Purchases under {format_inr(threshold)} add up to {format_inr(summary['total'])}",
            explanation=f"{summary['count']} transactions, about {share} of positive spending in this view.",
            figures=[format_inr(summary["total"]), str(summary["count"]), share],
            period="This view",
            why_it_matters="Small charges rarely show up in a category chart, but the total can still be meaningful.",
            action="Sort the transaction list by amount if you want to see them together.",
            tone="neutral",
        )
    ]


def _merchant(spend) -> list[Insight]:
    merchants = merchant_totals(spend, limit=5)
    if merchants.empty:
        return []
    top = merchants.iloc[0]
    if float(top["share"]) < 0.12 or float(top["spending"]) < 3000:
        return []
    return [
        Insight(
            headline=f"{top['merchant']} is your largest merchant",
            explanation=(
                f"{format_inr(top['spending'])} across {int(top['transactions'])} transactions, "
                f"{format_percent(float(top['share']), signed=False)} of positive spending."
            ),
            figures=[format_inr(top["spending"]), str(int(top["transactions"]))],
            period="This view",
            why_it_matters="A single merchant can explain a category that otherwise looks broad.",
            action="If that merchant is expected, the category is less of a mystery.",
            tone="neutral",
        )
    ]


def _cash(spend) -> list[Insight]:
    cash = float(spend.loc[spend["category"] == "Cash Withdrawals", "spend"].sum())
    total = float(spend.loc[spend["spend"] > 0, "spend"].sum())
    share = safe_divide(cash, total)
    if cash < 5000 or share is None or share < 0.08:
        return []
    return [
        Insight(
            headline=f"Cash withdrawals come to {format_inr(cash)}",
            explanation=(
                f"That is {format_percent(share, signed=False)} of positive spending. "
                "Cash is included in the total, and it cannot be categorized further from the statement."
            ),
            figures=[format_inr(cash), format_percent(share, signed=False)],
            period="This view",
            why_it_matters="Whatever the cash was for stays invisible. That is a limit of the data, not a judgment.",
            action="No change is implied. If you want that spending categorized, it has to be tracked outside the ATM line.",
            tone="neutral",
        )
    ]


def _limited(message: str) -> Insight:
    return Insight(
        headline="Not enough history for a stronger reading",
        explanation=message,
        figures=[],
        period="—",
        why_it_matters="A pattern needs more than a handful of rows. Guessing would be worse than saying so.",
        action="Load at least two months when you want comparisons.",
        tone="neutral",
    )


def _normalize_number(raw: str) -> str:
    number = raw.replace(",", "")
    if number.endswith(".0"):
        number = number[:-2]
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return number


def recommendations_for(frame, today: date | None = None, small_threshold: float = 500) -> list[Recommendation]:
    return build_recommendations(frame, today=today, small_threshold=small_threshold)

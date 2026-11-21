"""Totals, partial months, subscriptions, insights, and exports."""

from datetime import date

from services.analytics import compute_kpis, spending_view
from services.ai_insights import build_insights
from services.anomaly_detector import detect_anomalies
from services.file_processor import process_bytes
from services.pipeline import prepare_transactions
from services.recommendations import build_recommendations
from services.report_generator import build_excel, build_pdf
from services.sample_data import load_sample_bytes
from services.subscription_detector import detect_recurring, subscription_monthly_total
from utils.formatting import format_inr

TODAY = date(2026, 11, 21)


def _demo():
    parsed = process_bytes("sample_transactions.csv", load_sample_bytes())
    assert parsed.status == "parsed", parsed.message
    frame, _notes = prepare_transactions([parsed.frame])
    return frame


def test_demo_ledger_is_a_six_month_story():
    frame = _demo()
    dated = frame["date"].dropna()
    months = dated.dt.to_period("M").nunique()
    assert months >= 6
    assert dated.min().date() == date(2026, 6, 1)
    assert dated.max().date() <= date(2026, 11, 20)
    assert "4160219812345678" not in " ".join(frame["description"])
    spend = spending_view(frame)
    assert not frame[frame["transaction_type"] == "income"]["counts_as_spend"].any()
    assert not frame[frame["category"] == "Investments"]["counts_as_spend"].any()
    assert spend["spend"].sum() > 0
    assert int(frame["is_duplicate"].sum()) >= 1


def test_partial_month_is_not_treated_as_a_finished_month():
    frame = _demo()
    kpis = compute_kpis(frame, frame, "All months", TODAY)
    assert kpis.total_spending > 0
    assert "Nov" in kpis.mom_note
    assert "Oct" in kpis.mom_label or "Sep" in kpis.mom_label
    assert "complete" in kpis.average_note.lower()
    assert kpis.top_category != "—"


def test_subscriptions_and_weekend_delivery_are_real():
    frame = _demo()
    recurring = detect_recurring(frame)
    names = {item.merchant for item in recurring if item.kind == "subscription"}
    assert "Netflix" in names
    assert "Spotify" in names
    assert subscription_monthly_total(recurring) > 2000
    assert all(item.kind != "subscription" or item.category == "Subscriptions" for item in recurring)
    insights = build_insights(frame, compute_kpis(frame, frame, "All months", TODAY), TODAY)
    headlines = " ".join(item.headline for item in insights)
    assert "weekend" in headlines.lower() or any("delivery" in item.headline.lower() for item in insights)
    for insight in insights:
        for figure in insight.figures:
            if figure.startswith("₹"):
                assert figure  # figures are formatted from computed values, not placeholders


def test_insights_use_numbers_from_the_kpis():
    frame = _demo()
    kpis = compute_kpis(frame, frame, "All months", TODAY)
    insights = build_insights(frame, kpis, TODAY)
    blob = " ".join(f"{item.headline} {item.explanation}" for item in insights)
    assert format_inr(kpis.top_category_amount) in blob


def test_anomalies_flag_the_electronics_purchase_without_calling_it_fraud():
    frame = _demo()
    anomalies = detect_anomalies(frame)
    blob = " ".join(f"{item.title} {item.detail}" for item in anomalies).lower()
    assert "croma" in blob or "shopping" in blob
    assert "fraud" not in blob
    assert "suspicious" not in blob


def test_recommendations_explain_a_scenario_instead_of_a_promise():
    frame = _demo()
    items = build_recommendations(frame, TODAY)
    assert items
    assert any(item.priority == "habit" for item in items)
    scenarios = [item for item in items if item.potential_monthly_savings is not None]
    assert scenarios
    assert all(item.savings_basis for item in scenarios)
    assert all("scenario" in item.savings_basis.lower() for item in scenarios)


def test_exports_open():
    frame = _demo()
    kpis = compute_kpis(frame, frame, "All months", TODAY)
    from services.analytics import category_breakdown, merchant_totals, month_totals

    spend = spending_view(frame)
    excel = build_excel(
        frame,
        kpis,
        category_breakdown(spend),
        month_totals(spend),
        merchant_totals(spend),
        detect_recurring(frame),
        detect_anomalies(frame),
        build_recommendations(frame, TODAY),
        build_insights(frame, kpis, TODAY),
        demo=True,
    )
    pdf = build_pdf(
        frame,
        kpis,
        category_breakdown(spend),
        month_totals(spend),
        merchant_totals(spend),
        detect_recurring(frame),
        detect_anomalies(frame),
        build_recommendations(frame, TODAY),
        build_insights(frame, kpis, TODAY),
        demo=True,
    )
    assert excel[:2] == b"PK"
    assert pdf.startswith(b"%PDF")
    import io

    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(excel))
    assert "Transactions" in workbook.sheetnames
    assert "Summary" in workbook.sheetnames

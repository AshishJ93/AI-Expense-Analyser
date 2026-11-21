"""Categorization, duplicates, refunds, and learned merchant rules."""

import pandas as pd

from config.settings import BANNED_COPY
from services.categorizer import classify_description
from services.edits import apply_user_edits
from services.pipeline import prepare_transactions
from services.ai_insights import narrative_is_grounded


def _raw(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in ["debit", "credit", "amount", "drcr", "currency", "account"]:
        if column not in frame:
            frame[column] = ""
    frame["source_file"] = "fixture.csv"
    frame["row_order"] = range(len(frame))
    return frame


def test_known_merchants_and_uncertainty():
    swiggy = classify_description("UPI-SWIGGY-ORDER")
    assert swiggy["category"] == "Food & Dining"
    assert swiggy["subcategory"] == "Food Delivery"
    assert swiggy["confidence"] >= 0.85
    prime = classify_description("AMAZON PRIME")
    assert prime["category"] == "Subscriptions"
    assert prime["merchant"] == "Amazon Prime"
    instamart = classify_description("SWIGGY INSTAMART")
    assert instamart["category"] == "Groceries"
    unknown = classify_description("UPI-RAHUL SHARMA-RAHUL@OKSBI")
    assert unknown["category"] == "Other"
    assert unknown["confidence"] < 0.6


def test_user_rule_overrides_dictionary():
    learned = classify_description("UPI-SWIGGY-ORDER", {"swiggy": {"category": "Groceries", "subcategory": "Quick Commerce", "merchant": "Swiggy"}})
    assert learned["category"] == "Groceries"
    assert learned["method"] == "user_rule"
    assert learned["confidence"] >= 0.95


def test_spend_math_refunds_transfers_and_duplicates():
    prepared, _notes = prepare_transactions(
        [
            _raw(
                [
                    {"date": "01/06/2026", "description": "SWIGGY", "debit": "1,000.00"},
                    {"date": "01/07/2026", "description": "SWIGGY", "debit": "2000"},
                    {"date": "01/06/2026", "description": "SALARY ACME", "credit": "50000"},
                    {"date": "15/06/2026", "description": "AMAZON REFUND", "credit": "200"},
                    {"date": "02/06/2026", "description": "NEFT SELF TRANSFER TO SAVINGS", "debit": "5000"},
                    {"date": "03/06/2026", "description": "ZOMATO", "debit": "300"},
                    {"date": "03/06/2026", "description": "ZOMATO", "debit": "300"},
                ]
            )
        ]
    )
    spending = prepared[prepared["counts_as_spend"]]
    net = float(spending["debit"].sum() - spending["credit"].sum())
    assert net == 3100
    assert int(prepared["is_duplicate"].sum()) == 1
    assert not bool(prepared[prepared["description"].str.contains("SALARY")].iloc[0]["counts_as_spend"])
    assert not bool(prepared[prepared["description"].str.contains("SELF TRANSFER")].iloc[0]["counts_as_spend"])
    refund = prepared[prepared["transaction_type"] == "refund"].iloc[0]
    assert refund["category"] == "Shopping"
    assert bool(refund["counts_as_spend"])


def test_correction_propagates_to_the_same_merchant():
    prepared, _notes = prepare_transactions(
        [_raw([
            {"date": "01/06/2026", "description": "SWIGGY", "debit": "400"},
            {"date": "08/06/2026", "description": "UPI-SWIGGY-ORDER", "debit": "500"},
        ])]
    )
    edit = prepared.iloc[[0]].copy()
    edit["category"] = "Groceries"
    edit["subcategory"] = "Quick Commerce"
    updated, rules, changed = apply_user_edits(prepared, edit, {})
    assert changed == 1
    assert set(updated["category"]) == {"Groceries"}
    assert rules["swiggy"]["category"] == "Groceries"
    assert bool(updated["counts_as_spend"].all())


def test_restoring_a_duplicate_puts_it_back_in_the_total():
    prepared, _notes = prepare_transactions(
        [_raw([
            {"date": "03/06/2026", "description": "ZOMATO", "debit": "300"},
            {"date": "03/06/2026", "description": "ZOMATO", "debit": "300"},
        ])]
    )
    duplicate = prepared[prepared["is_duplicate"]].copy()
    duplicate["is_duplicate"] = False
    updated, _rules, changed = apply_user_edits(prepared, duplicate, {})
    assert changed == 1
    assert float((updated["debit"] - updated["credit"]).sum()) == 600
    assert int(updated["counts_as_spend"].sum()) == 2


def test_briefing_rejects_invented_numbers():
    source = '{"total": "₹12,400", "change": "12.5%"}'
    assert narrative_is_grounded("Spending was ₹12,400, a 12.5% change.", source)
    assert not narrative_is_grounded("You could save ₹9,999 easily.", source)


def test_recommendation_language_stays_respectful():
    from datetime import date

    from services.sample_data import load_sample_bytes
    from services.file_processor import process_bytes
    from services.recommendations import build_recommendations

    parsed = process_bytes("sample_transactions.csv", load_sample_bytes())
    prepared, _notes = prepare_transactions([parsed.frame])
    items = build_recommendations(prepared, today=date(2026, 11, 21))
    blob = " ".join(f"{item.title} {item.why} {item.action} {item.savings_basis or ''}" for item in items).lower()
    for phrase in BANNED_COPY:
        assert phrase not in blob

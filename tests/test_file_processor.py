"""Parsing, Indian number formats, masking, and PDF recovery."""

from datetime import date

import pandas as pd
from fpdf import FPDF

from services.file_processor import process_bytes
from services.pipeline import prepare_transactions
from services.statement_parser import parse_delimited
from services.transaction_cleaner import parse_number_and_marker
from utils.formatting import format_inr


def test_indian_number_formats():
    assert parse_number_and_marker("1,23,456.78")[0] == 123456.78
    assert parse_number_and_marker("(1,200.50)")[0] == -1200.50
    assert parse_number_and_marker("Rs. 2,500.00 Dr") == (2500.0, "dr")
    assert parse_number_and_marker("₹ 999")[0] == 999


def test_indian_grouping_display():
    assert format_inr(1234567) == "₹12,34,567"
    assert format_inr(100000) == "₹1,00,000"
    assert format_inr(1234567.8, decimals=2) == "₹12,34,567.80"
    assert format_inr(-2500) == "-₹2,500"


def test_preamble_and_withdrawal_columns():
    raw = (
        "HDFC Bank statement\n"
        "Account,XXXX4821\n"
        "Date,Narration,Withdrawal,Deposit\n"
        "01/06/2026,UPI-SWIGGY-ORDER,\"1,250.00\",\n"
        "02/06/2026,SALARY ACME,,\"1,85,000.00\"\n"
    ).encode("utf-8")
    parsed = parse_delimited(raw, "hdfc.csv")
    assert parsed.status == "parsed"
    prepared, _notes = prepare_transactions([parsed.frame], {}, convention="auto")
    swiggy = prepared[prepared["description"].str.contains("SWIGGY")].iloc[0]
    salary = prepared[prepared["description"].str.contains("SALARY")].iloc[0]
    assert swiggy["category"] == "Food & Dining"
    assert swiggy["subcategory"] == "Food Delivery"
    assert swiggy["counts_as_spend"]
    assert float(swiggy["debit"]) == 1250
    assert salary["transaction_type"] == "income"
    assert not salary["counts_as_spend"]


def test_card_number_is_masked_and_not_dropped():
    raw = "Date,Narration,Debit,Credit\n09/09/2026,POS 4160219812345678 AMAZON MARKETPLACE,2199,\n".encode()
    parsed = process_bytes("card.csv", raw)
    prepared, _notes = prepare_transactions([parsed.frame])
    description = prepared.iloc[0]["description"]
    assert "4160219812345678" not in description
    assert "5678" in description
    assert prepared.iloc[0]["merchant"] == "Amazon"
    assert len(prepared) == 1


def test_email_and_phone_are_masked():
    from utils.helpers import mask_sensitive

    masked = mask_sensitive("NEFT john.doe@bank.com 9876543210 rent")
    assert "john.doe@bank.com" not in masked
    assert "9876543210" not in masked
    assert "3210" in masked


def test_unreadable_row_is_kept():
    raw = "Date,Narration,Debit,Credit\nnot-a-date,MYSTERY SHOP,,\n01/06/2026,SWIGGY,100,\n".encode()
    parsed = process_bytes("messy.csv", raw)
    prepared, notes = prepare_transactions([parsed.frame])
    assert len(prepared) == 2
    mystery = prepared[prepared["description"].str.contains("MYSTERY")].iloc[0]
    assert not mystery["counts_as_spend"]
    assert mystery["needs_review"]
    assert any("look" in note.lower() or "date" in note.lower() or "review" in note.lower() for note in notes)


def test_pdf_text_statement_round_trip():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in [
        "01/08/2026 SWIGGY BANGALORE 450.00 Dr",
        "02/08/2026 SALARY ACME TECHNOLOGIES 185000.00 Cr",
        "03/08/2026 NETFLIX.COM 649.00 Dr",
    ]:
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    parsed = process_bytes("statement.pdf", bytes(pdf.output()))
    assert parsed.status == "parsed", parsed.message
    prepared, _notes = prepare_transactions([parsed.frame])
    assert set(prepared["merchant"]) >= {"Swiggy", "Netflix"}
    assert prepared.loc[prepared["merchant"] == "Netflix", "category"].iloc[0] == "Subscriptions"
    salary = prepared[prepared["transaction_type"] == "income"]
    assert len(salary) == 1
    assert not bool(salary.iloc[0]["counts_as_spend"])


def test_amount_column_card_style_is_detected():
    raw = (
        "Transaction Date,Description,Amount\n"
        "01/06/2026,SWIGGY,450.00\n"
        "02/06/2026,SALARY ACME,-185000.00\n"
        "03/06/2026,NETFLIX,649.00\n"
    ).encode()
    parsed = process_bytes("card.csv", raw)
    prepared, notes = prepare_transactions([parsed.frame], convention="auto")
    swiggy = prepared[prepared["merchant"] == "Swiggy"].iloc[0]
    assert float(swiggy["debit"]) == 450
    assert swiggy["counts_as_spend"]
    assert any("positive" in note.lower() or "card" in note.lower() or "spending" in note.lower() for note in notes)


def test_excel_round_trip_bytes():
    buffer = pd.DataFrame(
        {
            "Date": ["15/07/2026"],
            "Particulars": ["BESCOM ELECTRICITY"],
            "Withdrawal Amt": ["2,150.00"],
            "Deposit Amt": [""],
        }
    )
    import io

    payload = io.BytesIO()
    buffer.to_excel(payload, index=False)
    parsed = process_bytes("bill.xlsx", payload.getvalue())
    assert parsed.status == "parsed", parsed.message
    prepared, _notes = prepare_transactions([parsed.frame])
    row = prepared.iloc[0]
    assert row["category"] == "Utilities & Bills"
    assert row["subcategory"] == "Electricity"
    assert float(row["debit"]) == 2150
    assert row["date"].date() == date(2026, 7, 15)

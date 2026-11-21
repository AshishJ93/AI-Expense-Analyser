"""Fictional transactions for the demo dashboard.

The story is a salaried Bengaluru professional across June–November 2026.
November stops on the 20th so partial-month handling can be seen honestly.
Nothing here is a real person or a real account.
"""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "data" / "sample_transactions.csv"

BANK = "HDFC Bank ••4821"
CARD = "ICICI Card ••2290"


def _month_dates(year: int, month: int, limit_day: int | None = None) -> list[date]:
    last = calendar.monthrange(year, month)[1]
    if limit_day is not None:
        last = min(last, limit_day)
    return [date(year, month, day) for day in range(1, last + 1)]


def build_sample_frame() -> pd.DataFrame:
    rows: list[dict] = []

    def add(when: date, description: str, debit: float = 0, credit: float = 0, account: str = CARD) -> None:
        if when.month == 11 and when.day > 20:
            return
        rows.append(
            {
                "Date": when.isoformat(),
                "Narration": description,
                "Withdrawal": f"{debit:.2f}" if debit else "",
                "Deposit": f"{credit:.2f}" if credit else "",
                "Currency": "INR",
                "Account": account,
            }
        )

    subscriptions = [
        (5, "NETFLIX.COM", 649),
        (6, "SPOTIFY", 119),
        (6, "AMAZON PRIME", 299),
        (7, "HOTSTAR", 299),
        (8, "ICLOUD", 75),
        (8, "YOUTUBE PREMIUM", 129),
        (9, "CULTFIT MEMBERSHIP", 1499),
    ]

    for month in range(6, 12):
        index = month - 6
        add(date(2026, month, 1), "SALARY ACME TECHNOLOGIES", credit=185000, account=BANK)
        add(date(2026, month, 2), "INTEREST CREDIT", credit=312, account=BANK)
        add(date(2026, month, 3), "NEFT RENT TO LANDLORD", debit=32000, account=BANK)
        add(date(2026, month, 4), "GROWW SIP NIFTY INDEX", debit=15000, account=BANK)
        add(date(2026, month, 12), "BESCOM ELECTRICITY", debit=1800 + index * 80, account=BANK)
        add(date(2026, month, 14), "AIRTEL POSTPAID", debit=999, account=BANK)
        add(date(2026, month, 16), "ACT FIBERNET", debit=1179, account=BANK)
        add(date(2026, month, 10), "DMART SARJAPUR", debit=3600 + index * 120)
        for slot in range(4):
            add(date(2026, month, 4 + slot * 4), "BLINKIT", debit=480 + slot * 30)
        for slot, day in enumerate((3, 11, 18)):
            add(date(2026, month, day), "INDIAN OIL FUEL", debit=2300 + index * 40 + slot * 25, account=BANK)
        add(date(2026, month, 8), "ATM CASH WDL INDIRANAGAR", debit=4000, account=BANK)
        add(date(2026, month, 19), "ATM CASH WDL KORAMANGALA", debit=3000, account=BANK)
        for day in (5, 12, 18):
            add(date(2026, month, day), "CAFE COFFEE DAY", debit=220)
        for day in (4, 11, 15, 18):
            add(date(2026, month, day), "BMRCL METRO", debit=45)
        for offset, day in enumerate((2, 6, 9, 13)):
            add(date(2026, month, day), "UBER TRIP", debit=180 + offset * 20)
        growth = 1 + 0.1 * index
        limit = 20 if month == 11 else calendar.monthrange(2026, month)[1]
        weekday_orders = 0
        for day in range(1, limit + 1):
            current = date(2026, month, day)
            if current.weekday() >= 5:
                add(current, "UPI-SWIGGY-ORDER", debit=round(860 * growth))
            elif weekday_orders < 4 and current.weekday() in {1, 3}:
                add(current, "UPI-SWIGGY-ORDER", debit=round(320 * growth))
                weekday_orders += 1
        add(date(2026, month, 15), "ZOMATO", debit=round(540 * growth))
        zomato_day = 18 if month == 11 else 21
        if date(2026, month, zomato_day).weekday() >= 5:
            add(date(2026, month, zomato_day), "ZOMATO", debit=round(780 * growth))
        else:
            add(date(2026, month, zomato_day), "ZOMATO", debit=round(420 * growth))
        add(date(2026, month, 17), "MYNTRA", debit=1800 + index * 250)
        for day, description, amount in subscriptions:
            add(date(2026, month, day), description, debit=amount)

    # One exact double import, plus a one-off electronics purchase and a refund.
    add(date(2026, 10, 11), "UPI-SWIGGY-ORDER", debit=486)
    add(date(2026, 10, 11), "UPI-SWIGGY-ORDER", debit=486)
    add(date(2026, 10, 18), "CROMA ELECTRONICS INDIRANAGAR", debit=64990)
    add(date(2026, 10, 19), "FLIPKART", debit=6420)
    add(date(2026, 8, 14), "INDIGO 6E204 BLR DEL", debit=18420)
    add(date(2026, 7, 9), "STAR HEALTH INSURANCE", debit=12500, account=BANK)
    add(date(2026, 9, 18), "AMAZON REFUND ORDER 8831", credit=2499)
    add(date(2026, 6, 6), "NEFT SELF TRANSFER TO SAVINGS", debit=25000, account=BANK)
    add(date(2026, 6, 7), "UPI-RAHUL SHARMA-RAHUL@OKHDFC", debit=1500, account=BANK)
    add(date(2026, 8, 28), "SMS ALERT CHARGE", debit=18, account=BANK)
    add(date(2026, 9, 4), "APOLLO PHARMACY", debit=860)
    add(date(2026, 11, 3), "APOLLO PHARMACY", debit=640)
    add(date(2026, 8, 22), "MANIPAL HOSPITAL", debit=4200)
    add(date(2026, 9, 9), "UDEMY", debit=499)
    add(date(2026, 7, 25), "PVR INOX FORUM", debit=780)
    add(date(2026, 10, 26), "BOOKMYSHOW", debit=960)

    # A 16-digit test number that must be masked. It is not a real card.
    add(date(2026, 9, 2), "POS AMAZON MARKETPLACE", debit=2199)

    return pd.DataFrame(rows)


def write_sample_csv(path: Path | None = None) -> Path:
    destination = path or SAMPLE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    build_sample_frame().to_csv(destination, index=False)
    return destination


def load_sample_bytes() -> bytes:
    if not SAMPLE_PATH.exists():
        write_sample_csv()
    return SAMPLE_PATH.read_bytes()


if __name__ == "__main__":
    target = write_sample_csv()
    print(f"Wrote {target} ({len(build_sample_frame())} rows)")

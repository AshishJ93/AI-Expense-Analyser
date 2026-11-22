# HisaabPehle — Product Requirements

**Status:** Built and on GitHub (`main`). Not yet confirmed live on Streamlit Community Cloud.
**Owner:** Ashish Jain
**Date:** 22 November 2026
**Repo:** https://github.com/AshishJ93/AI-Expense-Analyser

## 1. Problem

A bank statement answers “what left the account.” It does not answer “what should I look at before I spend again.”

Most expense tools stop at charts: a total, a category pie, a list of merchants. The person still has to decide which change matters. Income, transfers, card-bill payments, and investments sit in the same file as purchases, so a naive total overstates spending. A month that is still open makes the average look worse than it is. An AI paragraph written from the raw file can invent a number that was never calculated.

HisaabPehle is a personal spending desk. It reads a statement, calculates a small set of figures with stated rules, and leads with one decision. The written briefing is optional and is discarded if it introduces a number the calculation did not supply.

## 2. Who it is for

**Primary user.** A person with one or two Indian bank or card statements (CSV, Excel, or a text PDF) who wants a private reading of their own spending. The sample ledger is a fictional Bengaluru salaried household, June to November 2026, in INR. The same screens work for USD, EUR, and GBP when the file does not name a currency.

**Secondary reader.** A product manager or business analyst who wants to see how an AI feature can sit on top of calculated cards without becoming the source of the numbers.

**Not for.** Tax filing, credit decisions, investment advice, bookkeeping for a business, or scanned image-only PDFs. The product says so on the report and in Settings.

## 3. Product intent

A visitor should understand the kind of reading they will get before they upload anything. Opening the app should land on upload, not on a tour and not on a second demo button.

The public page is the fictional reading itself:

- Rent is about a third of spending (₹1,92,000, 34.3% of ₹5,60,393).
- October rose 96.9% from September. Shopping moved from ₹2,250 to ₹74,210, and Croma is ₹64,990 of that.
- Weekend food delivery averaged ₹1,119 a day against ₹121 on a weekday.
- Seven subscriptions recur at about ₹3,069 a month.
- Purchases under ₹500 add up to ₹29,551 across 130 transactions.
- 317 rows, 296 count toward spending, 1 duplicate held out, 2 rows need a look.
- Accounts shown as HDFC Bank ••4821 and ICICI Card ••2290 are fictional.

**Open the app** goes to the upload screen. The visitor’s own file is read only after they choose it and confirm the preview.

## 4. Goals

1. Show one decision before the charts.
2. Define spending so transfers, income, and investments do not inflate it.
3. Keep card numbers, emails, and phone numbers off the screen, out of exports, and out of the briefing.
4. Let the dashboard work with no model key. The briefing is an extra paragraph, not the product.
5. Make every AI sentence checkable against the cards already on screen.

## 5. Non-goals

- A formal PCI DSS certification. Masking and session-only storage reduce exposure. They are not an audit.
- Storing statements in a database, or keeping uploads after the session ends.
- Letting a visitor paste an API key. The owner’s xAI key stays in environment or Streamlit secrets and is never shown.
- Multi-user accounts, budgets with alerts, bank aggregation, or open-banking connections.
- Reading scanned or password-protected PDFs. Those paths ask for a CSV or Excel export from the bank.
- A second “explore the demo” door inside the app. The fictional reading lives on the website.

## 6. Experience

### 6.1 Public page

Header is the wordmark and **Open the app**. There is no Tour, All features, or Browse the features.

The page walks the fictional ledger: total, month bars (Jun–Nov), month-on-month change, average of complete months, largest category, transaction counts, the October shopping decision, four lenses (Daily, Patterns, Recurring, Review), categories, merchants, and a briefing written from those figures. The page states that if a sentence and a card disagree, the card wins.

Month bars and lenses switch in place. **Open the app** navigates to upload.

### 6.2 Upload

Title: **Upload a statement.**

- Accepts CSV, XLSX, XLS, and text PDF. Several files at once.
- **Read statements** stays disabled until a file is chosen.
- Every extracted row is previewed before analysis. Failed files keep their reason.
- Ambiguous headers can be mapped. A single amount column can be treated as “detect,” “positive is a purchase,” or “negative is a purchase.”
- Card numbers, emails, and phone numbers are masked in the preview.
- Continuing runs categorization and opens Overview.
- Replacing a statement that is already loaded stays on upload and offers **Back to dashboard**.

### 6.3 After a statement is loaded

Sidebar sections:

| Screen | Job |
| --- | --- |
| Overview | Period total, the decision, optional briefing, monthly trend, category ranking, the first things that stand out |
| Spending Intelligence | Daily, Patterns, Recurring, Review. One question per lens |
| Think before you spend | High priority, worth reviewing, and habits that are working. A note is a place to look, not a verdict that a purchase was wrong |
| Categories | Where the money went, including change over months |
| Merchants | Who received it |
| Transactions | Search, filter, correct a category, restore a duplicate, export the current view |
| Reports | Excel workbook (every row) and PDF (the narrative), for the period in the header |
| Settings | Small-purchase threshold, fallback currency, briefing on or off, delete merchant rules, clear the session |

The header period control changes the view. An open month is labeled as open.

## 7. Functional requirements

### 7.1 Parsing and cleaning

- Detect the header row in a CSV that has a preamble.
- Parse ISO dates as year-month-day before day-first parsing.
- Mask 12–19 digit sequences to the last 4, emails, and Indian mobile numbers before categorization and before anything is shown.
- Hold likely duplicates out of spending and say so.
- Mark low-confidence categories for review. Unrecognized UPI and NEFT stay as transfers until the person recategorizes them.
- Cash withdrawals count as spending, with a note that the statement cannot say what the cash bought.

### 7.2 Spending definition

**Spending** = withdrawals minus refunds, on rows that count as spend.

**Left out of spending:** income, transfers (self-transfers and card-bill payments), investments, unclassified credits, duplicates.

**Month still in progress:** if the latest date is the current month and the day is before the 28th, that month is excluded from the average and from the month-to-month comparison. The comparison uses the last two complete months and says which months those are.

### 7.3 Categories and memory

- Merchants are categorized from rules.
- A correction in Transactions is remembered as merchant, category, and subcategory only, in `.hisaabpehle/merchant_rules.json` on the machine running the app.
- Amounts and narrations are not written there.
- Settings can delete those rules. On Streamlit Community Cloud the file lasts only as long as the container does.

### 7.4 Recommendations

Think before you spend groups notes into:

- **High priority:** larger shifts in discretionary spending.
- **Worth reviewing:** real movements, including essentials that may simply cost more.
- **Good habit:** patterns that do not need a change.

If the selected period is too short for a fair comparison, the notes use every loaded month and say so. If nothing stands out, the screen says the months may simply look alike.

### 7.5 Briefing

- People using the app never enter a key.
- The key is read from the environment or Streamlit secrets (`XAI_API_KEY`, provider `xai`, base `https://api.x.ai/v1`, model `grok-4-1-fast-non-reasoning`).
- With no key, every calculated screen still works.
- With a key, and with consent on (the default), the app asks for one paragraph.
- The request contains the insight cards already calculated: totals, category names, merchant names, recommendation text. It does not contain account numbers or the full statement.
- A paragraph that contains a number absent from that source is discarded.
- Settings can turn the briefing off or refresh it.

### 7.6 Reports and privacy copy

- Excel and PDF are built in the session from the loaded rows and the selected period.
- Demo exports stay labeled fictional.
- The PDF states that the report is a personal review aid, not tax, credit, or investment advice.
- **Clear loaded statements** drops the session data.

## 8. Privacy requirements

| Data | Rule |
| --- | --- |
| Uploaded file | Not saved. Lives in session memory |
| Transaction rows | Not written to a database |
| Card and long account numbers | Masked to last 4 before display, export, and briefing |
| Email and phone | Masked before display |
| Briefing payload | Aggregated cards only |
| Merchant rules | Merchant name and category only, local file, deletable |
| API key | Owner-side secret. Never in the UI, never in git |

This is a privacy design. It is not a claim of PCI certification.

## 9. Success, for this version

A first-time visitor can:

1. Read the fictional page and name the decision (October shopping) without uploading a file.
2. Open the app and see only upload.
3. Upload a CSV, preview masked rows, and reach Overview.
4. See a total that excludes a known transfer or investment.
5. Download a report that does not show a full card number.
6. Use the app with the briefing switched off and still get the decision, charts, and exports.

Known sample checks, using the fictional ledger and a “today” of 21 November 2026:

- Spending ₹5,60,393.
- Rent ₹1,92,000 across 6 payments.
- October versus September +96.9%.
- Average of 5 complete months ₹96,978.
- November left out of that average.

## 10. Constraints

- Single Streamlit app, Python 3.11+, no separate frontend service.
- `screens/` must not be named `pages/`. Streamlit would treat that folder as multipage navigation.
- Public hosting target is Streamlit Community Cloud, main file `app.py`, secrets set in the cloud UI.
- The standalone `site/index.html` still points **Open the app** at `localhost` until that link is changed to the deployed URL plus `?enter=1`. Inside the running app, the button already stays on the current host.

## 11. Open questions

1. Deploy URL on Streamlit Community Cloud, then update the standalone site link.
2. Whether merchant rules should exist at all on a public Cloud app, given the container is ephemeral and shared only in the sense of one running process.
3. Whether a later version should add a budget or a “next month” target. Out of scope until the reading above is the habit.

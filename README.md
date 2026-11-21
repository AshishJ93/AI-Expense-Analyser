# SpendWise AI

SpendWise is a personal spending desk. You upload a bank or card statement, and it shows where the money went, what is repeating, and which changes are worth a second look.

The totals, categories, and recommendations are calculated in the app. An AI provider is optional. If you never add a key, the dashboard still works.

## What you can do

- Upload CSV, Excel (`.xlsx` and `.xls`), and text-based PDF statements, including several files at once.
- Map columns when a file's headers are ambiguous.
- Preview every extracted row before anything is analyzed. Rows that cannot be read are kept and explained.
- Categorize merchants, then correct a category. A correction is remembered for that merchant.
- Read monthly, category, and merchant views.
- See recurring payments, unusual charges, and a "Think before you spend" list.
- Export the current view, plus an Excel workbook and a PDF report.
- Open a fictional demo if you do not want to upload your own statement.

## Install

Python 3.11 or newer.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS or Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

From this folder:

```bash
streamlit run app.py
```

Open the local URL Streamlit prints. Choose **Explore the demo** or upload a statement.

## xAI briefing

People using the app never enter a key. Copy `.env.example` to `.env` and set it there, or put the same names in `.streamlit/secrets.toml` when you deploy:

```bash
SPENDWISE_LLM_PROVIDER=xai
XAI_API_KEY=
SPENDWISE_LLM_BASE_URL=https://api.x.ai/v1
SPENDWISE_LLM_MODEL=grok-4-1-fast-non-reasoning
```

`SPENDWISE_LLM_API_KEY` is accepted as well. Do not commit `.env` or `secrets.toml`.

When a key is present, SpendWise asks Grok for one paragraph after a statement is analyzed. It sends the insight cards already on screen (totals, category names, and merchant names). It does not send account numbers or the full statement. A briefing that introduces a number which is not in those cards is discarded. Turn this off under Settings.

## How the numbers are defined

- **Spending** is withdrawals minus refunds.
- **Excluded from spending:** income, transfers (including self-transfers and card-bill payments), investments, unclassified credits, and rows marked as duplicates.
- **Cash withdrawals** stay in spending, with a note that the statement cannot say what the cash bought.
- **A month still in progress** is left out of the average and out of the month-to-month comparison. The comparison uses the last two finished months, and says so.
- **Low confidence** means the category is a suggestion. Unrecognized UPI and NEFT payments are held as transfers so they do not inflate spending until you recategorize them.

## Privacy

Transaction rows live in the session. They are not written to a database.

Merchant corrections are saved only as merchant name, category, and subcategory in `.spendwise/merchant_rules.json` on the machine running the app. Amounts and narrations are not saved there. Delete them from Settings.

Card numbers, long account numbers, email addresses, and phone numbers are masked before a row is shown, exported, or sent into a briefing. The original file is not saved.

## PDF statements

PDF support reads tables and, failing that, lines that look like `date description amount`. Scanned statements and unusual layouts often fail. When they do, the screen says why and asks for a CSV or Excel export from the bank, which is the more accurate path. Password-protected files need to be exported unlocked.

## Deploy for the public

Opening the app shows the feature tour first. **Open the app** goes to the screen where a visitor explores the fictional demo or uploads a statement. `site/index.html` is that same tour for a separate web page. On that file, change `http://localhost:8523/?enter=1` to your Streamlit address plus `?enter=1` before you publish it. Inside the running app, the button already stays on the app.

1. Push this folder to GitHub. Do not commit `.env` or `.streamlit/secrets.toml`. Both are gitignored. The xAI key stays in Streamlit secrets, not in the repository.
2. Create an app on [Streamlit Community Cloud](https://streamlit.io/cloud) with main file `app.py`.
3. In the app settings, add:

```toml
XAI_API_KEY = "your-key"
SPENDWISE_LLM_PROVIDER = "xai"
SPENDWISE_LLM_BASE_URL = "https://api.x.ai/v1"
SPENDWISE_LLM_MODEL = "grok-4-1-fast-non-reasoning"
```

4. There is no database. Uploaded statements live only in the browser session. Card numbers, long account numbers, email addresses, and phone numbers are masked before they are shown, exported, or used in a briefing. They are not written to disk.

`site/index.html` is a separate public page. Host it with GitHub Pages if you want a site in front of the app. Change the **Open the app** link in that file to your Streamlit URL, for example `https://your-app.streamlit.app`.

## Tests

```bash
pytest
```

## Project map

| Path | Role |
| --- | --- |
| `app.py` | Navigation and session |
| `screens/` | Each screen |
| `components/` | Header, charts, cards |
| `services/` | Parsing, cleaning, categories, math, insights, exports |
| `config/settings.py` | Categories, merchant rules, colors |
| `data/sample_transactions.csv` | Fictional demo ledger |
| `styles/custom.css` | Visual system |

## Limits

Categories are rules plus your corrections, not a guarantee. A large purchase is not treated as a mistake. Savings figures are labeled scenarios. This is a personal review tool, not tax, credit, or investment advice.

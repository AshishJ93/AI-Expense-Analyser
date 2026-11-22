"""Categories, merchant rules, thresholds, and design tokens.

Classification rules are ordered. The first match wins, so more specific
patterns (Swiggy Instamart, Amazon Prime) sit above broader ones (Swiggy, Amazon).
"""

from __future__ import annotations

import re

APP_NAME = "HisaabPehle"
APP_TAGLINE = "A personal reading of where your money goes."

# Lifestyle spending. Income, transfers, and investments are tracked separately
# so a salary credit or a SIP is not treated as a purchase.
SPENDING_CATEGORIES: list[str] = [
    "Food & Dining",
    "Groceries",
    "Shopping",
    "Travel",
    "Fuel & Transportation",
    "Entertainment",
    "Healthcare",
    "Utilities & Bills",
    "Rent & Housing",
    "Education",
    "Subscriptions",
    "Insurance",
    "Cash Withdrawals",
    "Bank Charges & Fees",
    "Other",
]

NON_SPEND_CATEGORIES = {"Transfers", "Investments", "Income"}

CATEGORIES: list[str] = SPENDING_CATEGORIES + ["Investments", "Transfers", "Income"]

SUBCATEGORIES: dict[str, list[str]] = {
    "Food & Dining": ["Restaurants", "Cafes", "Food Delivery", "General"],
    "Groceries": ["Supermarket", "Quick Commerce", "General"],
    "Shopping": ["Clothing", "Electronics", "Personal Care", "Online Shopping", "General"],
    "Travel": ["Flights", "Hotels", "Rail", "Local Transport", "General"],
    "Fuel & Transportation": ["Fuel", "Transit", "General"],
    "Entertainment": ["Movies & Events", "General"],
    "Healthcare": ["Pharmacy", "Hospital", "General"],
    "Utilities & Bills": ["Electricity", "Mobile", "Internet", "General"],
    "Rent & Housing": ["Rent", "General"],
    "Education": ["Courses", "Fees", "General"],
    "Subscriptions": ["Streaming", "Software", "Fitness", "General"],
    "Insurance": ["Health", "Life", "General"],
    "Investments": ["SIP & Mutual Funds", "Brokerage", "General"],
    "Cash Withdrawals": ["ATM", "General"],
    "Bank Charges & Fees": ["Account Fees", "Card Fees", "General"],
    "Transfers": ["Self Transfer", "Card Payment", "Person", "General"],
    "Income": ["Salary", "Interest", "General"],
    "Other": ["General"],
}

# Discretionary groups can support a savings scenario. Essentials are described,
# never framed as something the user should cut.
DISCRETIONARY = {
    "Food & Dining",
    "Shopping",
    "Entertainment",
    "Travel",
    "Subscriptions",
}
ESSENTIAL = {
    "Groceries",
    "Fuel & Transportation",
    "Healthcare",
    "Utilities & Bills",
    "Rent & Housing",
    "Education",
    "Insurance",
}

CATEGORY_COLORS: dict[str, str] = {
    "Food & Dining": "#FF6B4A",
    "Groceries": "#34C759",
    "Shopping": "#AF52DE",
    "Travel": "#007AFF",
    "Fuel & Transportation": "#FF9F0A",
    "Entertainment": "#FF2D55",
    "Healthcare": "#30B0C7",
    "Utilities & Bills": "#5856D6",
    "Rent & Housing": "#1D1D1F",
    "Education": "#5AC8FA",
    "Subscriptions": "#BF5AF2",
    "Insurance": "#64D2FF",
    "Investments": "#248A3D",
    "Cash Withdrawals": "#8E8E93",
    "Bank Charges & Fees": "#C7C7CC",
    "Transfers": "#AEAEB2",
    "Income": "#32ADE6",
    "Other": "#D1D1D6",
}

INK = "#1C1B19"
MUTED = "#6F6A62"
ACCENT = "#3F5E4E"
GRID = "rgba(28, 27, 25, 0.08)"
POSITIVE = "#248A3D"
WARNING = "#B86E00"
NEGATIVE = "#C41E3A"

DEFAULT_SMALL_PURCHASE = 500.0
DEFAULT_LARGE_TRANSACTION = 10000.0
DEFAULT_CURRENCY = "INR"

# (pattern, category, subcategory, canonical merchant or None)
MERCHANT_RULES: list[tuple[str, str, str, str | None]] = [
    (r"swiggy\s*instamart", "Groceries", "Quick Commerce", "Swiggy Instamart"),
    (r"\bswiggy\b", "Food & Dining", "Food Delivery", "Swiggy"),
    (r"\bzomato\b", "Food & Dining", "Food Delivery", "Zomato"),
    (r"uber\s*eats", "Food & Dining", "Food Delivery", "Uber Eats"),
    (r"\beatclub\b", "Food & Dining", "Food Delivery", "EatClub"),
    (r"starbucks|cafe\s*coffee\s*day|\bccd\b|third\s*wave|blue\s*tokai|chai\s*point", "Food & Dining", "Cafes", None),
    (r"mcdonald|burger\s*king|\bkfc\b|domino|pizza\s*hut|subway|haldiram|barbeque\s*nation", "Food & Dining", "Restaurants", None),
    (r"blinkit|zepto|big\s*basket|jiomart|jio\s*mart|\bdunzo\b", "Groceries", "Quick Commerce", None),
    (r"d[\s-]?mart|reliance\s*fresh|nature.?s\s*basket|star\s*bazaar|more\s+(mega|super|retail)|spencer", "Groceries", "Supermarket", None),
    (r"amazon\s*prime|amzn\s*prime|prime\s*video", "Subscriptions", "Streaming", "Amazon Prime"),
    (r"\bamazon\b|\bamzn\b", "Shopping", "Online Shopping", "Amazon"),
    (r"\bflipkart\b", "Shopping", "Online Shopping", "Flipkart"),
    (r"\bmyntra\b|\bajio\b|westside|max\s*fashion|\bzara\b|h\s*&\s*m|h and m", "Shopping", "Clothing", None),
    (r"\bnykaa\b", "Shopping", "Personal Care", "Nykaa"),
    (r"\bcroma\b|reliance\s*digital|vijay\s*sales", "Shopping", "Electronics", None),
    (r"\bdecathlon\b|\bikea\b", "Shopping", "General", None),
    (r"\bmeesho\b", "Shopping", "Online Shopping", "Meesho"),
    (r"indigo|spice\s*jet|air\s*india|\bakasa\b|vistara|go\s*first", "Travel", "Flights", None),
    (r"\boyo\b|airbnb|treebo|taj\s*hotel|oyo\s*rooms", "Travel", "Hotels", None),
    (r"makemytrip|goibibo|\byatra\b|agoda|booking\.com", "Travel", "Hotels", None),
    (r"\birctc\b", "Travel", "Rail", "IRCTC"),
    (r"uber\s*eats", "Food & Dining", "Food Delivery", "Uber Eats"),
    (r"\buber\b", "Travel", "Local Transport", "Uber"),
    (r"\bola\b|\brapido\b|namma\s*yatri|bmrcl|namma\s*metro|metro\s*rail|\bredbus\b|abhibus", "Travel", "Local Transport", None),
    (r"indian\s*oil|\bioc[l]?\b|\bbpcl\b|\bhpcl\b|hindustan\s*petroleum|bharat\s*petroleum|nayara|shell\s*(petrol|india)|petrol|diesel|\bfuel\b", "Fuel & Transportation", "Fuel", None),
    (r"bookmyshow|\bpvr\b|\binox\b", "Entertainment", "Movies & Events", None),
    (r"apollo|medplus|pharmeasy|netmeds|\b1mg\b|practo|fortis|manipal|pharmacy|hospital|diagnostic", "Healthcare", "General", None),
    (r"bescom|msedcl|cescom|hescom|tangedco|tata\s*power|adani\s*electricity|electricity|\bbijli\b", "Utilities & Bills", "Electricity", None),
    (r"airtel|\bjio\b|vodafone|myvi|\bbsnl\b", "Utilities & Bills", "Mobile", None),
    (r"act\s*fiber|hathway|excitel|tata\s*play|dishtv|spectranet|fibernet", "Utilities & Bills", "Internet", None),
    (r"\brent\b|lease\s+payment|no\s*broker", "Rent & Housing", "Rent", None),
    (r"udemy|coursera|unacademy|byju|school\s*fee|college\s*fee", "Education", "Courses", None),
    (r"netflix", "Subscriptions", "Streaming", "Netflix"),
    (r"spotify", "Subscriptions", "Streaming", "Spotify"),
    (r"hotstar|disney\s*\+", "Subscriptions", "Streaming", "Disney+ Hotstar"),
    (r"youtube\s*premium", "Subscriptions", "Streaming", "YouTube Premium"),
    (r"icloud|apple\.com/bill", "Subscriptions", "Software", "Apple"),
    (r"google\s*(one|storage)", "Subscriptions", "Software", "Google One"),
    (r"linkedin\s*premium|\bnotion\b|chatgpt|openai|\bcursor\b|microsoft\s*365|\badobe\b", "Subscriptions", "Software", None),
    (r"cult\.?fit|cultfit", "Subscriptions", "Fitness", "Cult.fit"),
    (r"\blic\b|star\s*health|hdfc\s*ergo|niva\s*bupa|icici\s*lombard|tata\s*aig|policybazaar", "Insurance", "General", None),
    (r"zerodha|\bgroww\b|kuvera|\bnps\b|mutual\s*fund|\bsip\b|ppfas", "Investments", "SIP & Mutual Funds", None),
    (r"\batm\b|cash\s+withdraw|cash\s+wdl|nfs\s*cash|\bcwdr\b", "Cash Withdrawals", "ATM", None),
    (r"bank\s+charge|sms\s+(alert\s+)?charge|annual\s+fee|late\s+payment|finance\s+charge|min(?:imum)?\s+balance|account\s+maintenance|card\s+fee", "Bank Charges & Fees", "Account Fees", None),
    (r"self\s+transfer|own\s+account|credit\s+card\s+payment|\bcc\s+payment\b|card\s+bill|balance\s+transfer", "Transfers", "Self Transfer", None),
]

GENERIC_RULES: list[tuple[str, str, str]] = [
    (r"\brestaurant\b|\bdining\b|\beatery\b|\bcafe\b|\bcoffee\b", "Food & Dining", "Restaurants"),
    (r"\bgrocery\b|\bsupermarket\b|\bprovision\b|\bvegetables\b", "Groceries", "General"),
    (r"\bflight\b|\bhotel\b|\btravel\b", "Travel", "General"),
    (r"\bpharmacy\b|\bmedical\b|\bdoctor\b|\bclinic\b", "Healthcare", "General"),
    (r"\binsurance\b|\bpremium\b", "Insurance", "General"),
    (r"\btuition\b|\buniversity\b", "Education", "Fees"),
]

INCOME_PATTERNS = [
    r"\bsalary\b",
    r"\bpayroll\b",
    r"\binterest\s+credit\b",
    r"\bint\.?\s*cr\b",
    r"\bdividend\b",
]
REFUND_PATTERNS = [
    r"\brefund\b",
    r"\breversal\b",
    r"\bcharge\s*back\b",
    r"\bcashback\b",
]
FEE_PATTERNS = [
    r"\bbank\s+charge",
    r"\bsms\s+(alert\s+)?charge",
    r"\bannual\s+fee\b",
    r"\blate\s+payment\b",
    r"\bfinance\s+charge\b",
    r"\baccount\s+maintenance\b",
]
CASH_PATTERNS = [
    r"\batm\b",
    r"\bcash\s+withdraw",
    r"\bcash\s+wdl\b",
    r"\bnfs\s*cash\b",
    r"\bcwdr\b",
]
TRANSFER_PATTERNS = [
    r"\bself\s+transfer\b",
    r"\bown\s+account\b",
    r"\bcredit\s+card\s+payment\b",
    r"\bcc\s+payment\b",
    r"\bcard\s+bill\b",
    r"\bbalance\s+transfer\b",
    r"\bto\s+my\s+account\b",
]
CHANNEL_TRANSFER = re.compile(r"\b(neft|imps|rtgs)\b", re.I)
UPI_PATTERN = re.compile(r"\bupi\b", re.I)

VIDEO_MERCHANTS = {"netflix", "disney+ hotstar", "amazon prime", "youtube premium"}

HEADER_ALIASES: dict[str, list[str]] = {
    "date": [
        "date",
        "txn date",
        "transaction date",
        "trans date",
        "value date",
        "posted date",
        "posting date",
        "txn dt",
        "tran date",
    ],
    "description": [
        "description",
        "narration",
        "particulars",
        "details",
        "transaction details",
        "remarks",
        "merchant",
        "transaction remarks",
        "narrative",
    ],
    "debit": [
        "debit",
        "withdrawal",
        "withdrawals",
        "money out",
        "paid out",
        "dr amount",
        "debit amount",
        "withdrawal amt",
        "withdrawal amount",
    ],
    "credit": [
        "credit",
        "deposit",
        "deposits",
        "money in",
        "paid in",
        "cr amount",
        "credit amount",
        "deposit amt",
        "deposit amount",
    ],
    "amount": [
        "amount",
        "amt",
        "transaction amount",
        "txn amount",
        "tran amt",
    ],
    "drcr": [
        "dr/cr",
        "cr/dr",
        "dr cr",
        "type",
        "transaction type",
        "credit/debit",
        "debit/credit",
    ],
    "currency": ["currency", "ccy", "curr"],
    "account": ["account", "account number", "card", "card number", "account no"],
}

SKIP_HEADER_TOKENS = ("balance", "closing", "opening", "available", "limit", "reward")

PERIODS = [
    "All months",
    "Latest month",
    "Previous month",
    "Last 3 months",
    "Last 6 months",
]

NAV_ITEMS = [
    ("Overview", "Overview"),
    ("Intelligence", "Spending Intelligence"),
    ("Review", "Think Before You Spend"),
    ("Categories", "Categories"),
    ("Merchants", "Merchants"),
    ("Transactions", "Transactions"),
    ("Reports", "Reports"),
    ("Settings", "Settings"),
]


def compile_rules(rules: list[tuple]) -> list[tuple]:
    compiled = []
    for rule in rules:
        pattern = re.compile(rule[0], re.IGNORECASE)
        compiled.append((pattern, *rule[1:]))
    return compiled


COMPILED_MERCHANT_RULES = compile_rules(MERCHANT_RULES)
COMPILED_GENERIC_RULES = [
    (re.compile(pattern, re.IGNORECASE), category, subcategory)
    for pattern, category, subcategory in GENERIC_RULES
]
COMPILED_INCOME = [re.compile(p, re.I) for p in INCOME_PATTERNS]
COMPILED_REFUND = [re.compile(p, re.I) for p in REFUND_PATTERNS]
COMPILED_FEE = [re.compile(p, re.I) for p in FEE_PATTERNS]
COMPILED_CASH = [re.compile(p, re.I) for p in CASH_PATTERNS]
COMPILED_TRANSFER = [re.compile(p, re.I) for p in TRANSFER_PATTERNS]

BANNED_COPY = (
    "guilt",
    "guilty",
    "shame",
    "waste",
    "wasted",
    "wasting",
    "bad habit",
    "can't afford",
    "cannot afford",
    "you should stop",
    "irresponsible",
)

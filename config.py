import os
from dotenv import load_dotenv

load_dotenv()

# Bot credentials
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

# Pricing
BASE_PRICE: int = 490          # ETB for 1 email
PRICE_PER_EXTRA_EMAIL: int = 50  # ETB added per additional email
MAX_EMAILS: int = 10           # maximum emails a user can choose

# Payment details shown to users
CBE_ACCOUNT: str = os.getenv("CBE_ACCOUNT", "1000XXXXXXXXX")
TELEBIRR_ACCOUNT: str = os.getenv("TELEBIRR_ACCOUNT", "09XXXXXXXX")
ACCOUNT_NAME: str = os.getenv("ACCOUNT_NAME", "Your Name")

# SQLite database path
DB_PATH: str = os.getenv("DB_PATH", "subscriptions.db")


def calculate_price(num_emails: int) -> int:
    """Return the total price in ETB for the requested number of emails."""
    if num_emails < 1:
        return BASE_PRICE
    return BASE_PRICE + (num_emails - 1) * PRICE_PER_EXTRA_EMAIL

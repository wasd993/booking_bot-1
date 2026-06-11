import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN or "xxxxxxxxx" in BOT_TOKEN:
    raise ValueError("Заполни BOT_TOKEN в файле .env")

_raw = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _raw.split(",")
    if x.strip().isdigit()
]
if not ADMIN_IDS:
    raise ValueError("Заполни ADMIN_IDS в файле .env — узнай ID у @userinfobot")

STARS_PRICE: int = int(os.getenv("STARS_PRICE", "10").strip() or "10")
DB_PATH: str     = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"
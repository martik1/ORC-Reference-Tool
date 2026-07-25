from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_MAX_AGE_DAYS = 7

DEFAULT_COUNTRIES: list[str] = []

API_BASE = "https://data.orc.org/public/WPub.dll"

import pathlib

BASE_DIR = pathlib.Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "museums.db"

# How often to re-scrape (hours)
SCRAPE_INTERVAL_HOURS = 24

# HTTP headers for static scrapers
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MUSEUM_LABELS = {
    "tate": "Tate",
    "british_museum": "British Museum",
    "vam": "V&A",
    "design_museum": "Design Museum",
    "kew": "Kew Gardens",
}

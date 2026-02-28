import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

import dateparser

logger = logging.getLogger(__name__)


@dataclass
class RawExhibition:
    title: str
    url: str
    raw_dates: Optional[str] = None
    date_start: Optional[str] = None  # ISO 8601 date string
    date_end: Optional[str] = None    # ISO 8601 date string


def _parse_single_date(text: str) -> Optional[date]:
    """Parse a single date string using dateparser with UK settings."""
    result = dateparser.parse(
        text.strip(),
        settings={
            "DATE_ORDER": "DMY",
            "PREFER_DAY_OF_MONTH": "first",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )
    return result.date() if result else None


def parse_uk_date_range(raw: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a UK-format date range string into (date_start, date_end) ISO strings.

    Handles patterns like:
      - "14 Mar – 26 Oct 2025"
      - "Until 26 October 2025"
      - "From 14 March 2025"
      - "Permanent"
      - "14 March – 26 October"  (year inferred from end)
    """
    if not raw:
        return None, None

    text = raw.strip()

    # Permanent exhibitions
    if re.search(r'\bpermanent\b', text, re.IGNORECASE):
        return None, None

    # Strip common non-date prefixes (e.g. "Free display: Until 5 Jan 2026")
    text = re.sub(r'^[^:]+:\s+', '', text, count=1)

    # "Until X" / "Closes [Day,] X" — only end date
    m = re.match(r'^(?:until|closes?(?:\s+\w+,)?)\s+(.+)$', text, re.IGNORECASE)
    if m:
        end = _parse_single_date(m.group(1))
        return None, end.isoformat() if end else None

    # "From X" / "Opens [Day,] X" — only start date
    m = re.match(r'^(?:from|opens?(?:\s+\w+,)?)\s+(.+)$', text, re.IGNORECASE)
    if m:
        start = _parse_single_date(m.group(1))
        return start.isoformat() if start else None, None

    # Date range with en-dash, em-dash, or " - "
    # Matches: "14 Mar – 26 Oct 2025" or "14 March - 26 October 2025"
    range_pattern = re.split(r'\s*[–—-]\s*', text, maxsplit=1)
    if len(range_pattern) == 2:
        start_str, end_str = range_pattern

        # Parse end first to extract year
        end = _parse_single_date(end_str)

        # If start has no year, try appending end year
        start = _parse_single_date(start_str)
        if start is None and end is not None:
            year = end.year
            start = _parse_single_date(f"{start_str} {year}")

        return (
            start.isoformat() if start else None,
            end.isoformat() if end else None,
        )

    # Single date — treat as start only
    single = _parse_single_date(text)
    if single:
        return single.isoformat(), None

    return None, None


class BaseScraper(ABC):
    museum_slug: str
    base_url: str

    @abstractmethod
    async def fetch(self) -> list[RawExhibition]:
        """Scrape the museum website and return raw exhibition data."""
        ...

    def compute_status(
        self, start: Optional[str], end: Optional[str]
    ) -> str:
        today = date.today()
        try:
            start_date = date.fromisoformat(start) if start else None
            end_date = date.fromisoformat(end) if end else None
        except ValueError:
            return "unknown"

        if end_date and end_date < today:
            return "past"
        if start_date and start_date > today:
            return "upcoming"
        return "current"

    async def run(self, conn) -> int:
        """
        Fetch exhibitions, compute status, and upsert to DB.
        Returns count of exhibitions stored. Never raises.
        """
        from app.database import upsert_exhibition
        from datetime import timezone

        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0

        try:
            exhibitions = await self.fetch()
        except Exception as exc:
            logger.error("[%s] fetch() failed: %s", self.museum_slug, exc, exc_info=True)
            return 0

        for ex in exhibitions:
            try:
                status = self.compute_status(ex.date_start, ex.date_end)

                # Skip past exhibitions
                if status == "past":
                    continue

                row = {
                    "museum": self.museum_slug,
                    "title": ex.title,
                    "url": ex.url,
                    "date_start": ex.date_start,
                    "date_end": ex.date_end,
                    "status": status,
                    "raw_dates": ex.raw_dates,
                    "scraped_at": scraped_at,
                }
                upsert_exhibition(conn, row)
                count += 1
            except Exception as exc:
                logger.error(
                    "[%s] Failed to store '%s': %s",
                    self.museum_slug, ex.title, exc, exc_info=True,
                )

        logger.info("[%s] Stored %d exhibitions", self.museum_slug, count)
        return count

import logging

import httpx
from bs4 import BeautifulSoup

from app.config import HTTP_HEADERS
from app.scrapers.base import BaseScraper, RawExhibition, parse_uk_date_range

logger = logging.getLogger(__name__)

WHATS_ON_URL = "https://www.tate.org.uk/whats-on"


class TateScraper(BaseScraper):
    museum_slug = "tate"
    base_url = "https://www.tate.org.uk"

    async def fetch(self) -> list[RawExhibition]:
        async with httpx.AsyncClient(headers=HTTP_HEADERS, follow_redirects=True, timeout=30) as client:
            resp = await client.get(WHATS_ON_URL)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        seen_urls = set()

        # Card structure: the <a> IS the card
        #   <a href="/whats-on/venue/slug">
        #     <h2 class="card__title">
        #       <span class="card__title--maintitle">Title</span>
        #     </h2>
        #     <div class="event-info event-info__date">
        #       <span>Until 12 Apr 2026</span>
        #     </div>
        #   </a>
        cards = soup.select("a[href^='/whats-on/']")

        for card in cards:
            href = card.get("href", "")
            # Skip the listing page itself and non-detail slugs
            parts = [p for p in href.split("/") if p]
            if len(parts) < 3:  # need /whats-on/venue/slug
                continue

            url = self.base_url + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title_el = card.select_one(".card__title--maintitle") or card.select_one("h2, h3")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            # Date: calendar icon section
            date_el = card.select_one(".event-info__date span:not(.event-icon)")
            if not date_el:
                date_el = card.select_one(".event-info__date span")
            raw_dates = date_el.get_text(strip=True) if date_el else None

            date_start, date_end = parse_uk_date_range(raw_dates) if raw_dates else (None, None)

            results.append(
                RawExhibition(
                    title=title,
                    url=url,
                    raw_dates=raw_dates,
                    date_start=date_start,
                    date_end=date_end,
                )
            )

        logger.info("[tate] Found %d exhibitions", len(results))
        return results

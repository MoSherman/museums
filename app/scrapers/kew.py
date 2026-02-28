import logging

import httpx
from bs4 import BeautifulSoup

from app.config import HTTP_HEADERS
from app.scrapers.base import BaseScraper, RawExhibition, parse_uk_date_range

logger = logging.getLogger(__name__)

WHATS_ON_URL = "https://www.kew.org/kew-gardens/whats-on"


class KewScraper(BaseScraper):
    museum_slug = "kew"
    base_url = "https://www.kew.org"

    async def fetch(self) -> list[RawExhibition]:
        async with httpx.AsyncClient(headers=HTTP_HEADERS, follow_redirects=True, timeout=30) as client:
            resp = await client.get(WHATS_ON_URL)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        seen_urls = set()

        # Card structure:
        #   <div class="c-card c-card--default">
        #     <h3 class="c-card__title">
        #       <a href="/kew-gardens/whats-on/slug">Title</a>
        #     </h3>
        #     <div class="c-card__custom-date">
        #       <div class="visually-hidden">Custom date</div>
        #       7 February to 8 March 2026
        #     </div>
        #   </div>
        cards = soup.select("div.c-card--default")

        for card in cards:
            link = card.select_one("h3.c-card__title a, a[href*='/kew-gardens/whats-on/']")
            if not link:
                continue

            href = link.get("href", "")
            if not href:
                continue

            url = href if href.startswith("http") else self.base_url + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = link.get_text(strip=True)
            if not title:
                continue

            # Date: custom-date div, strip the visually-hidden child
            date_div = card.select_one(".c-card__custom-date")
            if date_div:
                for hidden in date_div.select(".visually-hidden"):
                    hidden.decompose()
                raw_dates = date_div.get_text(strip=True) or None
            else:
                raw_dates = None

            # Normalise Kew's "X to Y" format to "X – Y" for the parser
            if raw_dates:
                raw_dates = raw_dates.replace(" to ", " – ")

            date_start, date_end = parse_uk_date_range(raw_dates) if raw_dates else (None, None)

            # Admission: label contains "Included with entry" → included with garden ticket
            label_el = card.select_one(".c-card__label")
            label_text = label_el.get_text(separator=" ", strip=True) if label_el else ""
            if "included with entry" in label_text.lower():
                admission = "included"
            else:
                admission = None

            results.append(
                RawExhibition(
                    title=title,
                    url=url,
                    raw_dates=raw_dates,
                    date_start=date_start,
                    date_end=date_end,
                    admission=admission,
                )
            )

        logger.info("[kew] Found %d exhibitions", len(results))
        return results

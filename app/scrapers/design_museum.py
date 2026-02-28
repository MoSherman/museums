import logging

import httpx
from bs4 import BeautifulSoup

from app.config import HTTP_HEADERS
from app.scrapers.base import BaseScraper, RawExhibition, parse_uk_date_range

logger = logging.getLogger(__name__)

EXHIBITIONS_URL = "https://designmuseum.org/exhibitions"


class DesignMuseumScraper(BaseScraper):
    museum_slug = "design_museum"
    base_url = "https://designmuseum.org"

    async def fetch(self) -> list[RawExhibition]:
        async with httpx.AsyncClient(headers=HTTP_HEADERS, follow_redirects=True, timeout=30) as client:
            resp = await client.get(EXHIBITIONS_URL)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        seen_urls = set()

        # Card structure:
        #   <div class="page-item">
        #     <a href="/exhibitions/slug"><figure>...</figure></a>   ← image-only link
        #     <div class="item-content">
        #       <time class="icon-date">Until 29 March 2026</time>
        #       <h2 id="slug">Title</h2>
        #     </div>
        #   </div>
        cards = soup.select("div.page-item")

        for card in cards:
            link = card.select_one("a[href^='/exhibitions/']")
            if not link:
                continue

            href = link.get("href", "")
            url = self.base_url + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            content = card.select_one(".item-content")
            if not content:
                continue

            heading = content.select_one("h1, h2, h3, h4")
            if not heading:
                continue
            title = heading.get_text(strip=True)
            if not title:
                continue

            date_el = content.select_one("time")
            raw_dates = date_el.get_text(strip=True) if date_el else None

            # Skip navigation/category pages that have no date and generic titles
            _nav_slugs = {"future-exhibitions-and-displays", "touring-exhibitions", "past-exhibitions"}
            slug = href.rstrip("/").split("/")[-1]
            if slug in _nav_slugs:
                continue

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

        logger.info("[design_museum] Found %d exhibitions", len(results))
        return results

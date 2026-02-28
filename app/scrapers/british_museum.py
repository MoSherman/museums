import logging

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, RawExhibition, parse_uk_date_range

logger = logging.getLogger(__name__)

EXHIBITIONS_URL = "https://www.britishmuseum.org/exhibitions-events"


class BritishMuseumScraper(BaseScraper):
    museum_slug = "british_museum"
    base_url = "https://www.britishmuseum.org"

    async def fetch(self) -> list[RawExhibition]:
        # curl-cffi impersonates Chrome at TLS level, bypassing Cloudflare
        import asyncio
        from curl_cffi.requests import AsyncSession

        async with AsyncSession() as session:
            resp = await session.get(
                EXHIBITIONS_URL,
                impersonate="chrome",
                timeout=30,
            )
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "lxml")
        results = []
        seen_urls = set()

        # Card structure:
        #   <div class="teaser teaser--exhibition ...">
        #     <h3 class="teaser__title">
        #       <a href="/exhibitions/slug">
        #         <span>Title text <strong>subtitle</strong></span>
        #         <span class="visually-hidden">. Book now.</span>
        #       </a>
        #     </h3>
        #     <footer class="teaser__footer">
        #       <span class="date-display-range">15 January – 25 May 2026</span>
        #     </footer>
        #   </div>
        cards = soup.select("div[class*='teaser--exhibition']")

        for card in cards:
            link = card.select_one("a[href^='/exhibitions/']")
            if not link:
                continue

            href = link.get("href", "")
            url = self.base_url + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Title: text from the visible span (exclude visually-hidden spans)
            for hidden in link.select(".visually-hidden"):
                hidden.decompose()
            title = link.get_text(separator=" ", strip=True)
            if not title:
                continue

            # Date
            date_el = card.select_one("span.date-display-range")
            raw_dates = date_el.get_text(strip=True) if date_el else None
            date_start, date_end = parse_uk_date_range(raw_dates) if raw_dates else (None, None)

            # Admission: defacer div says "Free" or "Book now"
            defacer = card.select_one(".teaser__defacer")
            defacer_text = defacer.get_text(strip=True).lower() if defacer else ""
            if "free" in defacer_text:
                admission = "free"
            elif "book" in defacer_text:
                admission = "paid"
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

        logger.info("[british_museum] Found %d exhibitions", len(results))
        return results

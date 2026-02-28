import logging

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, RawExhibition, parse_uk_date_range

logger = logging.getLogger(__name__)

WHATS_ON_URL = "https://www.vam.ac.uk/whatson"


class VAMScraper(BaseScraper):
    museum_slug = "vam"
    base_url = "https://www.vam.ac.uk"

    async def fetch(self) -> list[RawExhibition]:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-GB",
            )

            # Block images and fonts to reduce load time
            await context.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}",
                lambda route: route.abort(),
            )

            page = await context.new_page()
            try:
                await page.goto(WHATS_ON_URL, wait_until="networkidle", timeout=60000)
            except Exception as exc:
                logger.warning("[vam] Page load issue: %s", exc)

            html = await page.content()
            await browser.close()

        soup = BeautifulSoup(html, "lxml")
        results = []
        seen_urls = set()

        # Card structure: the <a> IS the card
        #   <a href="/exhibitions/slug" class="b-card ... exhibiton-carousel-card">
        #     <h3 class="b-card__heading">Title</h3>
        #     <li class="b-icon-list__icon--calendar">
        #       <p class="b-icon-list__item-text">Closes Sunday, 22 March 2026</p>
        #     </li>
        #   </a>
        cards = soup.select("a[href*='/exhibitions/']")

        for card in cards:
            href = card.get("href", "")
            if not href or href.rstrip("/") in ("/exhibitions",):
                continue

            url = href if href.startswith("http") else self.base_url + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            heading = card.select_one("h3.b-card__heading, h2, h3")
            title = heading.get_text(strip=True) if heading else card.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            # Date is in the calendar icon list item
            date_el = card.select_one(".b-icon-list__icon--calendar .b-icon-list__item-text")
            if not date_el:
                # Fallback: any <p> that isn't the type label
                date_el = card.select_one(
                    "p:not(.exhibiton-carousel-card__event-type-label):not(.b-card__subtitle)"
                )

            raw_dates = date_el.get_text(strip=True) if date_el else None
            # Strip "Closes " / "Opens " prefixes that dateparser handles anyway
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

        logger.info("[vam] Found %d exhibitions", len(results))
        return results

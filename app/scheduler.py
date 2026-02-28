import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import SCRAPE_INTERVAL_HOURS

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def run_all_scrapers():
    """Run all scrapers sequentially, committing each to the DB."""
    from app.database import db_connection
    from app.scrapers.tate import TateScraper
    from app.scrapers.kew import KewScraper
    from app.scrapers.design_museum import DesignMuseumScraper
    from app.scrapers.british_museum import BritishMuseumScraper
    from app.scrapers.vam import VAMScraper

    scrapers = [
        TateScraper(),
        KewScraper(),
        DesignMuseumScraper(),
        BritishMuseumScraper(),
        VAMScraper(),
    ]

    logger.info("Starting scrape run for %d museums", len(scrapers))
    total = 0

    for scraper in scrapers:
        try:
            with db_connection() as conn:
                count = await scraper.run(conn)
                total += count
        except Exception as exc:
            logger.error(
                "Scraper %s failed at DB level: %s",
                scraper.museum_slug, exc, exc_info=True,
            )

    logger.info("Scrape run complete. Total exhibitions stored: %d", total)
    return total


def start_scheduler():
    scheduler = get_scheduler()
    scheduler.add_job(
        run_all_scrapers,
        trigger=IntervalTrigger(hours=SCRAPE_INTERVAL_HOURS),
        id="scrape_all",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started, interval=%dh", SCRAPE_INTERVAL_HOURS)


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

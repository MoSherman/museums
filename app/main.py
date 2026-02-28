import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db, is_db_empty
from app.scheduler import run_all_scrapers, start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()

    if is_db_empty():
        logger.info("Database is empty — running initial scrape")
        await run_all_scrapers()
    else:
        logger.info("Database has data — skipping initial scrape")

    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()


app = FastAPI(title="UK Museum Exhibitions", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

from app.api.routes import router  # noqa: E402
app.include_router(router)

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import MUSEUM_LABELS
from app.database import query_exhibitions, query_status

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    museum: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    exhibitions = query_exhibitions(museum=museum, status=status)
    status_data = query_status()

    # Enrich with human-readable museum labels
    for ex in exhibitions:
        ex["museum_label"] = MUSEUM_LABELS.get(ex["museum"], ex["museum"])

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "exhibitions": exhibitions,
            "status_data": status_data,
            "museum_labels": MUSEUM_LABELS,
            "selected_museum": museum or "",
            "selected_status": status or "",
        },
    )


@router.get("/api/exhibitions")
async def api_exhibitions(
    museum: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    exhibitions = query_exhibitions(museum=museum, status=status)
    for ex in exhibitions:
        ex["museum_label"] = MUSEUM_LABELS.get(ex["museum"], ex["museum"])
    return exhibitions


@router.get("/api/status")
async def api_status():
    return query_status()


@router.post("/api/refresh")
async def api_refresh(background_tasks: BackgroundTasks):
    from app.scheduler import run_all_scrapers
    background_tasks.add_task(run_all_scrapers)
    logger.info("Manual refresh triggered")
    return {"status": "ok", "message": "Scrape started in background"}

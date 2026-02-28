import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from app.config import DB_PATH

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS exhibitions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    museum      TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    date_start  TEXT,
    date_end    TEXT,
    status      TEXT NOT NULL,
    raw_dates   TEXT,
    scraped_at  TEXT NOT NULL,
    UNIQUE(museum, url)
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_connection():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_connection() as conn:
        conn.executescript(SCHEMA)
    logger.info("Database initialised at %s", DB_PATH)


def upsert_exhibition(conn: sqlite3.Connection, row: dict):
    conn.execute(
        """
        INSERT INTO exhibitions
            (museum, title, url, date_start, date_end, status, raw_dates, scraped_at)
        VALUES
            (:museum, :title, :url, :date_start, :date_end, :status, :raw_dates, :scraped_at)
        ON CONFLICT(museum, url) DO UPDATE SET
            title      = excluded.title,
            date_start = excluded.date_start,
            date_end   = excluded.date_end,
            status     = excluded.status,
            raw_dates  = excluded.raw_dates,
            scraped_at = excluded.scraped_at
        """,
        row,
    )


def query_exhibitions(
    museum: str | None = None,
    status: str | None = None,
) -> list[dict]:
    with db_connection() as conn:
        clauses = []
        params: list = []
        if museum:
            clauses.append("museum = ?")
            params.append(museum)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT museum, title, url, date_start, date_end, status, raw_dates, scraped_at
            FROM exhibitions
            {where}
            ORDER BY
                CASE status WHEN 'current' THEN 0 WHEN 'upcoming' THEN 1 ELSE 2 END,
                date_start ASC NULLS LAST,
                museum ASC
        """
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def query_status() -> list[dict]:
    """Return last scrape time and exhibition count per museum."""
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT museum, MAX(scraped_at) as last_scraped, COUNT(*) as count
            FROM exhibitions
            GROUP BY museum
            ORDER BY museum
            """
        ).fetchall()
        return [dict(r) for r in rows]


def is_db_empty() -> bool:
    with db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM exhibitions").fetchone()
        return row[0] == 0

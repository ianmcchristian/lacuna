"""Reporting queries. Plain SQL that runs on both Postgres and SQLite."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Float, Integer, String, column, text
from sqlalchemy.orm import Session

from lacuna.db.models import UTCDateTime

# Window runs before LIMIT, so the change is still vs the true previous scan.
SHELF_HISTORY = text("""
    SELECT s.id AS scan_id,
           s.created_at,
           s.occupancy,
           s.gap_count,
           s.occupancy - LAG(s.occupancy) OVER (ORDER BY s.created_at, s.id) AS occupancy_change
    FROM scans s
    JOIN images i ON i.id = s.image_id
    WHERE i.shelf_id = :shelf_id
    ORDER BY s.created_at DESC, s.id DESC
    LIMIT :limit
""").columns(
    column("scan_id", String),
    column("created_at", UTCDateTime),
    column("occupancy", Float),
    column("gap_count", Integer),
    column("occupancy_change", Float),
)

# Worst = lowest occupancy on the latest scan, i.e. where to send a restock first.
WORST_SHELVES = text("""
    WITH ranked AS (
        SELECT i.shelf_id,
               s.occupancy,
               s.gap_count,
               s.created_at,
               ROW_NUMBER() OVER (
                   PARTITION BY i.shelf_id ORDER BY s.created_at DESC, s.id DESC
               ) AS rn
        FROM scans s
        JOIN images i ON i.id = s.image_id
        WHERE i.shelf_id IS NOT NULL
    )
    SELECT sh.code AS shelf,
           COUNT(*) AS scan_count,
           AVG(r.occupancy) AS avg_occupancy,
           MAX(CASE WHEN r.rn = 1 THEN r.occupancy END) AS latest_occupancy,
           MAX(CASE WHEN r.rn = 1 THEN r.gap_count END) AS latest_gap_count,
           MAX(r.created_at) AS last_scanned_at
    FROM ranked r
    JOIN shelves sh ON sh.id = r.shelf_id
    GROUP BY sh.code
    ORDER BY latest_occupancy ASC NULLS LAST, sh.code
    LIMIT :limit
""").columns(
    column("shelf", String),
    column("scan_count", Integer),
    column("avg_occupancy", Float),
    column("latest_occupancy", Float),
    column("latest_gap_count", Integer),
    column("last_scanned_at", UTCDateTime),
)


@dataclass(frozen=True, slots=True)
class HistoryRow:
    scan_id: str
    created_at: datetime
    occupancy: float | None
    gap_count: int
    occupancy_change: float | None


@dataclass(frozen=True, slots=True)
class ShelfReportRow:
    shelf: str
    scan_count: int
    avg_occupancy: float | None
    latest_occupancy: float | None
    latest_gap_count: int | None
    last_scanned_at: datetime


def shelf_history(session: Session, shelf_id: int, limit: int) -> list[HistoryRow]:
    rows = session.execute(SHELF_HISTORY, {"shelf_id": shelf_id, "limit": limit})
    return [HistoryRow(**row._mapping) for row in rows]


def worst_shelves(session: Session, limit: int) -> list[ShelfReportRow]:
    rows = session.execute(WORST_SHELVES, {"limit": limit})
    return [ShelfReportRow(**row._mapping) for row in rows]

"""SQL-backed shelf reports."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from lacuna.api.deps import SessionDep
from lacuna.db import reports
from lacuna.schemas import SHELF_CODE, HistoryPoint, ShelfHistory, ShelfReport
from lacuna.services import NotFoundError, get_shelf

router = APIRouter(tags=["reports"])


@router.get("/shelves/{code}/history", responses={404: {"description": "Unknown shelf"}})
def shelf_history(
    code: Annotated[str, Path(pattern=SHELF_CODE)],
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> ShelfHistory:
    """Scans for one shelf, newest first, with the occupancy change vs the scan before."""
    try:
        shelf = get_shelf(session, code)
    except NotFoundError as err:
        raise HTTPException(404, str(err)) from err
    rows = reports.shelf_history(session, shelf.id, limit)
    return ShelfHistory(
        shelf=code,
        baseline_scan_id=shelf.baseline_scan_id,
        scans=[HistoryPoint.model_validate(r) for r in rows],
    )


@router.get("/reports/worst-shelves")
def worst_shelves(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 10
) -> list[ShelfReport]:
    """Shelves ranked by occupancy on their latest scan, emptiest first."""
    return [ShelfReport.model_validate(r) for r in reports.worst_shelves(session, limit)]

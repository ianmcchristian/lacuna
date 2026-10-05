"""Baseline compare: mark a stocked scan, then see what sold out of each gap."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response

from lacuna.api.deps import SessionDep
from lacuna.api.scans import NOT_FOUND
from lacuna.baseline import WrongShelfError, missing_products, product_crop, set_baseline
from lacuna.schemas import SHELF_CODE, BaselineIn, DetectionOut, GapOut, MissingGap, MissingOut
from lacuna.services import NotFoundError

router = APIRouter(tags=["baseline"])


@router.post(
    "/shelves/{code}/baseline",
    responses={**NOT_FOUND, 422: {"description": "Scan is from another shelf"}},
)
def put_baseline(
    code: Annotated[str, Path(pattern=SHELF_CODE)], body: BaselineIn, session: SessionDep
) -> BaselineIn:
    """Use this scan as the shelf's stocked baseline. Replaces any earlier one."""
    try:
        shelf = set_baseline(session, code, body.scan_id)
    except NotFoundError as err:
        raise HTTPException(404, str(err)) from err
    except WrongShelfError as err:
        raise HTTPException(422, str(err)) from err
    return BaselineIn(scan_id=shelf.baseline_scan_id or body.scan_id)


@router.get("/results/{scan_id}/missing", responses=NOT_FOUND)
def get_missing(scan_id: str, session: SessionDep) -> MissingOut:
    """For each gap, the baseline products that used to sit there."""
    try:
        missing = missing_products(session, scan_id)
    except NotFoundError as err:
        raise HTTPException(404, str(err)) from err
    return MissingOut(
        scan_id=missing.scan_id,
        baseline_scan_id=missing.baseline_scan_id,
        aligned=missing.aligned,
        gaps=[
            MissingGap(
                gap=GapOut.model_validate(gap),
                products=[DetectionOut.model_validate(p) for p in products],
            )
            for gap, products in missing.gaps
        ],
    )


@router.get(
    "/results/{scan_id}/products/{detection_id}/crop",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}, **NOT_FOUND},
)
def get_crop(scan_id: str, detection_id: int, session: SessionDep) -> Response:
    """One detected product, cut out of the scan's photo."""
    try:
        data = product_crop(session, scan_id, detection_id)
    except NotFoundError as err:
        raise HTTPException(404, str(err)) from err
    # crops never change once a scan exists
    return Response(data, media_type="image/jpeg", headers={"cache-control": "max-age=86400"})

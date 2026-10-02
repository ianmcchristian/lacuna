"""Upload, detect, and fetch results."""

from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from lacuna.api.deps import DetectorDep, SessionDep, SettingsDep, StoreDep
from lacuna.db.models import ImageRecord
from lacuna.imaging import encode_jpeg
from lacuna.schemas import SHELF_CODE, DetectRequest, ImageOut, ScanOut
from lacuna.services import (
    NotFoundError,
    UploadRejected,
    get_scan,
    load_pixels,
    run_scan,
    save_upload,
)
from lacuna.vision.draw import draw_overlay

router = APIRouter(tags=["scans"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"description": "Not found"}}


def to_image_out(record: ImageRecord) -> ImageOut:
    return ImageOut(
        id=record.id,
        shelf=record.shelf.code if record.shelf else None,
        filename=record.filename,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        width=record.width,
        height=record.height,
        created_at=record.created_at,
    )


@router.post(
    "/images",
    status_code=201,
    responses={
        413: {"description": "File too large"},
        415: {"description": "Not a jpeg, png, or webp"},
        422: {"description": "Empty or unreadable image"},
    },
)
def upload_image(
    session: SessionDep,
    store: StoreDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="Shelf photo: jpeg, png, or webp")],
    shelf: Annotated[str | None, Form(pattern=SHELF_CODE, description="e.g. aisle4-bay2")] = None,
) -> ImageOut:
    """Store a shelf photo. Run /detect on it next."""
    data = file.file.read(settings.max_upload_bytes + 1)  # one extra byte catches oversize
    try:
        record = save_upload(
            session,
            store,
            data=data,
            filename=file.filename or "upload",
            content_type=file.content_type or "",
            max_bytes=settings.max_upload_bytes,
            shelf_code=shelf,
        )
    except UploadRejected as err:
        raise HTTPException(err.status_code, err.detail) from err
    return to_image_out(record)


@router.post("/detect", status_code=201, responses={**NOT_FOUND, 503: {"description": "No model"}})
def detect(
    body: DetectRequest,
    session: SessionDep,
    store: StoreDep,
    detector: DetectorDep,
    settings: SettingsDep,
) -> ScanOut:
    """Find products and gaps in an uploaded image and save the scan."""
    try:
        scan = run_scan(session, store, detector, body.image_id, settings.min_gap_ratio)
    except NotFoundError as err:
        raise HTTPException(404, str(err)) from err
    return ScanOut.model_validate(scan)


@router.get("/results/{scan_id}", responses=NOT_FOUND)
def get_result(scan_id: str, session: SessionDep) -> ScanOut:
    try:
        return ScanOut.model_validate(get_scan(session, scan_id))
    except NotFoundError as err:
        raise HTTPException(404, str(err)) from err


@router.get(
    "/results/{scan_id}/overlay",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}, **NOT_FOUND},
)
def get_overlay(scan_id: str, session: SessionDep, store: StoreDep) -> Response:
    """The original photo with products in green and gaps in red."""
    try:
        scan = get_scan(session, scan_id)
        image = load_pixels(store, scan.image_id)
    except NotFoundError as err:
        raise HTTPException(404, str(err)) from err
    overlay = draw_overlay(image, scan.detections, scan.gaps)
    return Response(encode_jpeg(overlay), media_type="image/jpeg")

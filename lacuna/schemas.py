"""Request and response bodies."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SHELF_CODE = r"^[A-Za-z0-9._-]{1,64}$"


class Health(BaseModel):
    status: str
    version: str
    commit: str | None = None  # git SHA of the deploy, so CI can tell when a new one is live


class Ready(BaseModel):
    status: str
    database: bool
    model: str | None


class ImageOut(BaseModel):
    id: str
    shelf: str | None
    filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    created_at: datetime


class DetectRequest(BaseModel):
    image_id: str = Field(min_length=1, max_length=32)


class BoxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    x1: float
    y1: float
    x2: float
    y2: float
    score: float


class GapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row: int
    x1: float
    y1: float
    x2: float
    y2: float
    width_ratio: float


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    image_id: str
    model: str
    product_count: int
    gap_count: int
    occupancy: float | None = Field(
        description="1.0 = no gaps found. None = not enough products to judge."
    )
    latency_ms: float
    created_at: datetime
    detections: list[BoxOut]
    gaps: list[GapOut]


class HistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: str
    created_at: datetime
    occupancy: float | None
    gap_count: int
    occupancy_change: float | None


class ShelfHistory(BaseModel):
    shelf: str
    baseline_scan_id: str | None = Field(description="The stocked scan gaps are compared to.")
    scans: list[HistoryPoint]


class BaselineIn(BaseModel):
    scan_id: str = Field(min_length=1, max_length=32)


class DetectionOut(BoxOut):
    id: int


class MissingGap(BaseModel):
    gap: GapOut
    products: list[DetectionOut] = Field(
        description="Products in the baseline scan that sat where this gap is now."
    )


class MissingOut(BaseModel):
    scan_id: str
    baseline_scan_id: str | None
    aligned: bool = Field(description="False if the photos couldn't be lined up, or no baseline.")
    gaps: list[MissingGap]


class ShelfReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shelf: str
    scan_count: int
    avg_occupancy: float | None
    latest_occupancy: float | None
    latest_gap_count: int | None
    last_scanned_at: datetime

"""ORM tables.

shelves 1--* images 1--* scans 1--* detections
                               1--* gaps
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Dialect, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Always hand back aware UTC datetimes. SQLite drops the tzinfo, Postgres keeps it."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        result: datetime = value
        if result.tzinfo is None:
            return result.replace(tzinfo=UTC)
        return result.astimezone(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Shelf(Base):
    __tablename__ = "shelves"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ImageRecord(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    shelf_id: Mapped[int | None] = mapped_column(ForeignKey("shelves.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    shelf: Mapped[Shelf | None] = relationship()


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id"), index=True)
    model: Mapped[str] = mapped_column(String(64))
    product_count: Mapped[int] = mapped_column(Integer)
    gap_count: Mapped[int] = mapped_column(Integer)
    occupancy: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    image: Mapped[ImageRecord] = relationship()
    detections: Mapped[list["DetectionRecord"]] = relationship(
        cascade="all, delete-orphan", order_by="DetectionRecord.id"
    )
    gaps: Mapped[list["GapRecord"]] = relationship(
        cascade="all, delete-orphan", order_by="GapRecord.id"
    )


class DetectionRecord(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    x2: Mapped[float] = mapped_column(Float)
    y2: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)


class GapRecord(Base):
    __tablename__ = "gaps"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    row: Mapped[int] = mapped_column(Integer)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    x2: Mapped[float] = mapped_column(Float)
    y2: Mapped[float] = mapped_column(Float)
    width_ratio: Mapped[float] = mapped_column(Float)

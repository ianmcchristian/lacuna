"""Shared geometry types."""

from dataclasses import dataclass
from typing import Protocol


class Rect(Protocol):
    """Anything with xyxy pixel coords: Box, Gap, or a database row."""

    @property
    def x1(self) -> float: ...
    @property
    def y1(self) -> float: ...
    @property
    def x2(self) -> float: ...
    @property
    def y2(self) -> float: ...


@dataclass(frozen=True, slots=True)
class Box:
    """Axis-aligned box in original image pixels."""

    x1: float
    y1: float
    x2: float
    y2: float
    score: float = 1.0

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

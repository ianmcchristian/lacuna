"""Detection, gap analysis, and drawing. No web or database code in here."""

from lacuna.vision.detector import Detector, OnnxDetector
from lacuna.vision.gaps import Gap, ShelfAnalysis, analyze_shelf
from lacuna.vision.types import Box

__all__ = ["Box", "Detector", "Gap", "OnnxDetector", "ShelfAnalysis", "analyze_shelf"]

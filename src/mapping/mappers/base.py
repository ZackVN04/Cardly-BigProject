from abc import ABC, abstractmethod
from typing import Any


class BaseMapper(ABC):
    """Abstract base for all document-type mappers.

    Each subclass receives the raw OCR + Vision dicts and implements
    extract() to produce a flat dict of field_name → raw_value.
    Fields that cannot be found must be returned as None (never omitted).
    """

    def __init__(self, ocr_result: dict[str, Any], vision_result: dict[str, Any]) -> None:
        self.ocr = ocr_result
        self.vision = vision_result
        self._blocks: list[dict] = ocr_result.get("blocks", [])
        self._regions: list[dict] = vision_result.get("detected_regions", [])

    @abstractmethod
    def extract(self) -> dict[str, Any]:
        """Return flat dict mapping field names → raw extracted values.
        All expected keys must be present; use None for unextracted fields.
        """
        ...

    def _find_region(self, label: str) -> dict | None:
        """Return first vision region matching the given label, or None."""
        for region in self._regions:
            if region.get("label") == label:
                return region
        return None

    def _find_block_near(self, bbox: list[float], threshold: float = 50.0) -> dict | None:
        """Return OCR block whose bbox centroid is closest to the given bbox centroid."""
        if not bbox or not self._blocks:
            return None
        rx, ry = bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2
        best, best_dist = None, float("inf")
        for block in self._blocks:
            bx, by = block["bbox"][0] + block["bbox"][2] / 2, block["bbox"][1] + block["bbox"][3] / 2
            dist = ((rx - bx) ** 2 + (ry - by) ** 2) ** 0.5
            if dist < best_dist:
                best_dist, best = dist, block
        return best if best_dist <= threshold else None

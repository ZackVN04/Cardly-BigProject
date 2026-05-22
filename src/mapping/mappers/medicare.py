# TODO(P5 — Hui): Implement MedicareMapper
from typing import Any

from src.mapping.mappers.base import BaseMapper


class MedicareMapper(BaseMapper):
    """Maps OCR + Vision output to MedicareFields."""

    FIELD_LABELS = ["card_number", "irn", "full_name", "valid_to"]

    def extract(self) -> dict[str, Any]:
        result: dict[str, Any] = {field: None for field in self.FIELD_LABELS}

        for label in self.FIELD_LABELS:
            region = self._find_region(label)
            if region:
                block = self._find_block_near(region["bbox"])
                if block:
                    result[label] = block["text"]

        return result

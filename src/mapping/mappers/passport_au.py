# TODO(P5 — Hui): Implement PassportMapper
from typing import Any

from src.mapping.mappers.base import BaseMapper


class PassportMapper(BaseMapper):
    """Maps OCR + Vision output to PassportFields for Australian passports."""

    FIELD_LABELS = [
        "document_no", "type", "country_code", "surname", "given_names",
        "nationality", "date_of_birth", "sex", "place_of_birth",
        "date_of_issue", "date_of_expiry", "authority", "mrz_line1", "mrz_line2",
    ]

    def extract(self) -> dict[str, Any]:
        result: dict[str, Any] = {field: None for field in self.FIELD_LABELS}

        for label in self.FIELD_LABELS:
            region = self._find_region(label)
            if region:
                block = self._find_block_near(region["bbox"])
                if block:
                    result[label] = block["text"]

        return result

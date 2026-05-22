# TODO(P5 — Hui): Implement DriverLicenceMapper
from typing import Any

from src.mapping.mappers.base import BaseMapper


class DriverLicenceMapper(BaseMapper):
    """Maps OCR + Vision output to DriverLicenceFields for VIC licences."""

    FIELD_LABELS = [
        "licence_no", "full_name", "address", "date_of_birth",
        "licence_expiry", "licence_type", "conditions", "state",
    ]

    def extract(self) -> dict[str, Any]:
        result: dict[str, Any] = {field: None for field in self.FIELD_LABELS}

        for label in self.FIELD_LABELS:
            region = self._find_region(label)
            if region:
                block = self._find_block_near(region["bbox"])
                if block:
                    result[label] = block["text"]

        # state defaults to VIC for driver_licence_vic
        if result["state"] is None:
            result["state"] = "VIC"

        return result

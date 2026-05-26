from typing import Any
import re

from src.mapping.mappers.base import BaseMapper


class BusinessCardMapper(BaseMapper):
    """Maps OCR + Vision output to BusinessCardFields for business cards."""

    FIELD_LABELS = [
        "name", "phone", "email", "web", "position", "company"
    ]

    def extract(self) -> dict[str, Any]:
        result: dict[str, Any] = {field: None for field in self.FIELD_LABELS}

        # 1. Match using AI Vision regions and OCR blocks
        for label in self.FIELD_LABELS:
            region = self._find_region(label)
            # Fallback to aliases if needed
            if not region and label == "name":
                region = self._find_region("full_name")
            if not region and label == "web":
                region = self._find_region("website")

            if region:
                block = self._find_block_near(region["bbox"])
                if block:
                    result[label] = block["text"]

        # 2. Fallback heuristic: search raw OCR blocks if fields are missing
        if not result["email"]:
            for block in self._blocks:
                text = block.get("text", "")
                match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
                if match:
                    result["email"] = match.group(0)
                    break

        if not result["phone"]:
            for block in self._blocks:
                text = block.get("text", "")
                cleaned_text = re.sub(r"^(Điện thoại|Phone|Tel|Cell|Mobile|SĐT|M|P|T)\s*[:.-]\s*", "", text, flags=re.IGNORECASE).strip()
                # Check if it has at least 7 digits
                digits_only = re.sub(r"\D", "", cleaned_text)
                if len(digits_only) >= 7:
                    result["phone"] = cleaned_text
                    break

        if not result["web"]:
            for block in self._blocks:
                text = block.get("text", "")
                cleaned_text = re.sub(r"^(Website|Web|Url|W)\s*[:.-]\s*", "", text, flags=re.IGNORECASE).strip()
                if any(kw in cleaned_text.lower() for kw in ["www.", "http://", "https://"]):
                    result["web"] = cleaned_text
                    break

        # Clean prefix labels from fields if matched blocks contain them
        prefix_pattern = r"^(Điện thoại|Phone|Tel|Cell|Mobile|SĐT|Email|Website|Web|Url|W|P|T|E|M)\s*[:.-]\s*"
        for label in ["phone", "email", "web"]:
            if result[label]:
                result[label] = re.sub(prefix_pattern, "", result[label], flags=re.IGNORECASE).strip()

        return result

from __future__ import annotations

import re
from typing import Any

from src.mapping.mappers.base import BaseMapper

# ---------------------------------------------------------------------------
# Compiled patterns — used for regex-first structured field extraction
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# Covers international (+84 ...) and local Vietnamese (09xx xxx xxx) formats.
# Uses backtracking-friendly groups so digit clusters of varying sizes match.
_PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s\-]?)?"          # optional country code
    r"\(?\d{2,4}\)?"                    # area/prefix (may have parens)
    r"[\s.\-]?\d{3,4}"                  # middle group
    r"[\s.\-]?\d{3,6}",                 # trailing group
)

# Matches full URLs, www-domains, and bare domain.tld (e.g. theimprobability.co)
_WEB_RE = re.compile(
    r"https?://[^\s]+"                                                        # https://…
    r"|www\.[a-zA-Z0-9][a-zA-Z0-9.\-]+[a-zA-Z0-9]"                           # www.domain
    r"|[a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?(?:/\S*)?",  # domain.tld
    re.IGNORECASE,
)

# Label prefixes that appear before the actual field value in OCR text
# e.g. "Email: abc@def.com" → strip "Email: " → "abc@def.com"
_PREFIX_RE = re.compile(
    r"^(?:Điện\s*thoại|Phone|Tel|Cell|Mobile|SĐT"
    r"|E\s*mail|Email"
    r"|Website|Web|Url"
    r"|Địa\s*chỉ|Address"
    r"|[WPTME])\s*[:.\-]\s*",
    re.IGNORECASE,
)

# Guard: text matching these patterns should NOT be assigned to name/position/company
_CONTACT_GUARD_RE = re.compile(
    r"@|https?://|www\."
    r"|(?:\+?\d{2,3}[\s\-]?)?\d{3,4}[\s.\-]\d{3,4}",  # phone-like digit clusters
    re.IGNORECASE,
)


class BusinessCardMapper(BaseMapper):
    """Maps OCR + Vision output to BusinessCardFields for business cards.

    Extraction is split into two phases:

    **Phase 1 — regex-first (email, phone, web)**
        Scan every OCR block with compiled patterns, independent of Vision
        spatial layout.  Strips label prefixes (e.g. ``"Email: "``) before
        matching.  The first block that yields a valid pattern wins.

    **Phase 2 — Vision-guided spatial match (name, position, company)**
        Text-identity fields lack strong regex patterns.  A Vision-detected
        bounding-box region is used to find the nearest OCR block (centroid
        distance ≤ 50 px).  A contact-info guard prevents phone / email / URL
        text from being mislabelled as a person name or company.

    ``self.field_block_refs`` is populated during ``extract()`` so that P6
    can look up the OCR block confidence for every mapped field.
    """

    FIELD_LABELS = ("name", "position", "company", "address", "phone", "email", "web")

    # Vision region label aliases to try when the primary label is missing
    _ALIASES: dict[str, list[str]] = {
        "name":     ["full_name"],
        "position": ["title", "job_title"],
        "company":  ["organization", "org"],
    }

    def extract(self) -> dict[str, Any]:
        result: dict[str, Any] = {f: None for f in self.FIELD_LABELS}
        self.field_block_refs = {f: [] for f in self.FIELD_LABELS}

        # ------------------------------------------------------------------
        # Phase 1: regex-first — structured contact fields
        # ------------------------------------------------------------------
        self._extract_email(result)
        self._extract_phone(result)
        self._extract_web(result)

        # ------------------------------------------------------------------
        # Phase 2: Vision-guided spatial match — text identity fields
        # ------------------------------------------------------------------
        for label in ("name", "position", "company"):
            for lbl in [label] + self._ALIASES.get(label, []):
                region = self._find_region(lbl)
                if not region:
                    continue
                block = self._find_block_near(region["bbox"])
                if block:
                    text = _PREFIX_RE.sub("", block.get("text", "")).strip()
                    # Guard: reject if text looks like contact info (email/phone/URL)
                    if text and not _CONTACT_GUARD_RE.search(text):
                        result[label] = text
                        self._record_ref(label, block)
                break  # found a matching region — stop trying aliases

        # address: spatial match like identity fields but allow longer text
        self._extract_address(result)

        return result

    # ------------------------------------------------------------------
    # Phase 1 helpers
    # ------------------------------------------------------------------

    def _extract_email(self, result: dict[str, Any]) -> None:
        """First block whose text (after prefix strip) contains a valid email."""
        for block in self._blocks:
            cleaned = _PREFIX_RE.sub("", block.get("text", "")).strip()
            m = _EMAIL_RE.search(cleaned)
            if m:
                result["email"] = m.group(0)
                self._record_ref("email", block)
                return

    def _extract_phone(self, result: dict[str, Any]) -> None:
        """First block whose cleaned text matches a phone pattern.

        Blocks containing ``@`` or URL keywords are skipped to avoid matching
        an email domain or website against the phone regex.
        """
        for block in self._blocks:
            raw = block.get("text", "")
            cleaned = _PREFIX_RE.sub("", raw).strip()
            if "@" in cleaned or re.search(r"https?://|www\.", cleaned, re.IGNORECASE):
                continue
            m = _PHONE_RE.search(cleaned)
            if m:
                result["phone"] = m.group(0)
                self._record_ref("phone", block)
                return

    def _extract_web(self, result: dict[str, Any]) -> None:
        """First block whose cleaned text is entirely a URL or bare domain.

        Requires no internal whitespace (after prefix removal) so that
        company names or addresses are not mistakenly captured.
        Blocks containing ``@`` are skipped to avoid matching the domain part
        of an email address.
        """
        for block in self._blocks:
            raw = block.get("text", "")
            cleaned = _PREFIX_RE.sub("", raw).strip()
            if "@" in cleaned or re.search(r"\s", cleaned):
                continue
            # fullmatch: the entire cleaned token must be a URL / domain
            if _WEB_RE.fullmatch(cleaned):
                result["web"] = cleaned
                self._record_ref("web", block)
                return

    def _extract_address(self, result: dict[str, Any]) -> None:
        """Vision-guided spatial match for address.

        Address lines may contain digits and commas, so the contact guard is
        intentionally relaxed here — we only skip blocks that look like a
        pure phone number or a URL/email.
        """
        _ADDR_SKIP_RE = re.compile(
            r"@|https?://|www\."
            r"|^\+?\d[\d\s\-().]{6,}$",  # pure phone number line
            re.IGNORECASE,
        )
        for lbl in ["address"] + self._ALIASES.get("address", []):
            region = self._find_region(lbl)
            if not region:
                continue
            block = self._find_block_near(region["bbox"], threshold=200.0)
            if block:
                text = _PREFIX_RE.sub("", block.get("text", "")).strip()
                if text and not _ADDR_SKIP_RE.search(text):
                    result["address"] = text
                    self._record_ref("address", block)
            break

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _record_ref(self, field: str, block: dict[str, Any]) -> None:
        """Store the block id in field_block_refs if the block has one."""
        bid = block.get("id")
        if bid:
            self.field_block_refs[field] = [bid]

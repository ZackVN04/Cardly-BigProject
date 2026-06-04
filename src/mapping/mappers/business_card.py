from __future__ import annotations

import re
from collections import Counter
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
    r"(?:\+\d{1,3}\)?[\s\-]?)?"       # optional country code
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

        text_candidates = self._extract_from_text_lines()
        self._apply_text_candidates(result, text_candidates)

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

    def _apply_text_candidates(
        self,
        result: dict[str, Any],
        candidates: dict[str, str],
    ) -> None:
        non_empty_values = [value for value in result.values() if isinstance(value, str) and value.strip()]
        duplicated_values = {
            value for value, count in Counter(non_empty_values).items()
            if count >= 3
        }

        for label in self.FIELD_LABELS:
            value = result.get(label)
            should_replace = (
                not value
                or value in duplicated_values
                or not self._value_matches_field(label, value)
            )
            if should_replace and candidates.get(label):
                result[label] = candidates[label]
            elif should_replace and label in {"phone", "email", "web"}:
                result[label] = None

    def _extract_from_text_lines(self) -> dict[str, str]:
        lines = self._ocr_lines()
        joined_text = "\n".join(lines)
        candidates: dict[str, str] = {}

        email_match = re.search(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            joined_text,
        )
        if email_match:
            candidates["email"] = email_match.group(0)

        phone = self._find_phone(lines)
        if phone:
            candidates["phone"] = phone

        web = self._find_web(lines)
        if web:
            candidates["web"] = web

        name_index, name = self._find_name(lines)
        if name:
            candidates["name"] = name

        position = self._find_position(lines, name_index)
        if position:
            candidates["position"] = position

        company = self._find_company(lines, name_index)
        if company:
            candidates["company"] = company

        return candidates

    def _ocr_lines(self) -> list[str]:
        raw_text = self.ocr.get("raw_text") or self.ocr.get("raw_ocr_output") or ""
        lines: list[str] = []

        if isinstance(raw_text, str):
            lines.extend(raw_text.splitlines())

        if not lines:
            lines.extend(str(block.get("text", "")) for block in self._blocks)

        cleaned_lines: list[str] = []
        seen: set[str] = set()
        for line in lines:
            cleaned = " ".join(str(line).split())
            if cleaned and cleaned not in seen:
                cleaned_lines.append(cleaned)
                seen.add(cleaned)
        return cleaned_lines

    def _find_phone(self, lines: list[str]) -> str | None:
        phone_pattern = re.compile(r"(\+?\d[\d\s().-]{5,}\d)")
        labelled_lines = [
            line for line in lines
            if re.search(r"\b(phone|tel|cell|mobile|sdt|p|t)\b|điện thoại", line, re.IGNORECASE)
        ]

        for line in labelled_lines + lines:
            match = phone_pattern.search(line)
            if not match:
                continue
            candidate = re.sub(
                r"^(điện thoại|phone|tel|cell|mobile|sdt|m|p|t)\s*[:.-]\s*",
                "",
                match.group(0).strip(),
                flags=re.IGNORECASE,
            )
            digits = re.sub(r"\D", "", candidate)
            if 7 <= len(digits) <= 15:
                return candidate
        return None

    def _find_web(self, lines: list[str]) -> str | None:
        domain_pattern = re.compile(
            r"\b(?:https?://|www\.)?[a-zA-Z0-9][a-zA-Z0-9-]*(?:\.[a-zA-Z]{2,})+\b"
        )
        labelled_lines = [
            line for line in lines
            if re.search(r"\b(web|website|url|www)\b", line, re.IGNORECASE)
        ]

        for line in labelled_lines + lines:
            if "@" in line:
                continue
            match = domain_pattern.search(line)
            if match:
                return match.group(0)
        return None

    def _find_name(self, lines: list[str]) -> tuple[int | None, str | None]:
        best_index: int | None = None
        best_line: str | None = None
        best_score = -1

        for index, line in enumerate(lines):
            if self._is_contact_or_address_line(line) or self._looks_like_company_line(line):
                continue
            tokens = line.split()
            if not 2 <= len(tokens) <= 4:
                continue
            if not all(re.match(r"^[A-Za-zÀ-ỹ'’-]+$", token) for token in tokens):
                continue
            if tokens[0].lower() in {"and", "or", "for"}:
                continue

            score = 1
            if any(token.isupper() and len(token) > 1 for token in tokens[1:]):
                score += 3
            if any(token[:1].isupper() and token[1:].islower() for token in tokens):
                score += 2
            if index > 0:
                score += 1

            if score > best_score:
                best_score = score
                best_index = index
                best_line = line

        return best_index, best_line

    def _find_position(self, lines: list[str], name_index: int | None) -> str | None:
        title_keywords = (
            "coordinator", "manager", "director", "engineer", "developer",
            "designer", "consultant", "specialist", "officer", "executive",
            "founder", "president", "assistant", "analyst", "sales",
            "marketing", "conference", "professor", "lecturer", "ceo", "cto",
        )

        search_lines = lines[name_index + 1:] if name_index is not None else lines
        for line in search_lines:
            lower = line.lower()
            if self._is_contact_or_address_line(line):
                continue
            if any(keyword in lower for keyword in title_keywords):
                return line
        return None

    def _find_company(self, lines: list[str], name_index: int | None) -> str | None:
        org_lines: list[str] = []

        if name_index is not None:
            after_name = lines[name_index + 1:]
            for line in after_name:
                if self._is_contact_or_address_line(line):
                    break
                if self._find_position([line], None) == line:
                    break
                if self._looks_like_company_line(line):
                    return line

        limit = name_index if name_index is not None else len(lines)
        for line in lines[:limit]:
            if self._is_contact_or_address_line(line):
                continue
            if self._looks_like_company_line(line) or org_lines:
                org_lines.append(line)
                continue
            if len(line.split()) >= 2:
                org_lines.append(line)

        while org_lines and re.search(r"\.[a-zA-Z]{2,}\b", org_lines[-1]):
            org_lines.pop()

        if org_lines:
            return " ".join(org_lines[:2]).strip()
        return None

    def _value_matches_field(self, label: str, value: Any) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False
        stripped = value.strip()

        if label == "email":
            return bool(re.fullmatch(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", stripped))
        if label == "phone":
            digits = re.sub(r"\D", "", stripped)
            return 7 <= len(digits) <= 15
        if label == "web":
            return bool(re.search(r"\b(?:https?://|www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+\b", stripped))
        if label in {"name", "position", "company"}:
            return not self._is_contact_or_address_line(stripped)
        return True

    def _is_contact_or_address_line(self, line: str) -> bool:
        lower = line.lower()
        return (
            "@" in line
            or bool(re.search(r"\b(phone|tel|cell|mobile|email|e-mail|skype|web|website|url)\b", lower))
            or bool(re.search(r"\b(address|begijnhoflaan|street|road|avenue|laan)\b", lower))
            or bool(re.search(r"\+?\d[\d\s().-]{5,}\d", line))
        )

    def _looks_like_company_line(self, line: str) -> bool:
        lower = line.lower()
        company_keywords = (
            "company", "corp", "corporation", "ltd", "llc", "inc", "jsc",
            "institute", "university", "school", "engineering", "systems",
            "solutions", "technologies", "group", "foundation", "association",
            "telecommunications", "informatics", "sciences", "swinburne",
            "vietnam", "technology", "education", "program",
        )
        return any(keyword in lower for keyword in company_keywords)

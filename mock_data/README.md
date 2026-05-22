# Mock Data for OCR Project

This directory contains reference JSON payloads for every stage of the OCR pipeline. **Every team member should use these as the single source of truth** for module input/output shapes when developing in isolation.

## File index

| File | Stage | Source image |
|---|---|---|
| `passport_au_ocr_output.json` | P4 output → P5 input | `1.jpg` |
| `passport_au_mapped.json` | P5 output → P6/P7 input | `1.jpg` |
| `medicare_ocr_output.json` | P4 output → P5 input | `2.jpg` |
| `medicare_mapped.json` | P5 output → P6/P7 input | `2.jpg` |
| `driver_licence_vic_ocr_output.json` | P4 output → P5 input | `3.jpg` |
| `driver_licence_vic_mapped.json` | P5 output → P6/P7 input | `3.jpg` |
| `document_full_state.json` | P6 output → P7 review input; also the response of `GET /documents/{processing_id}` | `1.jpg` |

## How each member uses these files

### P2 (Phúc Khang) — Intake & Validation
- You don't have an "input" mock — your input is the uploaded file itself (use `1.jpg`, `2.jpg`, `3.jpg`).
- Your **output** is the `UploadedImage` Beanie document — your module sets `status`, `processing_id`, `file_hash_sha256`, etc.
- For unit tests: feed corrupted bytes, oversize files, duplicate hashes; assert correct `status` and `validation_errors`.

### P3 (Phú Phàm) — Pre-processing
- **Input**: a file path + a `processing_id` string. That's it.
- **Output**: writes a `PreprocessedImage` document. No JSON contract issue — you control both ends.
- For unit tests: rotated images, dark images, low-DPI images; assert `rotation_applied`, `resolution_dpi`, `steps_applied`.

### P4 (Cường, Thiệt) — OCR + AI Vision
- **Input**: path to a preprocessed image.
- **Output**: must match the structure of `*_ocr_output.json` files. **This is the contract with P5.**
- Two separate sub-modules (`ocr.extract()` and `vision.detect()`) — but the combined output is what P5 consumes.
- For unit tests: feed `1.jpg`, `2.jpg`, `3.jpg` through your engine; the JSON shape must match the mocks.

### P5 (Hui) — Business Field Mapping
- **Input**: any of `*_ocr_output.json` files (these are P4 output).
- **Output**: matches `*_mapped.json` files. **This is the contract with P6.**
- 3 mappers (one per `doc_type`), 1 normalizer, 1 validator.
- For unit tests: load `passport_au_ocr_output.json`, run your mapper, compare output to `passport_au_mapped.json`.

### P6 (Nhân Tài) — Confidence Scoring & Storage
- **Input**: any of `*_mapped.json` files (these are P5 output).
- **Output**: adds the `confidence` block and `processing_history` array (see `document_full_state.json`).
- Implements `GET /documents`, `GET /documents/{id}` endpoints.
- For unit tests: load `passport_au_mapped.json`, run scoring, assert `overall_score`, classification, `auto_approved` flags.

### P7 (Khanh) — JSON Review
- **Input**: `document_full_state.json` (this is what `GET /documents/{id}` returns).
- **Output**: edited document → `FinalizedDocument`.
- Implements `PATCH /documents/{id}/review`, `POST /documents/{id}/confirm`.
- For frontend dev: use `document_full_state.json` directly to build the review UI without waiting for the backend.

## Mock conventions

- `processing_id` format: `PRC-YYYYMMDD-XXXXXX` (date + 6-char random base32).
- All timestamps are UTC ISO-8601 with `Z` suffix.
- `_id` fields are 24-character hex strings (MongoDB ObjectId).
- `_comment` fields at the top of each file are documentation only — strip before using in code.
- The 3 sample images correspond to fixed `processing_id`s in these mocks to make cross-referencing easy:
  - `1.jpg` (passport) → `PRC-20260521-7H3K9F`
  - `2.jpg` (medicare) → `PRC-20260521-8K4L2M`
  - `3.jpg` (driver licence) → `PRC-20260521-9P5N3Q`

## Loading mocks in tests

```python
import json
from pathlib import Path

MOCK_DIR = Path(__file__).parent.parent / "mock_data"

def load_mock(name: str) -> dict:
    with open(MOCK_DIR / f"{name}.json") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}

# Example: P5 unit test
def test_passport_mapper():
    ocr_input = load_mock("passport_au_ocr_output")
    expected = load_mock("passport_au_mapped")
    result = map_passport_fields(ocr_input)
    assert result["extracted_fields"] == expected["extracted_fields"]
```

## When the real P4 lands

If the actual OCR/Vision output differs from these mocks, **update the mocks first**, push to a branch, get P4 and P5 reviewers to sign off, **then** update the mapping code. Mocks are the source of truth, not the code.

## Important notes about the sample images

- `2.jpg` (Medicare) intentionally shows an expired card (`08/2016`). The mock reflects this — `valid_to.not_in_past` validation **fails on purpose** so P6 can test the "failed validation" branch.
- `3.jpg` (Driver Licence) is also expired (`20-05-2019`). Same reason — useful for testing edge cases.
- Only `1.jpg` (Passport) has all validations passing.

This gives the team three concrete states to test against without needing to fabricate edge cases.

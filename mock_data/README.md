# Mock Data for OCR & Cardly Document Processing System

This directory contains reference JSON payloads for every stage of the OCR pipeline and authentication features. **Every team member should use these as the single source of truth** for module input/output shapes when developing in isolation.

## File Index

### 1. Document Pipeline Contracts (OCR, Mapping, Scoring, Review)

| File | Stage | Document Type | Source Image |
|---|---|---|---|
| `passport_au_ocr_output.json` | P4 output → P5 input | Passport AU | `1.jpg` |
| `passport_au_mapped.json` | P5 output → P6/P7 input | Passport AU | `1.jpg` |
| `document_full_state.json` | P6 output → P7 review input; response of `GET /documents/{id}` | Passport AU | `1.jpg` |
| `medicare_ocr_output.json` | P4 output → P5 input | Medicare | `2.jpg` |
| `medicare_mapped.json` | P5 output → P6/P7 input | Medicare | `2.jpg` |
| `document_full_state_medicare.json` | P6 output → P7 review input; response of `GET /documents/{id}` | Medicare | `2.jpg` |
| `driver_licence_vic_ocr_output.json` | P4 output → P5 input | Driver Licence VIC | `3.jpg` |
| `driver_licence_vic_mapped.json` | P5 output → P6/P7 input | Driver Licence VIC | `3.jpg` |
| `document_full_state_driver_licence.json` | P6 output → P7 review input; response of `GET /documents/{id}` | Driver Licence VIC | `3.jpg` |
| `business_card_ocr_output.json` | P4 output → P5 input | Business Card | `business_card.jpg` |
| `business_card_mapped.json` | P5 output → P6/P7 input | Business Card | `business_card.jpg` |
| `document_full_state_business_card.json` | P6 output → P7 review input; response of `GET /documents/{id}` | Business Card | `business_card.jpg` |

### 2. Feature-specific Mock Files

- `auth_feature_mocks.json`: Mock payloads for Feature P1 (Authentication, Login, Register, OTP, Me, Beanie models).
- `intake_feature_mocks.json`: Mock payloads for Feature P2 (Upload, List, Beanie models).
- `preprocess_feature_mocks.json`: Mock Beanie documents and results for Feature P3 (Pre-processing).
- `review_feature_mocks.json`: Mock payloads for Feature P7 (Review PATCH edits, confirm dry-runs, finalized Beanie models).

---

## How Each Member Uses These Files

### P1 (Auth) — Authentication
- Use `auth_feature_mocks.json` as the reference for API requests/responses and Beanie database shapes (User, RefreshToken, OtpToken, LoginAttempt).

### P2 (Phúc Khang) — Intake & Validation
- Your inputs are the uploaded files (`1.jpg`, `2.jpg`, `3.jpg`, `business_card.jpg`).
- Refer to `intake_feature_mocks.json` for validation rules, response formats, and `UploadedImage` database document structures.

### P3 (Phú Phàm) — Pre-processing
- Use `preprocess_feature_mocks.json` to verify `PreprocessedImage` document properties (DPI, orientation, brightness/contrast adjustments, steps applied).

### P4 (Cường, Thiệt) — OCR + AI Vision
- Your outputs must match the structures of the `*_ocr_output.json` files for the respective document types. **This is the contract with P5.**

### P5 (Hui) — Business Field Mapping
- **Input**: `*_ocr_output.json` files.
- **Output**: `*_mapped.json` files. **This is the contract with P6.**
- Implement separate mappers for `passport_au`, `medicare`, `driver_licence_vic`, and `business_card`.

### P6 (Nhân Tài) — Confidence Scoring & Storage
- **Input**: `*_mapped.json` files.
- **Output**: Generates confidence scores, classifies fields, and appends history. Refer to `document_full_state*.json` for the overall response payload structure.

### P7 (Khanh) — JSON Review
- Use `document_full_state*.json` as the input for your review UI.
- Refer to `review_feature_mocks.json` for expected review PATCH payloads, dry-run responses, and FinalizedDocument Beanie models.

---

## Mock Conventions

- `processing_id` format: `PRC-YYYYMMDD-XXXXXX` (date + 6-char random base32).
- All timestamps are UTC ISO-8601 with `Z` suffix.
- `_id` fields are 24-character hex strings (MongoDB ObjectId).
- The sample images correspond to fixed `processing_id`s in these mocks:
  - `1.jpg` (passport) → `PRC-20260521-7H3K9F`
  - `2.jpg` (medicare) → `PRC-20260521-8K4L2M`
  - `3.jpg` (driver licence) → `PRC-20260521-9P5N3Q`
  - `business_card.jpg` (business card) → `PRC-20260521-5B2C3D`

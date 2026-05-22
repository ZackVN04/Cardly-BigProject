# OCR Document Processing System — API Endpoints

> **Stack**: FastAPI + Beanie (MongoDB) + JWT
> **Convention**: REST, JSON. All endpoints under prefix `/api/v1`.
> **Style reference**: https://github.com/zhanymkanov/fastapi-best-practices
> 🔒 = requires `Authorization: Bearer <access_token>` header.

---

## Design principles

- **User-facing only**: Endpoints expose actions a real client (mobile app, web) takes. Internal pipeline stages (preprocess → OCR → vision → mapping → confidence) are **functions called by a background worker**, not HTTP endpoints.
- **`processing_id` is the single resource key**: every endpoint that touches a document uses `processing_id` (format `PRC-YYYYMMDD-XXXXXX`).
- **Pipeline is async**: `POST /documents` returns immediately with `processing_id`; client polls `GET /documents/{id}` until `status: ready_for_review`.
- **One read endpoint, full state**: `GET /documents/{id}` returns everything the client needs (status + extracted_fields + confidence + validation), no need to call 4 different endpoints.

---

## 1. Auth (P1)

Owner: TBD — added at the end. Router: `app/auth/router.py` — prefix `/api/v1/auth`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Create a new user account. |
| `POST` | `/api/v1/auth/login` | Issue `access_token` + `refresh_token`. |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token, issue new access token. |
| `POST` | `/api/v1/auth/logout` 🔒 | Revoke current refresh token. |
| `GET`  | `/api/v1/auth/me` 🔒 | Return current authenticated user. |

### `POST /auth/register` — Request

```json
{
  "email": "hui@example.com",
  "password": "strong-password",
  "full_name": "Hui Nguyen"
}
```

### `POST /auth/register` — Response 201

```json
{
  "id": "665a1b2c3d4e5f6a7b8c9d0e",
  "email": "hui@example.com",
  "full_name": "Hui Nguyen",
  "role": "user",
  "created_at": "2026-05-21T10:00:00Z"
}
```

### `POST /auth/login` — Request

```json
{ "email": "hui@example.com", "password": "strong-password" }
```

### `POST /auth/login` — Response 200

```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### `POST /auth/refresh` — Request

```json
{ "refresh_token": "eyJhbGc..." }
```

### `POST /auth/refresh` — Response 200

Same shape as `/auth/login`. Old refresh token is revoked (rotation).

### `GET /auth/me` — Response 200

```json
{
  "id": "665a1b2c3d4e5f6a7b8c9d0e",
  "email": "hui@example.com",
  "full_name": "Hui Nguyen",
  "role": "user",
  "is_active": true
}
```

---

## 2. Documents (P2 → P6)

A `Document` is the user-facing aggregate covering upload, the entire scan pipeline, and the current state. Router: `app/documents/router.py` — prefix `/api/v1/documents`.

| Method | Path | Description |
|---|---|---|
| `POST`   | `/api/v1/documents` 🔒 | Upload image + trigger pipeline (async). Returns `processing_id`. |
| `GET`    | `/api/v1/documents` 🔒 | List the current user's documents (paginated, filter by status). |
| `GET`    | `/api/v1/documents/{processing_id}` 🔒 | Full state: status, extracted_fields, confidence, validation. Used for polling. |
| `GET`    | `/api/v1/documents/{processing_id}/image` 🔒 | Stream the original uploaded image. |
| `POST`   | `/api/v1/documents/{processing_id}/reprocess` 🔒 | Re-run the pipeline (e.g. after a transient failure). |
| `DELETE` | `/api/v1/documents/{processing_id}` 🔒 | Soft-delete the document (allowed only before `confirmed`). |

### `POST /documents` — Request

`multipart/form-data` with one field:
- `file` — JPG / PNG / WEBP / PDF, max 10 MB.

### `POST /documents` — Response 202 Accepted

```json
{
  "processing_id": "PRC-20260521-7H3K9F",
  "status": "received",
  "uploaded_at": "2026-05-21T10:14:22Z"
}
```

The pipeline (intake validation → preprocess → OCR → vision → mapping → confidence) runs asynchronously in a background worker. Client polls `GET /documents/{processing_id}` until `status` becomes `ready_for_review`.

### Document status lifecycle

```
received          → file accepted, queued
processing        → pipeline running (preprocess + OCR + vision + mapping)
ready_for_review  → user can view extracted fields & edit
confirmed         → finalized, immutable
failed            → pipeline failed; reprocess endpoint can retry
rejected          → intake validation failed (bad MIME, > 10 MB, duplicate, corrupted)
```

### `GET /documents/{processing_id}` — Response 200

```json
{
  "processing_id": "PRC-20260521-7H3K9F",
  "status": "ready_for_review",
  "doc_type": "passport_au",
  "doc_type_confidence": 0.97,
  "uploaded_at": "2026-05-21T10:14:22Z",
  "processed_at": "2026-05-21T10:14:31Z",

  "extracted_fields": {
    "document_no": "BN8038374",
    "surname": "PEREZ",
    "given_names": "LACHLAN",
    "nationality": "AUSTRALIAN",
    "date_of_birth": "2000-05-03",
    "sex": "M",
    "place_of_birth": "SYDNEY",
    "date_of_issue": "2024-10-01",
    "date_of_expiry": "2034-10-01",
    "authority": "LONDON"
  },

  "confidence": {
    "overall_score": 0.94,
    "classification": "low",
    "field_scores": [
      { "field_name": "document_no",     "score": 0.99, "classification": "high",   "auto_approved": true  },
      { "field_name": "surname",         "score": 0.98, "classification": "high",   "auto_approved": true  },
      { "field_name": "place_of_birth",  "score": 0.82, "classification": "low",    "auto_approved": false },
      { "field_name": "authority",       "score": 0.68, "classification": "failed", "auto_approved": false }
    ],
    "requires_manual_review": true
  },

  "validation": {
    "missing_required_fields": [],
    "validation_results": [
      { "field_name": "document_no",    "rule": "regex_passport_au", "passed": true },
      { "field_name": "date_of_expiry", "rule": "not_in_past",       "passed": true }
    ]
  }
}
```

### `GET /documents` — Response 200

```json
{
  "items": [
    {
      "processing_id": "PRC-20260521-7H3K9F",
      "doc_type": "passport_au",
      "status": "ready_for_review",
      "uploaded_at": "2026-05-21T10:14:22Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

Query params: `?status=ready_for_review&doc_type=passport_au&page=1&page_size=20`.

### `POST /documents/{processing_id}/reprocess` — Response 202

```json
{
  "processing_id": "PRC-20260521-7H3K9F",
  "status": "processing",
  "reprocess_count": 1
}
```

**Retry behavior**: each reprocess call appends new rows to `processing_history` (one per pipeline stage), never updates existing rows. This preserves the full audit trail. `reprocess_count` is derived at read time by counting `intake` stage rows in `processing_history`.

---

## 3. Review (P7)

Edit-and-confirm flow over a document that is `ready_for_review`. Router: `app/review/router.py` — prefix `/api/v1/documents/{processing_id}/review`.

| Method | Path | Description |
|---|---|---|
| `PATCH` | `/api/v1/documents/{processing_id}/review` 🔒 | Edit one or more extracted fields. Edits are logged for audit. |
| `POST`  | `/api/v1/documents/{processing_id}/confirm` 🔒 | Validate + finalize → produces immutable `FinalizedDocument`. Supports `?dry_run=true` to validate without finalizing. |
| `GET`   | `/api/v1/documents/{processing_id}/final` 🔒 | Get finalized JSON (only after `status: confirmed`). |

### `PATCH /documents/{processing_id}/review` — Request

```json
{
  "edits": [
    { "field_name": "place_of_birth", "new_value": "Sydney, NSW" },
    { "field_name": "authority",      "new_value": "Sydney"     }
  ]
}
```

### `PATCH /documents/{processing_id}/review` — Response 200

Returns the updated document in the same shape as `GET /documents/{processing_id}`, plus a re-run of validation against the edited values.

### `POST /documents/{processing_id}/confirm` — Response 200

```json
{
  "processing_id": "PRC-20260521-7H3K9F",
  "status": "confirmed",
  "finalized_at": "2026-05-21T10:22:11Z",
  "final_json": {
    "doc_type": "passport_au",
    "document_no": "BN8038374",
    "surname": "Perez",
    "given_names": "Lachlan",
    "...": "..."
  }
}
```

Confirm is **idempotent** — calling it twice on a `confirmed` document returns the existing `final_json` without re-creating the record.

**400 if required fields are missing or validation fails:**

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Cannot confirm — required fields missing or invalid",
    "details": {
      "missing_required_fields": ["date_of_expiry"],
      "failed_validations": [
        { "field_name": "document_no", "rule": "regex_passport_au", "passed": false }
      ]
    }
  }
}
```

### `POST /documents/{processing_id}/confirm?dry_run=true` — Response 200

Validate the current document state **without** finalizing it. Useful for the review UI (P7 US3 — "Validate Required Fields Before Confirmation") to show a green/red indicator before the user actually commits. Status is **not** changed; no `FinalizedDocument` is created.

```json
{
  "processing_id": "PRC-20260521-7H3K9F",
  "dry_run": true,
  "would_succeed": true,
  "missing_required_fields": [],
  "failed_validations": []
}
```

When validation would fail, response is still 200 (it's a query, not a state change) with `would_succeed: false` and the same `missing_required_fields` / `failed_validations` arrays as the 400 case above.

---

## 4. Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness probe. |
| `GET` | `/api/v1/health/db` | MongoDB readiness probe. |

---

## Endpoint count summary

| Group | Endpoints |
|---|---|
| Auth | 5 |
| Documents | 6 |
| Review | 3 |
| Health | 2 |
| **Total** | **16** |

(Down from 30+ in the previous draft. Internal pipeline stages are now functions, not HTTP routes.)

---

## Error envelope (all 4xx / 5xx)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "File exceeds 10 MB limit",
    "details": [{ "field": "file", "rule": "max_size_10mb" }]
  }
}
```

Common error codes: `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `VALIDATION_FAILED`, `DUPLICATE_FILE`, `INVALID_MIME`, `FILE_TOO_LARGE`, `PIPELINE_FAILED`, `INVALID_STATE` (e.g. confirming an already-confirmed document, editing a `processing` document).

---

## How team members map to endpoints

| Member | Task | Endpoints they own | Internal modules |
|---|---|---|---|
| TBD     | P1 Auth | `/auth/*`                          | `app/auth/`        |
| Phúc Khang | P2 Intake & Validation | `POST /documents` (upload + validate part) | `app/intake/`   |
| Phú Phàm | P3 Pre-processing | *(internal)*                       | `app/preprocess/`  |
| Cuong Ngo, Nguyễn Thanh Thiệt | P4 OCR + AI Vision | *(internal)*    | `app/ocr/`, `app/vision/` |
| **Hui** | P5 Business Field Mapping | *(internal)*           | `app/mapping/`     |
| Nhân Tài | P6 Confidence + Storage | `GET /documents`, `GET /documents/{id}`, history | `app/confidence/` |
| Khanh   | P7 JSON Review | `PATCH .../review`, `POST .../confirm`, `GET .../final` | `app/review/` |

P3, P4, P5 don't expose HTTP endpoints — they are pipeline steps called by the background worker. Their outputs surface to the client through `GET /documents/{processing_id}`.

---

## Pipeline orchestration (internal, for reference)

```
POST /documents (P2)
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│  Background worker (Celery / ARQ / FastAPI BG task)      │
│                                                          │
│  intake.validate()         ← P2                          │
│  preprocess.normalize()    ← P3                          │
│  ocr.extract()             ← P4                          │
│  vision.detect()           ← P4                          │
│  mapping.map_fields()      ← P5   ← Hui                  │
│  mapping.normalize_data()  ← P5                          │
│  mapping.validate_rules()  ← P5                          │
│  confidence.score()        ← P6                          │
│  history.log_stage()       ← P6 (called after each step) │
└─────────────────────────────────────────────────────────┘
  │
  ▼
status = ready_for_review
```

When pipeline finishes, `status` flips to `ready_for_review` and the client (which has been polling `GET /documents/{processing_id}`) renders the review UI.

---

## Branch & commit conventions

- `feature/auth-jwt-login`
- `feature/p5-passport-mapper`
- `feature/p5-normalize-dates`

Commit messages:
- `Add JWT access + refresh token issuance`
- `Implement passport field mapper for AU passport`
- `Normalize date_of_birth to ISO-8601`

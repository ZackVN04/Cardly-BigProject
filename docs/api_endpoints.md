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
- **One read endpoint, full state**: `GET /documents/{id}` returns everything the client needs (status + extracted_fields + confidence + validation + quality_check + metadata), no need to call 4 different endpoints.

---

## 1. Auth (P1)

Owner: TBD — added at the end. Router: `app/auth/router.py` — prefix `/api/v1/auth`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Create a new user account. |
| `POST` | `/api/v1/auth/login` | Issue `access_token` + `refresh_token` (Lockout after 5 failed attempts). |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token, issue new access token. |
| `POST` | `/api/v1/auth/logout` 🔒 | Revoke current refresh token. |
| `GET`  | `/api/v1/auth/me` 🔒 | Return current authenticated user. |
| `POST` | `/api/v1/auth/forgot-password` | Send 6-digit OTP to user email (valid for 5 minutes). |
| `POST` | `/api/v1/auth/verify-otp` | Verify 6-digit OTP code. |
| `POST` | `/api/v1/auth/reset-password` | Set new password with verified OTP token. |

---

## 2. Documents (P2 → P6)

A `Document` is the user-facing aggregate covering upload, the entire scan pipeline, and the current state. Router: `app/documents/router.py` — prefix `/api/v1/documents`.

| Method | Path | Description |
|---|---|---|
| `POST`   | `/api/v1/documents` 🔒 | Upload image(s) + trigger pipeline (async). Supports two-sided uploads. Returns `processing_id`. |
| `GET`    | `/api/v1/documents` 🔒 | List the current user's documents (paginated, filter by status). |
| `GET`    | `/api/v1/documents/{processing_id}` 🔒 | Full state: status, extracted_fields, confidence, validation, quality_check, and metadata. |
| `GET`    | `/api/v1/documents/{processing_id}/image` 🔒 | Stream the original uploaded image(s) (supports `?side=front` or `?side=back`). |
| `POST`   | `/api/v1/documents/{processing_id}/reprocess` 🔒 | Re-run the pipeline (e.g. after a transient failure). |
| `DELETE` | `/api/v1/documents/{processing_id}` 🔒 | Soft-delete the document (allowed only before `confirmed`). |

### `POST /documents` — Request

`multipart/form-data` with fields:
- `file` — JPG / PNG / WEBP / PDF, max 10 MB (front side).
- `back_file` — (Optional) JPG / PNG / WEBP / PDF, max 10 MB (back side, for two-sided cards).

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
  "doc_type": "business_card",
  "doc_type_confidence": 0.99,
  "uploaded_at": "2026-05-21T10:14:22Z",
  "processed_at": "2026-05-21T10:14:31Z",

  "quality_check": {
    "tilt": 0.02,
    "blur": 0.05,
    "brightness": 0.85,
    "passed": true
  },

  "extracted_fields": {
    "name": "NGUYEN VAN A",
    "phone": "+84 901 234 567",
    "email": "VAN.A@COMPANY.COM.VN",
    "web": "WWW.COMPANY.COM.VN",
    "position": "Giam Doc Cong Nghe",
    "company": "CONG TY TNHH CONG NGHE XYZ",
    "industry": null,
    "summary": null,
    "keywords": [],
    "highlights": []
  },

  "normalized_fields": {
    "name": "Nguyen Van A",
    "phone": "+84901234567",
    "email": "van.a@company.com.vn",
    "web": "https://www.company.com.vn",
    "position": "Giam Doc Cong Nghe",
    "company": "XYZ Technology Co., Ltd",
    "industry": "Technology",
    "summary": "Nguyen Van A is the Chief Technology Officer at XYZ Technology Co., Ltd, leading high-scale product development.",
    "keywords": ["CTO", "Software Architecture", "XYZ Technology"],
    "highlights": ["10+ years of tech leadership", "Spearheaded series A product launch"]
  },

  "confidence": {
    "overall_score": 0.97,
    "classification": "high",
    "field_scores": [
      { "field_name": "name",      "score": 0.98, "classification": "high",   "auto_approved": true  },
      { "field_name": "phone",     "score": 0.99, "classification": "high",   "auto_approved": true  },
      { "field_name": "email",     "score": 0.94, "classification": "low",    "auto_approved": false }
    ],
    "requires_manual_review": false
  },

  "validation": {
    "missing_required_fields": [],
    "validation_results": [
      { "field_name": "email", "rule": "email_format", "passed": true },
      { "field_name": "phone", "rule": "phone_format", "passed": true }
    ]
  },

  "context_metadata": {
    "event_name": null,
    "location": null,
    "meeting_date": null,
    "custom_tags": []
  }
}
```

### `GET /documents` — Response 200

```json
{
  "items": [
    {
      "processing_id": "PRC-20260521-7H3K9F",
      "doc_type": "business_card",
      "status": "ready_for_review",
      "uploaded_at": "2026-05-21T10:14:22Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

Query params: `?status=ready_for_review&page=1&page_size=20`.

---

## 3. Review (P7)

Edit-and-confirm flow over a document that is `ready_for_review`. Router: `app/review/router.py` — prefix `/api/v1/documents/{processing_id}/review`.

| Method | Path | Description |
|---|---|---|
| `PATCH` | `/api/v1/documents/{processing_id}/review` 🔒 | Edit fields or update smart tagging context. Edits are logged for audit. |
| `POST`  | `/api/v1/documents/{processing_id}/confirm` 🔒 | Validate + finalize → produces immutable `FinalizedDocument`. Supports `?dry_run=true`. |
| `GET`   | `/api/v1/documents/{processing_id}/final` 🔒 | Get finalized JSON (only after `status: confirmed`). |

### `PATCH /documents/{processing_id}/review` — Request

Allows editing both the extracted/normalized fields and the smart tagging context.

```json
{
  "edits": [
    { "field_name": "email", "new_value": "van.a@xyz.com.vn" }
  ],
  "context_metadata": {
    "event_name": "Vietnam Tech Summit 2026",
    "location": "GEM Center, HCMC",
    "meeting_date": "2026-05-26T12:00:00Z",
    "custom_tags": ["high-priority", "leads"]
  }
}
```

### `PATCH /documents/{processing_id}/review` — Response 200

Returns the updated document in the same shape as `GET /documents/{processing_id}`, with re-run validation against edited values.

### `POST /documents/{processing_id}/confirm` — Response 200

```json
{
  "processing_id": "PRC-20260521-7H3K9F",
  "status": "confirmed",
  "finalized_at": "2026-05-21T10:22:11Z",
  "final_json": {
    "name": "Nguyen Van A",
    "phone": "+84901234567",
    "email": "van.a@xyz.com.vn",
    "web": "https://www.company.com.vn",
    "position": "Giam Doc Cong Nghe",
    "company": "XYZ Technology Co., Ltd",
    "industry": "Technology",
    "summary": "Nguyen Van A is the Chief Technology Officer at XYZ Technology Co., Ltd, leading high-scale product development.",
    "keywords": ["CTO", "Software Architecture", "XYZ Technology"],
    "highlights": ["10+ years of tech leadership", "Spearheaded series A product launch"]
  },
  "context_metadata": {
    "event_name": "Vietnam Tech Summit 2026",
    "location": "GEM Center, HCMC",
    "meeting_date": "2026-05-26T12:00:00Z",
    "custom_tags": ["high-priority", "leads"]
  }
}
```

**400 if required fields are missing or validation fails:**

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Cannot confirm — required fields missing or invalid",
    "details": {
      "missing_required_fields": ["phone"],
      "failed_validations": [
        { "field_name": "email", "rule": "email_format", "passed": false }
      ]
    }
  }
}
```

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
| Auth | 8 |
| Documents | 6 |
| Review | 3 |
| Health | 2 |
| **Total** | **19** |

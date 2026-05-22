# OCR Document Processing — Backend

FastAPI + Beanie (MongoDB) + ARQ (Redis) + Pydantic v2

## Quick start

```bash
# 1. Clone & setup env
cp .env.example .env
# Edit .env — fill in GEMINI_API_KEY if you're on P4

# 2. Install dependencies
pip install -r requirements/dev.txt

# 3. Run dev server
uvicorn src.main:app --reload

# 4. Run tests
pytest
```

## Dev with Docker

```bash
docker compose -f docker/docker-compose.dev.yml up --build
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs (local/staging only)

## Project structure

```
src/
  auth/           P1 — Auth & JWT (TBD)
  intake/         P2 — Image Intake (Phúc Khang)
  preprocess/     P3 — Pre-processing (Phú Phàm)
  ocr/            P4 — OCR + AI Vision (Cường, Thiệt)
  mapping/        P5 — Field Mapping (Hui)
  confidence/     P6 — Confidence Scoring (Nhân Tài)
  review/         P7 — JSON Review (Khanh)
  pipeline/       Background orchestration
  common/         Shared utilities
tests/            Mirror of src/ — one test file per package
mock_data/        Source of truth for inter-package contracts
```

## Branch naming

`feature/<package>-<description>` — e.g. `feature/mapping-passport-mapper`

## Linting

```bash
ruff check src/ tests/
```

## API endpoints

See [docs/api_endpoints.md](docs/api_endpoints.md) or `/docs` when running locally.

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

graph TD
    %% Define styles
    classDef client fill:#f9f,stroke:#333,stroke-width:2px;
    classDef router fill:#bbf,stroke:#333,stroke-width:2px;
    classDef service fill:#bfb,stroke:#333,stroke-width:2px;
    classDef db fill:#ffb,stroke:#333,stroke-width:2px;
    classDef ext fill:#fbb,stroke:#333,stroke-width:2px;

    %% Client Layer
    Client["📱 Client App (Web / Mobile)"]:::client

    %% Core Application entry
    FastAPI["🚀 FastAPI Entry (src/main.py)"]:::router

    %% Modules / Domains
    subgraph auth ["🔐 Auth Module"]
        auth_router["router.py"]:::router
        auth_service["service.py"]:::service
        auth_models["models.py (User, OTP)"]:::db
    end

    subgraph intake ["📥 Intake Module"]
        intake_router["router.py"]:::router
        intake_service["service.py"]:::service
        intake_models["models.py (UploadedImage)"]:::db
    end

    subgraph preprocess ["⚙️ Preprocess Module"]
        prep_service["service.py (normalize, contrast)"]:::service
        prep_adapter["adapter.py"]:::service
        prep_utils["utils.py (cv2)"]:::service
    end

    subgraph ocr ["🔍 OCR Module"]
        ocr_router["router.py"]:::router
        ocr_service["service.py"]:::service
        ocr_clients["OCR Clients (Paddle, Gemini)"]:::ext
        ocr_models["models.py (BusinessCardScan)"]:::db
    end

    subgraph pipeline ["🔗 Pipeline Module"]
        ocr_pipeline["ocr_pipeline.py (Orchestrator)"]:::service
    end

    subgraph mapping ["🗺️ Field Mapping Module"]
        mapping_service["service.py (mapper)"]:::service
    end

    subgraph confidence ["📊 Confidence Module"]
        conf_router["router.py"]:::router
        conf_service["service.py"]:::service
    end

    subgraph review ["📝 Review Module"]
        review_router["router.py"]:::router
        review_service["service.py"]:::service
    end

    %% External & Shared Services
    MongoDB[("🗄️ Shared MongoDB (via Beanie)")]:::db
    GCS[("☁️ Google Cloud Storage (Blobs)")]:::ext

    %% Flow of requests
    Client -->|HTTP requests| FastAPI
    FastAPI --> auth_router
    FastAPI --> intake_router
    FastAPI --> ocr_router
    FastAPI --> conf_router
    FastAPI --> review_router

    %% Auth Layer interactions
    auth_router --> auth_service
    auth_service --> auth_models
    auth_models --> MongoDB

    %% Document Upload & Processing Orchestration Flow
    intake_router --> intake_service
    intake_service --> intake_models
    intake_models --> MongoDB
    intake_service -->|Upload raw files| GCS

    %% OCR Pipeline execution (Orchestrator)
    ocr_router --> ocr_pipeline
    ocr_pipeline -->|1. Fetch image records| MongoDB
    ocr_pipeline -->|2. Download blobs| GCS
    ocr_pipeline -->|3. Clean images| prep_adapter
    prep_adapter --> prep_service
    prep_service --> prep_utils
    ocr_pipeline -->|4. Detect text and map| ocr_service
    ocr_service --> ocr_clients
    ocr_service --> ocr_models
    ocr_models --> MongoDB
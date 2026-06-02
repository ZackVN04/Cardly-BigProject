FROM python:3.12-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# --- deps layer ---
FROM base AS deps
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir -r requirements/base.txt

# --- final ---
FROM deps AS final
COPY src/ src/
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
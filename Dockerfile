# Voice Travel Planner API — production image (Render, Railway, Fly, etc.)
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY scripts ./scripts

RUN pip install --no-cache-dir -e .

ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV CHROMA_PERSIST_DIR=/app/data/rag/index/chroma

EXPOSE 8000

CMD ["sh", "-c", "python scripts/ensure_chroma_index.py jaipur && uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

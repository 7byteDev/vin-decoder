# Build-Kontext ist das Repository-Wurzelverzeichnis (siehe docker-compose.yml)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN pip install --no-cache-dir \
        "fastapi>=0.115" "uvicorn[standard]>=0.30" "pydantic>=2.7" \
        "pydantic-settings>=2.3" "httpx>=0.27" "asyncpg>=0.29"

COPY backend/app /app/backend/app

RUN useradd --create-home --uid 10001 vindecoder
USER vindecoder

WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

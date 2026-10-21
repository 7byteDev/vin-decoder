# Build-Kontext ist das Repository-Wurzelverzeichnis (siehe docker-compose.yml)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# vininfo (BSD-3-Clause) liefert die herstellerspezifischen VDS-Regeln
# pydantic-settings wird von scripts/accuracy_report.py ueber app.config gebraucht
# Pillow verkleinert die geladenen Fotos, bevor sie in die Datenbank gehen
RUN pip install --no-cache-dir     "asyncpg>=0.29" "httpx>=0.27" "vininfo>=1.11"     "pydantic>=2.7" "pydantic-settings>=2.3" "pillow>=10.3"

COPY db /app/db
COPY etl /app/etl
COPY backend/app /app/backend/app
# Testset und Genauigkeitsmessung mitliefern (Phase 4)
COPY qa /app/qa
COPY scripts /app/scripts

RUN useradd --create-home --uid 10002 vinetl \
    && mkdir -p /app/etl/data/raw \
    && chown -R vinetl /app/etl/data
USER vinetl

CMD ["python", "-m", "etl.run_import", "status"]

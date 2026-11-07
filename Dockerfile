# Multi-stage production container for Since AI Backend
# Target Hosting: Google Cloud Run (europe-north1 / Hamina, Finland)

FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


FROM python:3.12-slim AS runner

WORKDIR /app

# Install minimal runtime libraries for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GCP_REGION=europe-north1

# Copy application source code and reference data
COPY src/ /app/src/
COPY data/reference/ /app/data/reference/

# Create non-root system user for security hardening
RUN useradd -u 1001 -m sinceai && chown -R sinceai:sinceai /app
USER sinceai

EXPOSE 8080

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

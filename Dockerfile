# Multi-stage production container for Since AI Backend
# Target Hosting: Google Cloud Run (europe-north1 / Hamina, Finland)

FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runner

WORKDIR /app

# Install minimal runtime libraries for PostgreSQL and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed virtualenv from builder with global read/exec permissions
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GCP_REGION=europe-north1

# Copy application source code, reference data, and web assets
COPY src/ /app/src/
COPY dsakit/ /app/dsakit/
COPY data/reference/ /app/data/reference/
COPY frontend/ /app/frontend/
COPY demo.html /app/demo.html
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create non-root system user for security hardening
RUN useradd -u 1001 -m sinceai && chown -R sinceai:sinceai /app /opt/venv
USER sinceai

EXPOSE 8080

ENTRYPOINT ["/app/docker-entrypoint.sh"]

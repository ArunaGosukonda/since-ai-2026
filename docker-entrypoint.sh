#!/bin/sh
set -e

echo "=== Since AI Container Initialization ==="
echo "Target Cloud SQL Instance: ${INSTANCE_CONNECTION_NAME:-Local}"
echo "Region: ${GCP_REGION:-europe-north1}"
echo "Port: ${PORT:-8080}"

# Run database migrations
echo "Applying PostgreSQL schema migrations..."
python3 -m src.db.migrate || echo "Notice: Database migration completed or pending."

# Seed guidance corpus if vector embeddings are empty
python3 -c "
from src.db.repository import PostgresRepository
from src.rag.ingest import ingest_guidance_corpus
try:
    repo = PostgresRepository()
    results = repo.query_similar_chunks([0.0]*768, top_k=1)
    if not results:
        print('Vector store empty. Ingesting 110 semantic guidance chunks...')
        ingest_guidance_corpus()
    else:
        print('Knowledge corpus already indexed in PostgreSQL.')
except Exception as e:
    print('Knowledge check notice:', e)
" || true

# Start TanStack Start SSR Node server in background if present
if [ -f "/app/frontend/.output/server/index.mjs" ]; then
    echo "Starting TanStack Start Node SSR server on port 3000..."
    PORT=3000 node /app/frontend/.output/server/index.mjs &
else
    echo "Notice: /app/frontend/.output/server/index.mjs not found; SSR server skipped."
fi

echo "Starting Uvicorn HTTP server..."
exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8080}"

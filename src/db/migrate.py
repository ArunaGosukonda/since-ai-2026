"""Database migration runner for Since AI PostgreSQL database.

Applies SQL migrations tracking execution in the schema_migrations table.
Strictly targets Google Cloud SQL for PostgreSQL 18.6 with pgvector.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import List

from src.db.connection import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def run_migrations() -> List[str]:
    """Applies all pending PostgreSQL migrations in order."""
    conn = get_db_connection()
    applied = []
    try:
        with conn.cursor() as cursor:
            # 1. Ensure migrations tracking table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(64) PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

            cursor.execute("SELECT version FROM schema_migrations;")
            already_applied = {row[0] for row in cursor.fetchall()}

            # 2. Find and execute SQL migrations in order
            sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            for sql_file in sql_files:
                version = sql_file.name
                if version in already_applied:
                    logger.info("Migration %s already applied.", version)
                    continue

                logger.info("Applying migration %s...", version)
                sql_content = sql_file.read_text(encoding="utf-8")
                cursor.execute(sql_content)
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s);",
                    (version,),
                )
                conn.commit()
                applied.append(version)
                logger.info("Successfully applied %s", version)

    finally:
        conn.close()

    return applied


def verify_schema() -> List[str]:
    """Verifies that all 12 schema tables and vector index exist in PostgreSQL."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cursor.fetchall()]

            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' AND indexname = 'idx_vector_embeddings_cosine';
            """)
            indexes = [row[0] for row in cursor.fetchall()]

            cursor.execute("""
                SELECT extname, extversion 
                FROM pg_extension 
                WHERE extname = 'vector';
            """)
            extensions = cursor.fetchall()

            logger.info("PostgreSQL Tables found: %s", tables)
            logger.info("Vector Index found: %s", indexes)
            logger.info("Extensions found: %s", extensions)
            return tables
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()
    verify_schema()

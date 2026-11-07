"""Database connection manager for Since AI.

Supports:
1. Google Cloud SQL for PostgreSQL 16 with pgvector (europe-north1)
2. Local Docker PostgreSQL 16 + pgvector (localhost:5432)
3. Hermetic local SQLite fallback for air-gapped unit/integration testing
"""

import os
import sqlite3
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Configurable environment settings
DATABASE_URL = os.getenv("DATABASE_URL")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "sinceai")
POSTGRES_USER = os.getenv("POSTGRES_USER", "sinceai_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "sinceai_local_secret")
SQLITE_FALLBACK_PATH = os.getenv("SQLITE_PATH", "data/assistant_sessions.db")


class DatabaseConnectionManager:
    """Manages connections to PostgreSQL or SQLite fallback."""

    def __init__(self):
        self._prefer_postgres = bool(DATABASE_URL or os.getenv("POSTGRES_HOST"))
        self._active_backend = None

    def get_connection(self) -> Any:
        """Returns an active database connection."""
        if self._prefer_postgres:
            try:
                import psycopg
                conn_str = DATABASE_URL or (
                    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
                    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
                )
                conn = psycopg.connect(conn_str)
                self._active_backend = "postgresql"
                return conn
            except Exception as e:
                logger.warning(
                    "PostgreSQL connection failed (%s). Falling back to local SQLite repository.",
                    e,
                )

        # Fallback to SQLite
        self._active_backend = "sqlite"
        os.makedirs(os.path.dirname(os.path.abspath(SQLITE_FALLBACK_PATH)), exist_ok=True)
        conn = sqlite3.connect(SQLITE_FALLBACK_PATH)
        conn.row_factory = sqlite3.Row
        self._ensure_sqlite_tables(conn)
        return conn

    @property
    def active_backend(self) -> str:
        return self._active_backend or "uninitialized"

    def _ensure_sqlite_tables(self, conn: sqlite3.Connection) -> None:
        """Ensures the 12 tables exist in SQLite fallback mode."""
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                locale TEXT NOT NULL DEFAULT 'fi',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ended_at TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                channel TEXT NOT NULL DEFAULT 'web'
            );
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                turn_index INT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                language TEXT DEFAULT 'fi',
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS case_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL UNIQUE,
                threat_category TEXT,
                confirmed_facts TEXT NOT NULL DEFAULT '{}',
                unresolved_questions TEXT NOT NULL DEFAULT '[]',
                decisive_topic TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS security_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                risk_level TEXT NOT NULL,
                urgency TEXT NOT NULL,
                action_type TEXT NOT NULL,
                requires_specialist INT NOT NULL DEFAULT 0,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS knowledge_docs (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                url TEXT,
                language TEXT NOT NULL DEFAULT 'fi',
                topic TEXT NOT NULL,
                audience TEXT NOT NULL DEFAULT 'consumer',
                content_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS semantic_chunks (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                chunk_index INT NOT NULL,
                section_header TEXT,
                chunk_text TEXT NOT NULL,
                token_count INT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS vector_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id TEXT NOT NULL UNIQUE,
                embedding TEXT NOT NULL,
                model_id TEXT NOT NULL,
                dimension INT NOT NULL DEFAULT 768,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS retrieval_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                turn_index INT,
                contextual_query_redacted TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_version TEXT,
                retrieved_doc_ids TEXT NOT NULL,
                similarity_scores TEXT NOT NULL,
                metadata_filters TEXT DEFAULT '{}',
                latency_ms REAL NOT NULL,
                evaluation_outcome TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS consent_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                conversation_id TEXT,
                telemetry_granted INT NOT NULL DEFAULT 0,
                processing_purpose TEXT NOT NULL DEFAULT 'incident_resolution',
                granted_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS decision_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                turn_index INT NOT NULL,
                action TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                urgency TEXT NOT NULL,
                requires_specialist INT NOT NULL DEFAULT 0,
                escalation_target TEXT,
                twin_decisive_question TEXT,
                rationale TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS security_audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()


_manager = DatabaseConnectionManager()


def get_db_connection() -> Any:
    return _manager.get_connection()


def get_active_backend() -> str:
    return _manager.active_backend

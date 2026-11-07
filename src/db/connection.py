"""Database connection manager for Since AI.

Strict PostgreSQL-Only Architecture:
- Google Cloud SQL for PostgreSQL 18.6 with pgvector in europe-north1 (Hamina, Finland)
- In Cloud Run: Connects securely via native Cloud SQL Unix socket /cloudsql/<INSTANCE_CONNECTION_NAME>
- In Local Development: Connects via Cloud SQL Auth Proxy on 127.0.0.1:5433
- PostgreSQL is the ONLY application database.
- Zero SQLite fallback. Fail fast on connection failure with DatabaseConnectionError.
"""

from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment configuration from .env if present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(Path.home() / ".env")

# Cloud SQL PostgreSQL Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "since_ai")
POSTGRES_USER = os.getenv("POSTGRES_USER", "since_ai_app")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
DATABASE_URL = os.getenv("DATABASE_URL")
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")


class DatabaseConnectionError(RuntimeError):
    """Raised when connection to the mandatory PostgreSQL database fails."""
    pass


class DatabaseConnectionManager:
    """Manages connections strictly to PostgreSQL + pgvector.
    
    Zero SQLite fallback. Fails fast with DatabaseConnectionError if PostgreSQL is unreachable.
    """

    def __init__(self):
        self._active_backend = "postgresql"

    def get_connection(self) -> Any:
        """Returns an active PostgreSQL connection with pgvector registered.
        
        Raises DatabaseConnectionError if connection cannot be established.
        """
        try:
            import psycopg
            from pgvector.psycopg import register_vector

            if DATABASE_URL:
                conn = psycopg.connect(DATABASE_URL)
            elif INSTANCE_CONNECTION_NAME:
                # Native Cloud Run connection via Cloud SQL Unix socket
                socket_dir = f"/cloudsql/{INSTANCE_CONNECTION_NAME}"
                conn = psycopg.connect(
                    host=socket_dir,
                    dbname=POSTGRES_DB,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                )
            else:
                # Standard TCP connection (Local Proxy or Docker)
                conn = psycopg.connect(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    dbname=POSTGRES_DB,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                )

            register_vector(conn)
            self._active_backend = "postgresql"
            return conn
        except Exception as e:
            target = f"Unix socket /cloudsql/{INSTANCE_CONNECTION_NAME}" if INSTANCE_CONNECTION_NAME else f"{POSTGRES_HOST}:{POSTGRES_PORT}"
            err_msg = (
                f"Failed to connect to Google Cloud SQL PostgreSQL ({target}/{POSTGRES_DB}): {e}. "
                "PostgreSQL is the only authorized database engine for Since AI. Zero SQLite fallback allowed."
            )
            logger.error(err_msg)
            raise DatabaseConnectionError(err_msg) from e

    @property
    def active_backend(self) -> str:
        return self._active_backend


_manager = DatabaseConnectionManager()


def get_db_connection() -> Any:
    return _manager.get_connection()


def get_active_backend() -> str:
    return _manager.active_backend

# -*- coding: utf-8 -*-
"""Session Database for Since AI — DNA Digital Security Assistant.

Uses Python standard library SQLite3 for zero-setup, ACID-compliant local persistence
of multi-turn chat sessions, user-revealed facts, and security decisions.
"""
import datetime
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
DB_PATH = os.path.join(ROOT, "data/assistant_sessions.db")


def _get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH):
    """Initializes the SQLite schema if not already present."""
    with _get_connection(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            journey TEXT,
            audience TEXT,
            language TEXT,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            msg_type TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS facts (
            session_id TEXT,
            key TEXT,
            value TEXT,
            PRIMARY KEY (session_id, key),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS decisions (
            session_id TEXT PRIMARY KEY,
            primary_action TEXT,
            risk_level TEXT,
            urgency TEXT,
            escalation_required INTEGER,
            escalation_target TEXT,
            steps_json TEXT,
            citations_json TEXT,
            signals_json TEXT,
            advice_text TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
        """)


def create_or_update_session(
    session_id: str,
    journey: str = "suspicious_message",
    audience: str = "consumer",
    language: str = "fi",
    status: str = "active",
    db_path: str = DB_PATH
):
    with _get_connection(db_path) as conn:
        conn.execute("""
        INSERT INTO sessions (session_id, journey, audience, language, status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            journey = excluded.journey,
            status = excluded.status
        """, (session_id, journey, audience, language, status))


def add_message(session_id: str, role: str, msg_type: str, content: str, db_path: str = DB_PATH):
    with _get_connection(db_path) as conn:
        conn.execute("""
        INSERT INTO messages (session_id, role, msg_type, content)
        VALUES (?, ?, ?, ?)
        """, (session_id, role, msg_type, content))


def get_messages(session_id: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with _get_connection(db_path) as conn:
        rows = conn.execute("""
        SELECT role, msg_type, content, timestamp
        FROM messages
        WHERE session_id = ?
        ORDER BY id ASC
        """, (session_id,)).fetchall()
        return [dict(r) for r in rows]


def set_fact(session_id: str, key: str, value: str, db_path: str = DB_PATH):
    with _get_connection(db_path) as conn:
        conn.execute("""
        INSERT INTO facts (session_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(session_id, key) DO UPDATE SET value = excluded.value
        """, (session_id, key, value))


def get_facts(session_id: str, db_path: str = DB_PATH) -> Dict[str, str]:
    with _get_connection(db_path) as conn:
        rows = conn.execute("""
        SELECT key, value FROM facts WHERE session_id = ?
        """, (session_id,)).fetchall()
        return {r["key"]: r["value"] for r in rows}


def save_decision(session_id: str, dec: Dict[str, Any], db_path: str = DB_PATH):
    with _get_connection(db_path) as conn:
        conn.execute("""
        INSERT INTO decisions (
            session_id, primary_action, risk_level, urgency,
            escalation_required, escalation_target, steps_json,
            citations_json, signals_json, advice_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            primary_action = excluded.primary_action,
            risk_level = excluded.risk_level,
            urgency = excluded.urgency,
            escalation_required = excluded.escalation_required,
            escalation_target = excluded.escalation_target,
            steps_json = excluded.steps_json,
            citations_json = excluded.citations_json,
            signals_json = excluded.signals_json,
            advice_text = excluded.advice_text
        """, (
            session_id,
            dec.get("primary_action", ""),
            dec.get("risk_level", "medium"),
            dec.get("urgency", "routine"),
            1 if dec.get("escalation_required") else 0,
            dec.get("escalation_target"),
            json.dumps(dec.get("steps", []), ensure_ascii=False),
            json.dumps(dec.get("citations", []), ensure_ascii=False),
            json.dumps(dec.get("signals_used", []), ensure_ascii=False),
            dec.get("advice_text", "")
        ))


def get_decision(session_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    with _get_connection(db_path) as conn:
        row = conn.execute("""
        SELECT * FROM decisions WHERE session_id = ?
        """, (session_id,)).fetchone()
        if not row:
            return None
        return {
            "primary_action": row["primary_action"],
            "risk_level": row["risk_level"],
            "urgency": row["urgency"],
            "escalation_required": bool(row["escalation_required"]),
            "escalation_target": row["escalation_target"],
            "steps": json.loads(row["steps_json"]),
            "citations": json.loads(row["citations_json"]),
            "signals_used": json.loads(row["signals_json"]),
            "advice_text": row["advice_text"]
        }


# Initialize DB immediately on load
init_db()

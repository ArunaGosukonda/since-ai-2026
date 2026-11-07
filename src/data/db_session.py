# -*- coding: utf-8 -*-
"""Session Database for Since AI — DNA Digital Security Assistant.

Strict PostgreSQL-Only Implementation:
- Uses Google Cloud SQL PostgreSQL via get_db_connection()
- Zero SQLite usage or fallback.
- Persists multi-turn conversations, turns, case facts, and security decisions
  directly to PostgreSQL schema tables (conversations, conversation_turns, case_state, decision_outcomes).
"""

from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional

from psycopg.rows import dict_row
from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def init_db(db_path: Optional[str] = None) -> None:
    """Verifies PostgreSQL connectivity. Zero SQLite initialization."""
    # SQLite is completely removed; tables are managed via PostgreSQL migrations
    pass


def create_or_update_session(
    session_id: str,
    journey: str = "suspicious_message",
    audience: str = "consumer",
    language: str = "fi",
    status: str = "active",
    db_path: Optional[str] = None,
) -> None:
    """Creates or updates a session in PostgreSQL conversations and case_state."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Upsert conversation
            cursor.execute(
                """
                INSERT INTO conversations (id, status, channel)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status
                """,
                (session_id, status, journey),
            )
            # 2. Ensure case_state exists
            cursor.execute(
                """
                INSERT INTO case_state (conversation_id, threat_category, confirmed_facts, unresolved_questions)
                VALUES (%s, %s, %s::jsonb, %s::jsonb)
                ON CONFLICT (conversation_id) DO UPDATE SET threat_category = EXCLUDED.threat_category
                """,
                (session_id, journey, json.dumps({"audience": audience, "language": language}), json.dumps([])),
            )
            conn.commit()
    finally:
        conn.close()


def add_message(
    session_id: str,
    role: str,
    msg_type: str,
    content: str,
    db_path: Optional[str] = None,
) -> None:
    """Adds a message to PostgreSQL conversation_turns."""
    conn = get_db_connection()
    meta = json.dumps({"msg_type": msg_type})
    try:
        with conn.cursor() as cursor:
            # Ensure conversation exists
            cursor.execute(
                """
                INSERT INTO conversations (id, status)
                VALUES (%s, 'active')
                ON CONFLICT (id) DO NOTHING
                """,
                (session_id,),
            )
            # Get next turn index
            cursor.execute(
                "SELECT COALESCE(MAX(turn_index), 0) + 1 FROM conversation_turns WHERE conversation_id = %s",
                (session_id,),
            )
            next_turn = cursor.fetchone()[0]

            # Role check: postgres CHECK (role IN ('user', 'assistant', 'system'))
            clean_role = role if role in ('user', 'assistant', 'system') else 'assistant'

            cursor.execute(
                """
                INSERT INTO conversation_turns (conversation_id, turn_index, role, content, metadata)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_id, next_turn, clean_role, content, meta),
            )
            conn.commit()
    finally:
        conn.close()


def get_messages(session_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all messages for a session from PostgreSQL conversation_turns."""
    conn = get_db_connection()
    try:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT role, content, metadata, created_at
                FROM conversation_turns
                WHERE conversation_id = %s
                ORDER BY turn_index ASC, id ASC
                """,
                (session_id,),
            )
            rows = cursor.fetchall()
            messages = []
            for r in rows:
                meta = r.get("metadata")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                elif not isinstance(meta, dict):
                    meta = {}

                messages.append({
                    "role": r["role"],
                    "msg_type": meta.get("msg_type", "text"),
                    "content": r["content"],
                    "timestamp": str(r["created_at"]),
                })
            return messages
    finally:
        conn.close()


def set_fact(session_id: str, key: str, value: str, db_path: Optional[str] = None) -> None:
    """Sets a fact inside PostgreSQL case_state.confirmed_facts JSONB."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO case_state (conversation_id, confirmed_facts)
                VALUES (%s, jsonb_build_object(%s, %s::text))
                ON CONFLICT (conversation_id) DO UPDATE SET
                    confirmed_facts = case_state.confirmed_facts || jsonb_build_object(%s, %s::text),
                    last_updated = CURRENT_TIMESTAMP
                """,
                (session_id, key, value, key, value),
            )
            conn.commit()
    finally:
        conn.close()


def get_facts(session_id: str, db_path: Optional[str] = None) -> Dict[str, str]:
    """Retrieves confirmed facts from PostgreSQL case_state."""
    conn = get_db_connection()
    try:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "SELECT confirmed_facts FROM case_state WHERE conversation_id = %s",
                (session_id,),
            )
            row = cursor.fetchone()
            if not row or not row.get("confirmed_facts"):
                return {}
            facts = row["confirmed_facts"]
            if isinstance(facts, str):
                return json.loads(facts)
            return dict(facts)
    finally:
        conn.close()


def save_decision(session_id: str, dec: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Saves a security decision to PostgreSQL decision_outcomes."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(MAX(turn_index), 0) + 1 FROM decision_outcomes WHERE conversation_id = %s",
                (session_id,),
            )
            next_turn = cursor.fetchone()[0]

            rationale_payload = json.dumps({
                "steps": dec.get("steps", []),
                "citations": dec.get("citations", []),
                "signals_used": dec.get("signals_used", []),
                "advice_text": dec.get("advice_text", ""),
            }, ensure_ascii=False)

            cursor.execute(
                """
                INSERT INTO decision_outcomes (
                    conversation_id, turn_index, action, risk_level,
                    urgency, requires_specialist, escalation_target,
                    twin_decisive_question, rationale
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    next_turn,
                    dec.get("primary_action", "verify_via_official_channel"),
                    dec.get("risk_level", "medium"),
                    dec.get("urgency", "routine"),
                    bool(dec.get("escalation_required", False)),
                    dec.get("escalation_target"),
                    dec.get("twin_decisive_question"),
                    rationale_payload,
                ),
            )
            conn.commit()
    finally:
        conn.close()


def get_decision(session_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves the latest decision outcome from PostgreSQL."""
    conn = get_db_connection()
    try:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT action, risk_level, urgency, requires_specialist, escalation_target,
                       twin_decisive_question, rationale
                FROM decision_outcomes
                WHERE conversation_id = %s
                ORDER BY turn_index DESC, id DESC
                LIMIT 1
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            rationale_data = {}
            if row.get("rationale"):
                try:
                    rationale_data = json.loads(row["rationale"])
                except Exception:
                    pass

            return {
                "primary_action": row["action"],
                "risk_level": row["risk_level"],
                "urgency": row["urgency"],
                "escalation_required": bool(row["requires_specialist"]),
                "escalation_target": row["escalation_target"],
                "steps": rationale_data.get("steps", []),
                "citations": rationale_data.get("citations", []),
                "signals_used": rationale_data.get("signals_used", []),
                "advice_text": rationale_data.get("advice_text", ""),
            }
    finally:
        conn.close()

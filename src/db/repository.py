"""Type-safe repository for Since AI data operations.

Interfaces with the 12 schema tables in PostgreSQL/pgvector or fallback SQLite.
"""

from __future__ import annotations
import json
import math
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class PostgresRepository:
    """Repository implementation handling session, vector, and audit persistence."""

    def __init__(self):
        pass

    def create_or_get_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Check if exists
            cursor.execute("SELECT id, user_id, status FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()
            if row:
                return dict(row) if hasattr(row, "keys") else {"id": row[0], "user_id": row[1], "status": row[2]}

            cursor.execute(
                "INSERT INTO conversations (id, user_id, status) VALUES (?, ?, 'active')",
                (conversation_id, user_id),
            )
            conn.commit()
            return {"id": conversation_id, "user_id": user_id, "status": "active"}
        finally:
            conn.close()

    def add_turn(
        self,
        conversation_id: str,
        turn_index: int,
        role: str,
        content: str,
        language: str = "fi",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.create_or_get_conversation(conversation_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        meta_str = json.dumps(metadata or {})
        try:
            cursor.execute(
                """
                INSERT INTO conversation_turns (conversation_id, turn_index, role, content, language, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, turn_index, role, content, language, meta_str),
            )
            conn.commit()
        finally:
            conn.close()

    def get_conversation_turns(self, conversation_id: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT turn_index, role, content, language, metadata, created_at
                FROM conversation_turns
                WHERE conversation_id = ?
                ORDER BY turn_index ASC, id ASC
                """,
                (conversation_id,),
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                if hasattr(r, "keys"):
                    results.append(dict(r))
                else:
                    results.append({
                        "turn_index": r[0],
                        "role": r[1],
                        "content": r[2],
                        "language": r[3],
                        "metadata": json.loads(r[4]) if isinstance(r[4], str) else r[4],
                        "created_at": r[5],
                    })
            return results
        finally:
            conn.close()

    def save_case_state(
        self,
        conversation_id: str,
        threat_category: Optional[str],
        confirmed_facts: Dict[str, Any],
        unresolved_questions: List[str],
        decisive_topic: Optional[str] = None,
    ) -> None:
        self.create_or_get_conversation(conversation_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        facts_json = json.dumps(confirmed_facts)
        questions_json = json.dumps(unresolved_questions)
        try:
            cursor.execute(
                """
                INSERT INTO case_state (conversation_id, threat_category, confirmed_facts, unresolved_questions, decisive_topic, last_updated)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    threat_category = excluded.threat_category,
                    confirmed_facts = excluded.confirmed_facts,
                    unresolved_questions = excluded.unresolved_questions,
                    decisive_topic = excluded.decisive_topic,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (conversation_id, threat_category, facts_json, questions_json, decisive_topic),
            )
            conn.commit()
        finally:
            conn.close()

    def get_case_state(self, conversation_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT threat_category, confirmed_facts, unresolved_questions, decisive_topic FROM case_state WHERE conversation_id = ?",
                (conversation_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "threat_category": None,
                    "confirmed_facts": {},
                    "unresolved_questions": [],
                    "decisive_topic": None,
                }
            if hasattr(row, "keys"):
                d = dict(row)
                d["confirmed_facts"] = json.loads(d["confirmed_facts"]) if isinstance(d["confirmed_facts"], str) else d["confirmed_facts"]
                d["unresolved_questions"] = json.loads(d["unresolved_questions"]) if isinstance(d["unresolved_questions"], str) else d["unresolved_questions"]
                return d
            return {
                "threat_category": row[0],
                "confirmed_facts": json.loads(row[1]) if isinstance(row[1], str) else row[1],
                "unresolved_questions": json.loads(row[2]) if isinstance(row[2], str) else row[2],
                "decisive_topic": row[3],
            }
        finally:
            conn.close()

    def save_knowledge_chunk_with_embedding(
        self,
        doc_id: str,
        title: str,
        url: str,
        language: str,
        topic: str,
        audience: str,
        chunk_id: str,
        chunk_index: int,
        section_header: str,
        chunk_text: str,
        embedding: List[float],
        model_id: str,
    ) -> None:
        conn = get_db_connection()
        cursor = conn.cursor()
        emb_json = json.dumps(embedding)
        try:
            # Insert or replace doc
            cursor.execute(
                """
                INSERT OR IGNORE INTO knowledge_docs (id, doc_id, title, url, language, topic, audience)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (doc_id, doc_id, title, url, language, topic, audience),
            )
            # Insert or replace chunk
            cursor.execute(
                """
                INSERT OR REPLACE INTO semantic_chunks (id, doc_id, chunk_index, section_header, chunk_text, token_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chunk_id, doc_id, chunk_index, section_header, chunk_text, len(chunk_text.split())),
            )
            # Insert or replace embedding
            cursor.execute(
                """
                INSERT OR REPLACE INTO vector_embeddings (chunk_id, embedding, model_id, dimension)
                VALUES (?, ?, ?, ?)
                """,
                (chunk_id, emb_json, model_id, len(embedding)),
            )
            conn.commit()
        finally:
            conn.close()

    def query_similar_chunks(
        self,
        query_embedding: List[float],
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Queries stored semantic chunks by cosine distance against query_embedding."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    c.id AS chunk_id,
                    c.doc_id,
                    c.chunk_text,
                    c.section_header,
                    d.title,
                    d.url,
                    d.language,
                    d.topic,
                    v.embedding
                FROM semantic_chunks c
                JOIN knowledge_docs d ON c.doc_id = d.doc_id
                JOIN vector_embeddings v ON c.id = v.chunk_id
            """)
            rows = cursor.fetchall()
            scored: List[Tuple[float, Dict[str, Any]]] = []
            for r in rows:
                if hasattr(r, "keys"):
                    d = dict(r)
                else:
                    d = {
                        "chunk_id": r[0],
                        "doc_id": r[1],
                        "chunk_text": r[2],
                        "section_header": r[3],
                        "title": r[4],
                        "url": r[5],
                        "language": r[6],
                        "topic": r[7],
                        "embedding": r[8],
                    }

                # Apply metadata filter if specified
                if filters:
                    match = True
                    for k, v in filters.items():
                        if d.get(k) != v:
                            match = False
                            break
                    if not match:
                        continue

                target_emb = json.loads(d["embedding"]) if isinstance(d["embedding"], str) else d["embedding"]
                sim = _cosine_similarity(query_embedding, target_emb)
                d["similarity_score"] = sim
                scored.append((sim, d))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [item[1] for item in scored[:top_k]]
        finally:
            conn.close()

    def log_retrieval_audit(
        self,
        conversation_id: Optional[str],
        turn_index: Optional[int],
        query_redacted: str,
        embedding_model: str,
        embedding_version: str,
        retrieved_doc_ids: List[str],
        similarity_scores: List[float],
        metadata_filters: Dict[str, Any],
        latency_ms: float,
        evaluation_outcome: str,
    ) -> None:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO retrieval_audit (
                    conversation_id, turn_index, contextual_query_redacted,
                    embedding_model, embedding_version, retrieved_doc_ids,
                    similarity_scores, metadata_filters, latency_ms, evaluation_outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    turn_index,
                    query_redacted,
                    embedding_model,
                    embedding_version,
                    json.dumps(retrieved_doc_ids),
                    json.dumps([round(s, 4) for s in similarity_scores]),
                    json.dumps(metadata_filters or {}),
                    latency_ms,
                    evaluation_outcome,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def record_decision_outcome(
        self,
        conversation_id: str,
        turn_index: int,
        action: str,
        risk_level: str,
        urgency: str,
        requires_specialist: bool = False,
        escalation_target: Optional[str] = None,
        twin_decisive_question: Optional[str] = None,
        rationale: str = "",
    ) -> None:
        self.create_or_get_conversation(conversation_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO decision_outcomes (
                    conversation_id, turn_index, action, risk_level,
                    urgency, requires_specialist, escalation_target,
                    twin_decisive_question, rationale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    turn_index,
                    action,
                    risk_level,
                    urgency,
                    1 if requires_specialist else 0,
                    escalation_target,
                    twin_decisive_question,
                    rationale,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def record_consent(
        self,
        user_id: str,
        conversation_id: str,
        telemetry_granted: bool,
        purpose: str = "incident_resolution",
    ) -> None:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO consent_records (user_id, conversation_id, telemetry_granted, processing_purpose)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, conversation_id, 1 if telemetry_granted else 0, purpose),
            )
            conn.commit()
        finally:
            conn.close()

    def record_security_audit_event(
        self,
        conversation_id: Optional[str],
        event_type: str,
        severity: str,
        payload: Dict[str, Any],
    ) -> None:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO security_audit_events (conversation_id, event_type, severity, payload)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, event_type, severity, json.dumps(payload)),
            )
            conn.commit()
        finally:
            conn.close()

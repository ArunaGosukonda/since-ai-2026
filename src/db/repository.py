"""Type-safe repository for Since AI data operations.

Interfaces strictly with Google Cloud SQL for PostgreSQL 18.6 with pgvector.
Zero SQLite fallback. Native pgvector cosine similarity search using the <=> operator.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from psycopg.rows import dict_row

from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)


def _vector_to_pg_literal(vec: List[float]) -> str:
    """Formats float list to standard PostgreSQL pgvector literal [x,y,z]."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


class PostgresRepository:
    """Repository handling conversations, turns, case state, knowledge, vectors, and audits in PostgreSQL."""

    def __init__(self):
        pass

    def create_or_get_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Ensures a conversation record exists in PostgreSQL."""
        conn = get_db_connection()
        try:
            with conn.cursor(row_factory=dict_row) as cursor:
                if user_id:
                    cursor.execute(
                        "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                        (user_id,),
                    )

                cursor.execute(
                    "SELECT id, user_id, status FROM conversations WHERE id = %s",
                    (conversation_id,),
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

                cursor.execute(
                    """
                    INSERT INTO conversations (id, user_id, status)
                    VALUES (%s, %s, 'active')
                    ON CONFLICT (id) DO UPDATE SET status = 'active'
                    RETURNING id, user_id, status
                    """,
                    (conversation_id, user_id),
                )
                new_row = cursor.fetchone()
                conn.commit()
                return dict(new_row) if new_row else {"id": conversation_id, "user_id": user_id, "status": "active"}
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
        """Appends a turn to conversation_turns in PostgreSQL."""
        self.create_or_get_conversation(conversation_id)
        conn = get_db_connection()
        meta_str = json.dumps(metadata or {})
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO conversation_turns (conversation_id, turn_index, role, content, language, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (conversation_id, turn_index, role) DO UPDATE SET
                        content = EXCLUDED.content,
                        language = EXCLUDED.language,
                        metadata = EXCLUDED.metadata
                    """,
                    (conversation_id, turn_index, role, content, language, meta_str),
                )
                conn.commit()
        finally:
            conn.close()

    def get_conversation_turns(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Retrieves ordered turns for a conversation from PostgreSQL."""
        conn = get_db_connection()
        try:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT turn_index, role, content, language, metadata, created_at
                    FROM conversation_turns
                    WHERE conversation_id = %s
                    ORDER BY turn_index ASC, id ASC
                    """,
                    (conversation_id,),
                )
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    d = dict(r)
                    if isinstance(d.get("metadata"), str):
                        try:
                            d["metadata"] = json.loads(d["metadata"])
                        except Exception:
                            pass
                    results.append(d)
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
        """Upserts active incident case state in PostgreSQL."""
        self.create_or_get_conversation(conversation_id)
        conn = get_db_connection()
        facts_json = json.dumps(confirmed_facts)
        questions_json = json.dumps(unresolved_questions)
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO case_state (
                        conversation_id, threat_category, confirmed_facts,
                        unresolved_questions, decisive_topic, last_updated
                    )
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (conversation_id) DO UPDATE SET
                        threat_category = EXCLUDED.threat_category,
                        confirmed_facts = EXCLUDED.confirmed_facts,
                        unresolved_questions = EXCLUDED.unresolved_questions,
                        decisive_topic = EXCLUDED.decisive_topic,
                        last_updated = CURRENT_TIMESTAMP
                    """,
                    (conversation_id, threat_category, facts_json, questions_json, decisive_topic),
                )
                conn.commit()
        finally:
            conn.close()

    def get_case_state(self, conversation_id: str) -> Dict[str, Any]:
        """Fetches active case state for a conversation from PostgreSQL."""
        conn = get_db_connection()
        try:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT threat_category, confirmed_facts, unresolved_questions, decisive_topic
                    FROM case_state
                    WHERE conversation_id = %s
                    """,
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
                d = dict(row)
                if isinstance(d.get("confirmed_facts"), str):
                    d["confirmed_facts"] = json.loads(d["confirmed_facts"])
                if isinstance(d.get("unresolved_questions"), str):
                    d["unresolved_questions"] = json.loads(d["unresolved_questions"])
                return d
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
        """Stores a guidance document, chunk, and pgvector embedding in PostgreSQL."""
        conn = get_db_connection()
        emb_literal = _vector_to_pg_literal(embedding)
        try:
            with conn.cursor() as cursor:
                # 1. Upsert knowledge_docs
                cursor.execute(
                    """
                    INSERT INTO knowledge_docs (id, doc_id, title, url, language, topic, audience)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        url = EXCLUDED.url,
                        language = EXCLUDED.language,
                        topic = EXCLUDED.topic,
                        audience = EXCLUDED.audience
                    """,
                    (doc_id, doc_id, title, url, language, topic, audience),
                )

                # 2. Upsert semantic_chunks
                cursor.execute(
                    """
                    INSERT INTO semantic_chunks (id, doc_id, chunk_index, section_header, chunk_text, token_count)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        section_header = EXCLUDED.section_header,
                        chunk_text = EXCLUDED.chunk_text,
                        token_count = EXCLUDED.token_count
                    """,
                    (chunk_id, doc_id, chunk_index, section_header, chunk_text, len(chunk_text.split())),
                )

                # 3. Upsert vector_embeddings using native vector(768)
                cursor.execute(
                    """
                    INSERT INTO vector_embeddings (chunk_id, embedding, model_id, dimension)
                    VALUES (%s, %s::vector, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        model_id = EXCLUDED.model_id,
                        dimension = EXCLUDED.dimension
                    """,
                    (chunk_id, emb_literal, model_id, len(embedding)),
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
        """Queries stored semantic chunks strictly via native pgvector cosine distance (<=>).
        
        Zero in-Python similarity calculation. Zero keyword matching.
        Leverages PostgreSQL HNSW index on vector_embeddings.
        """
        conn = get_db_connection()
        emb_literal = _vector_to_pg_literal(query_embedding)
        
        where_clauses = []
        params: List[Any] = [emb_literal]

        if filters:
            if "audience" in filters:
                aud = filters["audience"]
                where_clauses.append("(d.audience = %s OR d.audience = 'both')")
                params.append(aud)
            if "language" in filters:
                lang = filters["language"]
                where_clauses.append("d.language = %s")
                params.append(lang)
            if "topic" in filters:
                where_clauses.append("d.topic = %s")
                params.append(filters["topic"])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        
        # Second occurrence of emb_literal for ORDER BY distance
        params.append(emb_literal)
        params.append(top_k)

        query = f"""
            SELECT 
                c.id AS chunk_id,
                c.doc_id,
                c.chunk_text,
                c.section_header,
                d.title,
                d.url,
                d.language,
                d.topic,
                d.audience,
                (1.0 - (v.embedding <=> %s::vector)) AS similarity_score
            FROM semantic_chunks c
            JOIN knowledge_docs d ON c.doc_id = d.doc_id
            JOIN vector_embeddings v ON c.id = v.chunk_id
            {where_sql}
            ORDER BY v.embedding <=> %s::vector ASC
            LIMIT %s;
        """

        try:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    item = dict(r)
                    item["similarity_score"] = float(item["similarity_score"])
                    results.append(item)
                return results
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
        """Logs diagnostic metadata for RAG retrieval into PostgreSQL retrieval_audit."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO retrieval_audit (
                        conversation_id, turn_index, contextual_query_redacted,
                        embedding_model, embedding_version, retrieved_doc_ids,
                        similarity_scores, metadata_filters, latency_ms, evaluation_outcome
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        """Records security decision outcome in PostgreSQL decision_outcomes."""
        self.create_or_get_conversation(conversation_id)
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO decision_outcomes (
                        conversation_id, turn_index, action, risk_level,
                        urgency, requires_specialist, escalation_target,
                        twin_decisive_question, rationale
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        conversation_id,
                        turn_index,
                        action,
                        risk_level,
                        urgency,
                        requires_specialist,
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
        """Records GDPR consent in PostgreSQL consent_records."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                clean_user_id = user_id.strip() if (user_id and isinstance(user_id, str)) else None
                if clean_user_id:
                    cursor.execute(
                        "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                        (clean_user_id,),
                    )
                clean_conv_id = conversation_id.strip() if (conversation_id and isinstance(conversation_id, str)) else None
                if clean_conv_id:
                    # Ensure conversation exists if provided
                    cursor.execute(
                        "INSERT INTO conversations (id, user_id, status) VALUES (%s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                        (clean_conv_id, clean_user_id),
                    )

                cursor.execute(
                    """
                    INSERT INTO consent_records (user_id, conversation_id, telemetry_granted, processing_purpose)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (clean_user_id, clean_conv_id, telemetry_granted, purpose),
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
        """Records security audit events into PostgreSQL security_audit_events."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO security_audit_events (conversation_id, event_type, severity, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (conversation_id, event_type, severity, json.dumps(payload)),
                )
                conn.commit()
        finally:
            conn.close()

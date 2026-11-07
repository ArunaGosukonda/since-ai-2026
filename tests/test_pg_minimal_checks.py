"""Minimal 6 Acceptance Checks for Since AI on Google Cloud SQL PostgreSQL + pgvector.

Checks strictly per Hackathon specification:
1. PostgreSQL connection.
2. Schema/migration availability.
3. One knowledge document and embedding insertion.
4. One vector similarity retrieval.
5. One conversation persistence check.
6. One representative Dan hackathon scenario through the actual application.
"""

from __future__ import annotations
import uuid
import sys
import logging

from src.db.connection import get_db_connection
from src.db.repository import PostgresRepository
from src.rag.embedder import DenseEmbedder
from src.data import db_session
from src.conversation.live_chatbot import LiveChatbot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pg_verification")


def check_1_connection():
    logger.info("=== Check 1: PostgreSQL Connection ===")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, version();")
            db, user, ver = cursor.fetchone()
            logger.info("Connected to DB: %s as User: %s", db, user)
            logger.info("Server Version: %s", ver.split(",")[0])
            
            cursor.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            ext = cursor.fetchone()
            assert ext is not None, "pgvector extension is NOT installed!"
            logger.info("pgvector Extension: %s (version %s)", ext[0], ext[1])
            logger.info("Check 1 PASSED.")
            return True
    finally:
        conn.close()


def check_2_schema():
    logger.info("=== Check 2: Schema & Vector Index Availability ===")
    conn = get_db_connection()
    expected_tables = {
        "users", "conversations", "conversation_turns", "case_state",
        "security_incidents", "knowledge_docs", "semantic_chunks",
        "vector_embeddings", "retrieval_audit", "consent_records",
        "decision_outcomes", "security_audit_events"
    }
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            found_tables = {r[0] for r in cursor.fetchall()}
            missing = expected_tables - found_tables
            assert not missing, f"Missing PostgreSQL tables: {missing}"
            logger.info("All 12 schema tables verified: %s", sorted(expected_tables))

            cursor.execute("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE schemaname = 'public' AND indexname = 'idx_vector_embeddings_cosine';
            """)
            idx = cursor.fetchone()
            assert idx is not None, "idx_vector_embeddings_cosine HNSW index is missing!"
            logger.info("HNSW Cosine Index verified: %s", idx[0])
            logger.info("Check 2 PASSED.")
            return True
    finally:
        conn.close()


def check_3_insert():
    logger.info("=== Check 3: One Knowledge Document and Embedding Insertion ===")
    repo = PostgresRepository()
    embedder = DenseEmbedder()
    test_id = f"test_doc_{uuid.uuid4().hex[:6]}"
    chunk_id = f"test_chk_{uuid.uuid4().hex[:6]}"
    text = "DNA huijausviesti varoitus: älä koskaan luovuta pankkitunnuksia tekstiviestissä olevan linkin kautta."
    emb = embedder.embed_text(text)

    repo.save_knowledge_chunk_with_embedding(
        doc_id=test_id,
        title="DNA Testiohje",
        url="https://dna.fi/test",
        language="fi",
        topic="phishing",
        audience="consumer",
        chunk_id=chunk_id,
        chunk_index=0,
        section_header="Huijausviestit",
        chunk_text=text,
        embedding=emb,
        model_id=embedder.model_identifier,
    )
    logger.info("Successfully inserted document %s with chunk %s (dim=%d)", test_id, chunk_id, len(emb))
    logger.info("Check 3 PASSED.")
    return test_id, chunk_id


def check_4_retrieval(expected_chunk_id: str):
    logger.info("=== Check 4: One Vector Similarity Retrieval ===")
    repo = PostgresRepository()
    embedder = DenseEmbedder()
    query = "Sain oudon tekstiviestin pankin nimissä ja siinä on linkki"
    q_vec = embedder.embed_text(query)

    results = repo.query_similar_chunks(query_embedding=q_vec, top_k=3)
    assert len(results) > 0, "No chunks returned by pgvector similarity search!"
    top = results[0]
    logger.info("Top retrieved chunk: %s (Doc: %s, Similarity: %.4f)", top["chunk_id"], top["doc_id"], top["similarity_score"])
    logger.info("Excerpt: %s", top["chunk_text"][:80])
    assert top["similarity_score"] > 0.0, "Similarity score must be > 0.0!"
    logger.info("Check 4 PASSED.")
    return True


def check_5_conversation():
    logger.info("=== Check 5: One Conversation Persistence Check ===")
    cid = f"conv_test_{uuid.uuid4().hex[:8]}"
    db_session.create_or_update_session(cid, journey="suspicious_message", audience="consumer", language="fi")
    db_session.add_message(cid, role="user", msg_type="text", content="Sain huijausviestin")
    db_session.set_fact(cid, "clicked_link", "no")

    msgs = db_session.get_messages(cid)
    facts = db_session.get_facts(cid)

    assert len(msgs) == 1, f"Expected 1 message, got {len(msgs)}"
    assert msmsgs := msgs[0]["content"] == "Sain huijausviestin"
    assert facts.get("clicked_link") == "no"

    logger.info("Conversation %s persisted with %d message and fact clicked_link=%s", cid, len(msgs), facts.get("clicked_link"))
    logger.info("Check 5 PASSED.")
    return cid


def check_6_scenario():
    logger.info("=== Check 6: One Representative Dan Hackathon Scenario ===")
    bot = LiveChatbot()
    session_id = f"dan_test_{uuid.uuid4().hex[:8]}"
    
    # Representative Dan Scenario: Suspicious package SMS with link
    msg = "Sain tekstiviestin Postin nimissä että minulla on saapunut paketti ja pitää maksaa tullimaksu linkistä. Mitä minun pitäisi tehdä?"
    logger.info("User prompt: %s", msg)
    
    response = bot.handle_user_message(session_id, msg)
    reply_type = response.get("reply_type")
    logger.info("LiveChatbot Reply Type: %s", reply_type)
    logger.info("Response Text Excerpt: %s", response.get("text", "")[:120])
    logger.info("Retrieved RAG Docs count: %d", len(response.get("rag_docs", [])))

    assert len(response.get("text", "")) > 10, "Response text is too short!"
    assert len(response.get("rag_docs", [])) > 0, "No RAG docs retrieved from PostgreSQL!"

    # Verify conversation is persisted in PostgreSQL
    history = db_session.get_messages(session_id)
    assert len(history) >= 2, f"Expected at least 2 messages in PostgreSQL, found {len(history)}"
    logger.info("PostgreSQL Conversation Turns verified: %d turns saved", len(history))
    logger.info("Check 6 PASSED.")
    return True


def run_all_checks():
    logger.info("Starting minimal 6 verification checks on PostgreSQL...")
    check_1_connection()
    check_2_schema()
    _, chunk_id = check_3_insert()
    check_4_retrieval(chunk_id)
    check_5_conversation()
    check_6_scenario()
    logger.info("ALL 6 ESSENTIAL CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_all_checks()

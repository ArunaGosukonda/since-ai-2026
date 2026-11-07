-- Since AI Database Migration 001: Initial Schema
-- Target: Google Cloud SQL for PostgreSQL 16 (europe-north1) with pgvector

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Users table (GDPR pseudonymized user records)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    locale VARCHAR(8) NOT NULL DEFAULT 'fi',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    channel VARCHAR(32) NOT NULL DEFAULT 'web'
);

-- 3. Conversation Turns table (Multi-turn chat history)
CREATE TABLE IF NOT EXISTS conversation_turns (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_index INT NOT NULL,
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    language VARCHAR(8) DEFAULT 'fi',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_conversation_turn UNIQUE (conversation_id, turn_index, role)
);

-- 4. Case State table (Accumulated incident facts and active security questions)
CREATE TABLE IF NOT EXISTS case_state (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    threat_category VARCHAR(64),
    confirmed_facts JSONB NOT NULL DEFAULT '{}'::jsonb,
    unresolved_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    decisive_topic VARCHAR(64),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Security Incidents table
CREATE TABLE IF NOT EXISTS security_incidents (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(64) REFERENCES conversations(id) ON DELETE CASCADE,
    risk_level VARCHAR(16) NOT NULL CHECK (risk_level IN ('none', 'low', 'medium', 'high', 'critical')),
    urgency VARCHAR(16) NOT NULL CHECK (urgency IN ('low', 'medium', 'high', 'critical')),
    action_type VARCHAR(64) NOT NULL,
    requires_specialist BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Knowledge Docs table (Official DNA Guidance Corpus)
CREATE TABLE IF NOT EXISTS knowledge_docs (
    id VARCHAR(64) PRIMARY KEY,
    doc_id VARCHAR(64) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    url TEXT,
    language VARCHAR(8) NOT NULL DEFAULT 'fi',
    topic VARCHAR(64) NOT NULL,
    audience VARCHAR(32) NOT NULL DEFAULT 'consumer',
    content_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Semantic Chunks table
CREATE TABLE IF NOT EXISTS semantic_chunks (
    id VARCHAR(64) PRIMARY KEY,
    doc_id VARCHAR(64) NOT NULL REFERENCES knowledge_docs(doc_id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    section_header TEXT,
    chunk_text TEXT NOT NULL,
    token_count INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_doc_chunk UNIQUE (doc_id, chunk_index)
);

-- 8. Vector Embeddings table (Dense Semantic Embeddings with Cosine Similarity)
CREATE TABLE IF NOT EXISTS vector_embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(64) NOT NULL UNIQUE REFERENCES semantic_chunks(id) ON DELETE CASCADE,
    embedding vector(768) NOT NULL,
    model_id VARCHAR(64) NOT NULL,
    dimension INT NOT NULL DEFAULT 768,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Cosine similarity index using HNSW
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_cosine 
ON vector_embeddings USING hnsw (embedding vector_cosine_ops);

-- 9. Retrieval Audit table (Mandatory Diagnostic Logging)
CREATE TABLE IF NOT EXISTS retrieval_audit (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(64) REFERENCES conversations(id) ON DELETE SET NULL,
    turn_index INT,
    contextual_query_redacted TEXT NOT NULL,
    embedding_model VARCHAR(64) NOT NULL,
    embedding_version VARCHAR(32),
    retrieved_doc_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    similarity_scores JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_filters JSONB DEFAULT '{}'::jsonb,
    latency_ms REAL NOT NULL,
    evaluation_outcome VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. Consent Records table (GDPR Telemetry & Processing Audit)
CREATE TABLE IF NOT EXISTS consent_records (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) REFERENCES users(id) ON DELETE CASCADE,
    conversation_id VARCHAR(64) REFERENCES conversations(id) ON DELETE CASCADE,
    telemetry_granted BOOLEAN NOT NULL DEFAULT FALSE,
    processing_purpose VARCHAR(64) NOT NULL DEFAULT 'incident_resolution',
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 11. Decision Outcomes table (Authoritative Decision Engine History)
CREATE TABLE IF NOT EXISTS decision_outcomes (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_index INT NOT NULL,
    action VARCHAR(64) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    urgency VARCHAR(16) NOT NULL,
    requires_specialist BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_target VARCHAR(64),
    twin_decisive_question TEXT,
    rationale TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 12. Security Audit Events table (Prompt Injection, Red-Team & Anomaly Log)
CREATE TABLE IF NOT EXISTS security_audit_events (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(64),
    event_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

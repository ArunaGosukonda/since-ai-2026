"""Ingestion pipeline for Since AI Knowledge Corpus.

Chunks the 56 official DNA guidance articles, generates dense vector embeddings
via DenseEmbedder, and stores them in PostgreSQL with pgvector (vector(768)).
Strict zero-lexical policy: pure dense vectors and relational storage in PostgreSQL.
"""

from __future__ import annotations
import logging
import time
from typing import Dict, Any, Optional

from src.rag.chunker import SemanticChunker
from src.rag.embedder import DenseEmbedder
from src.db.repository import PostgresRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ingest_guidance_corpus(corpus_path: Optional[str] = None) -> int:
    """Ingests guidance corpus chunks and dense embeddings into PostgreSQL.
    
    Returns total number of semantic chunks ingested.
    """
    chunker = SemanticChunker(corpus_path)
    embedder = DenseEmbedder()
    repo = PostgresRepository()

    count = 0
    start_time = time.time()
    logger.info("Starting dense vector knowledge ingestion (Model: %s)...", embedder.model_identifier)

    for chunk in chunker.process_corpus():
        emb = embedder.embed_text(chunk["chunk_text"])
        repo.save_knowledge_chunk_with_embedding(
            doc_id=chunk["doc_id"],
            title=chunk["title"],
            url=chunk["url"],
            language=chunk["language"],
            topic=chunk["topic"],
            audience=chunk["audience"],
            chunk_id=chunk["chunk_id"],
            chunk_index=chunk["chunk_index"],
            section_header=chunk["section_header"],
            chunk_text=chunk["chunk_text"],
            embedding=emb,
            model_id=embedder.model_identifier,
        )
        count += 1
        if count % 20 == 0:
            logger.info("Ingested %d semantic chunks into PostgreSQL...", count)

    elapsed = time.time() - start_time
    logger.info("Ingestion completed: %d chunks embedded and indexed in PostgreSQL in %.2fs", count, elapsed)
    return count


if __name__ == "__main__":
    ingest_guidance_corpus()

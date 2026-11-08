"""Grounded Dense Semantic RAG Retriever over DNA Official Guidance Corpus.

Strict Zero-Lexical Policy:
- Uses dense vector embedding similarity and contextual semantic retrieval exclusively.
- No BM25, TF-IDF, keyword matching, lexical search, hybrid retrieval, RRF or keyword fallback.
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional

from src.core.contracts import ContextualQuery
from src.rag.retriever import ContextualDenseRetriever
from src.rag.embedder import DenseEmbedder
from src.db.repository import PostgresRepository

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
CORPUS_PATH = os.path.join(ROOT, "data/reference/guidance_corpus.jsonl")


class GuidanceRAGRetriever:
    """Dense vector semantic retriever for DNA security guidance.
    
    Provides backward-compatible interface backed strictly by dense vector embeddings.
    """

    def __init__(self, corpus_path: str = CORPUS_PATH):
        self.corpus_path = corpus_path
        self.embedder = DenseEmbedder()
        self.repo = PostgresRepository()
        self.retriever = ContextualDenseRetriever(embedder=self.embedder, repository=self.repo)
        self.documents: Dict[str, Dict[str, Any]] = {}
        self._load_corpus()

    def _load_corpus(self):
        if not os.path.exists(self.corpus_path):
            return
        with open(self.corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    doc = json.loads(line)
                    self.documents[doc["id"]] = doc

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        audience: Optional[str] = None,
        language: str = "fi",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        confirmed_facts: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves guidance documents matching the query using dense vector cosine similarity."""
        ctx_query = self.retriever.build_contextual_query(
            user_message=query,
            conversation_history=conversation_history,
            confirmed_facts=confirmed_facts,
            language=language,
        )

        filters = {}
        if audience:
            filters["audience"] = audience

        try:
            passages = self.retriever.retrieve(
                contextual_query=ctx_query,
                top_k=top_k,
                filters=filters,
            )
        except Exception:
            passages = []

        results = []
        for p in passages:
            base_id = p.doc_id.replace("_fi", "").replace("_en", "")
            doc = self.documents.get(base_id)
            if doc:
                res = dict(doc)
                res["similarity_score"] = p.similarity_score
                results.append(res)
            else:
                results.append({
                    "id": p.doc_id,
                    "title_fi": p.title,
                    "text_fi": p.content,
                    "title_en": p.title,
                    "text_en": p.content,
                    "url": p.url,
                    "similarity_score": p.similarity_score,
                })
        return results

    def get_by_id(self, guidance_id: str) -> Optional[Dict[str, Any]]:
        """Looks up a specific guidance document by its ID."""
        return self.documents.get(guidance_id)

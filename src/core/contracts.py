"""Core service contracts and data interfaces for Since AI.

Defines strict boundaries between:
- Contextual Dense Retrieval
- Dense Embeddings
- Conversational LLM (Gemini Flash)
- Deterministic Decision Engine
- Persistence & Audit Repository
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class RetrievedPassage:
    """A grounded knowledge passage retrieved via vector similarity."""
    doc_id: str
    chunk_id: str
    title: str
    content: str
    url: str
    language: str
    topic: str
    similarity_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalDiagnostics:
    """Structured diagnostics logged for every vector retrieval execution."""
    contextual_query_redacted: str
    embedding_model: str
    embedding_version: str
    retrieved_doc_ids: List[str]
    similarity_scores: List[float]
    metadata_filters: Dict[str, Any]
    latency_ms: float
    evaluation_outcome: str  # e.g., 'PASSED', 'BELOW_CONFIDENCE_THRESHOLD'
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ContextualQuery:
    """Synthesized multi-turn context used for dense vector retrieval."""
    raw_user_message: str
    synthesized_text: str
    confirmed_facts: Dict[str, Any]
    unresolved_questions: List[str]
    active_threat_category: Optional[str] = None
    language: str = "fi"


class EmbedderInterface(Protocol):
    """Protocol for dense vector embedding models."""
    def embed_text(self, text: str) -> List[float]:
        ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        ...

    @property
    def model_identifier(self) -> str:
        ...

    @property
    def dimension(self) -> int:
        ...


class VectorRetrieverInterface(Protocol):
    """Protocol for dense vector semantic retrieval.
    
    Zero-Lexical Policy: Keyword matching, BM25, TF-IDF, lexical search,
    hybrid retrieval, RRF, or keyword fallback are strictly prohibited.
    """
    def retrieve(
        self,
        contextual_query: ContextualQuery,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedPassage]:
        ...

    def get_last_diagnostics(self) -> Optional[RetrievalDiagnostics]:
        ...


class LLMClientInterface(Protocol):
    """Protocol for conversational LLMs (e.g. Gemini Flash in europe-north1)."""
    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        ...


@dataclass
class DecisionOutcome:
    """Authoritative output from deterministic decision engine."""
    action: str
    risk_level: str
    urgency: str
    requires_specialist: bool
    escalation_target: Optional[str]
    twin_decisive_question: Optional[str] = None
    rationale: str = ""

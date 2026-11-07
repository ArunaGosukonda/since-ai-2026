"""Core contracts and architectural interfaces for Since AI."""
from src.core.contracts import (
    ContextualQuery,
    DecisionOutcome,
    EmbedderInterface,
    LLMClientInterface,
    RetrievalDiagnostics,
    RetrievedPassage,
    VectorRetrieverInterface,
)

__all__ = [
    "ContextualQuery",
    "DecisionOutcome",
    "EmbedderInterface",
    "LLMClientInterface",
    "RetrievalDiagnostics",
    "RetrievedPassage",
    "VectorRetrieverInterface",
]

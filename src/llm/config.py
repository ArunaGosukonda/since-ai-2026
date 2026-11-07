"""Configuration for Google Cloud Vertex AI and Gemini models.

Strict Data Residency: All processing occurs in europe-north1 (Hamina, Finland).
Configurable Model IDs: Zero hardcoded model identifiers throughout the codebase.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    """Immutable configuration for Vertex AI and regional models."""
    gcp_region: str = os.getenv("GCP_REGION", "europe-north1")
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
    gemini_flash_model_id: str = os.getenv("GEMINI_FLASH_MODEL_ID", "gemini-1.5-flash-002")
    gemini_embedding_model_id: str = os.getenv("GEMINI_EMBEDDING_MODEL_ID", "gemini-embedding-001")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    max_output_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    enforce_finnish_residency: bool = True


DEFAULT_CONFIG = LLMConfig()

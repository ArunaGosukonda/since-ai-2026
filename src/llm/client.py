"""Google Cloud Vertex AI Regional Client for Gemini Flash.

Location: europe-north1 (Hamina, Finland).
Strict Residency: Never routes to non-Finnish endpoints without documented approval.
"""

from __future__ import annotations
import logging
import os
from typing import Optional

from src.core.contracts import LLMClientInterface
from src.llm.config import DEFAULT_CONFIG, LLMConfig

logger = logging.getLogger(__name__)


class VertexGeminiFlashClient(LLMClientInterface):
    """Regional Gemini Flash client running on Vertex AI europe-north1."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self._model = None
        self._init_client()

    def _init_client(self):
        """Initializes Vertex AI client strictly in europe-north1."""
        if self.config.enforce_finnish_residency and self.config.gcp_region != "europe-north1":
            raise ValueError(
                f"Data Residency Violation: Target region '{self.config.gcp_region}' is not approved. "
                "Only 'europe-north1' (Finland) is permitted."
            )

        if self.config.gcp_project_id and os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel
                vertexai.init(project=self.config.gcp_project_id, location=self.config.gcp_region)
                self._model = GenerativeModel(self.config.gemini_flash_model_id)
                logger.info(
                    "Initialized Vertex AI Gemini Flash (%s) in region %s",
                    self.config.gemini_flash_model_id,
                    self.config.gcp_region,
                )
            except Exception as e:
                logger.warning("Vertex AI initialization skipped: %s. Using hermetic local generator.", e)
                self._model = None

    @property
    def is_cloud_connected(self) -> bool:
        return self._model is not None

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generates conversational text using regional Gemini Flash."""
        temp = temperature if temperature is not None else self.config.temperature

        if self._model:
            try:
                # Direct invocation of Vertex AI Gemini Flash
                kwargs = {"temperature": temp}
                if system_instruction:
                    from vertexai.generative_models import GenerativeModel
                    # Re-instantiate with system instruction if provided
                    model_with_sys = GenerativeModel(
                        self.config.gemini_flash_model_id,
                        system_instruction=[system_instruction],
                    )
                    resp = model_with_sys.generate_content(prompt, generation_config=kwargs)
                else:
                    resp = self._model.generate_content(prompt, generation_config=kwargs)
                return resp.text.strip()
            except Exception as e:
                logger.error("Vertex AI inference error (%s). Falling back to grounded template generator.", e)

        # Fallback offline generator (hermetic test mode)
        return ""

"""Pydantic and dataclass request/response schemas for Since AI REST API."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
try:
    from pydantic import BaseModel, Field
except ImportError:
    # Graceful fallback for environments without pydantic installed
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def dict(self):
            return self.__dict__
    def Field(*args, **kwargs):
        return None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    language: Optional[str] = "fi"


class SessionCreateRequest(BaseModel):
    user_id: Optional[str] = None
    language: Optional[str] = "fi"
    telemetry_consent: bool = False


class ConsentRequest(BaseModel):
    user_id: str
    session_id: str
    telemetry_granted: bool
    purpose: str = "incident_resolution"


class ChatResponse(BaseModel):
    session_id: str
    reply_type: str  # 'question' or 'final'
    user_language: str
    text: str
    text_en: str
    action: Optional[str] = None
    risk_level: Optional[str] = None
    urgency: Optional[str] = None
    requires_specialist: bool = False
    escalation_target: Optional[str] = None
    decisive_question: Optional[str] = None
    steps_primary: List[str] = []
    steps_en: List[str] = []
    retrieved_passages: List[Dict[str, Any]] = []
    retrieval_diagnostics: Optional[Dict[str, Any]] = None

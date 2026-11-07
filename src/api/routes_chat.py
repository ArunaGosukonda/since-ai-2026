"""Chat and session routes for Since AI REST API."""

import uuid
from typing import Any, Dict

from src.api.schemas import ChatRequest, ChatResponse, ConsentRequest, SessionCreateRequest
from src.conversation.live_chatbot import LiveChatbot
from src.db.connection import get_active_backend
from src.db.repository import PostgresRepository
from src.llm.config import DEFAULT_CONFIG

_chatbot = LiveChatbot()
_repo = PostgresRepository()


def handle_create_session(req: Dict[str, Any]) -> Dict[str, Any]:
    session_id = req.get("session_id") or f"session_{uuid.uuid4().hex[:12]}"
    user_id = req.get("user_id") or f"anon_{uuid.uuid4().hex[:8]}"
    _repo.create_or_get_conversation(session_id, user_id=user_id)
    if req.get("telemetry_consent"):
        _repo.record_consent(user_id=user_id, conversation_id=session_id, telemetry_granted=True)
    return {
        "session_id": session_id,
        "user_id": user_id,
        "status": "active",
        "region": DEFAULT_CONFIG.gcp_region,
    }


def handle_chat_message(req: Dict[str, Any]) -> Dict[str, Any]:
    session_id = req.get("session_id") or f"session_{uuid.uuid4().hex[:12]}"
    user_id = req.get("user_id") or None
    channel = req.get("channel") or "web"
    sender_verified = bool(req.get("sender_identity_verified", False))
    message = req.get("message", "").strip()
    result = _chatbot.handle_user_message(
        session_id=session_id,
        message=message,
        user_id=user_id,
        channel=channel,
        sender_identity_verified=sender_verified,
    )
    return result


def handle_consent_update(req: Dict[str, Any]) -> Dict[str, Any]:
    user_id = req.get("user_id") or None
    session_id = req.get("session_id") or None
    granted = bool(req.get("telemetry_granted", req.get("granted", False)))
    purpose = req.get("purpose", "incident_resolution")
    _repo.record_consent(user_id=user_id, conversation_id=session_id, telemetry_granted=granted, purpose=purpose)
    return {"status": "recorded", "user_id": user_id, "telemetry_granted": granted}


def handle_health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "Since AI DNA Digital Security Assistant",
        "region": DEFAULT_CONFIG.gcp_region,
        "location": "Hamina, Finland (europe-north1)",
        "database_backend": get_active_backend(),
        "gemini_flash_model": DEFAULT_CONFIG.gemini_flash_model_id,
        "embedding_model": DEFAULT_CONFIG.gemini_embedding_model_id,
        "zero_lexical_enforced": True,
    }

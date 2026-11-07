# -*- coding: utf-8 -*-
"""Live Dynamic Chatbot Engine for Since AI — DNA Digital Security Assistant.

Processes arbitrary free-form security questions from human users,
determines threat intent, asks decisive questions to complete the journey,
grounds responses in DNA official guidance via RAG, and saves state to SQLite.
"""
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.data.db_session import (
    create_or_update_session, add_message, get_messages,
    set_fact, get_facts, save_decision, get_decision
)
from src.knowledge.rag_retriever import GuidanceRAGRetriever
from src.intelligence.signal_fusion import fuse_signals, matches_any
from src.decision.twin_resolver import detect_decisive_question
from src.decision.action_selector import ActionSelector
from src.explanations.generator import generate_response
from src.security.output_guard import OutputSecurityGate

_rag = GuidanceRAGRetriever()
_selector = ActionSelector()
_guard = OutputSecurityGate()


def _detect_language(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(jag|har|inte|och|på|det|som|med|ett|till|är)\b", t):
        return "sv"
    if re.search(r"\b(the|is|and|to|in|of|my|have|has|what|should|scam|call|link|bank)\b", t):
        return "en"
    return "fi"


def _detect_journey(text: str) -> str:
    t = text.lower()
    if matches_any(t, [r"soitti|puhelu|soittaja|called|caller|phone call|ringde|samtal"]):
        return "suspicious_call"
    if matches_any(t, [r"latasin|asensin|apk|installed|downloaded|klikkasin|avasin link|klickade"]):
        return "clicked_link"
    if matches_any(t, [r"ei kenttää|no service|esim|kirjautumi|login notice|password reset|tuntematon kirjautu"]):
        return "breach_notice"
    if matches_any(t, [r"yrity|laskut|invoice|ceo|toimitusjohtaja|lunnas|ransom|kumppani|supplier"]):
        return "smb_incident"
    return "suspicious_message"


def _detect_audience(text: str) -> str:
    t = text.lower()
    if matches_any(t, [r"yrity|firma|yhtiö|business|lasku|toimitusjohtaja|kirjanpito|ceo|invoice"]):
        return "small_business"
    return "consumer"


class LiveChatbot:
    """Coordinates arbitrary live chat sessions with multi-turn fact elicitation."""

    def __init__(self):
        self.rag = _rag
        self.selector = _selector
        self.guard = _guard

    def handle_user_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Takes an arbitrary user message and advances the security journey."""
        message = message.strip()
        add_message(session_id, role="user", msg_type="text", content=message)
        
        history = get_messages(session_id)
        facts = get_facts(session_id)
        
        # Check if this message answers a pending decisive question
        last_bot_msg = next((m for m in reversed(history[:-1]) if m["role"] == "assistant"), None)
        
        lang = _detect_language(message)
        audience = _detect_audience(message)
        journey = _detect_journey(history[0]["content"] if history else message)
        create_or_update_session(session_id, journey=journey, audience=audience, language=lang)
        
        # If user is answering a previous question:
        if last_bot_msg and last_bot_msg.get("msg_type") == "question":
            # Extract topic or store answer
            facts["user_answer"] = message
            t = message.lower()
            if matches_any(t, [r"kyllä|joo|olen|syötin|annoin|maksoin|yes|did|gave|paid|ja"]):
                facts["confirmed_risk"] = "yes"
            else:
                facts["confirmed_risk"] = "no"
            set_fact(session_id, "user_answer", message)
            set_fact(session_id, "confirmed_risk", facts["confirmed_risk"])

        # Grounding with RAG
        rag_docs = self.rag.retrieve(query=f"{history[0]['content']} {message}", top_k=3, audience=audience)
        
        # Synthesize a case dictionary for the fused context
        links = re.findall(r"https?://[^\s]+", history[0]["content"])
        case_dict = {
            "case_id": session_id,
            "opening_message": history[0]["content"],
            "journey": journey,
            "audience": audience,
            "language": lang,
            "signals": {
                "artifact": {
                    "type": "sms" if journey == "suspicious_message" else "call" if journey == "suspicious_call" else "email",
                    "body": history[0]["content"],
                    "links": links
                },
                "link_check": {"verdict": "malicious"} if links else None,
                "subscription": {
                    "network_status": {"service": "no_service" if "ei kenttää" in history[0]["content"].lower() else "normal"}
                },
                "device": {
                    "summary": {"platform": "mobile"}
                }
            }
        }

        ctx = fuse_signals(case_dict, facts)
        
        # Check for decisive question
        decisive = detect_decisive_question(ctx, facts)
        
        # If decisive question is needed and not yet answered:
        if decisive and not facts.get("user_answer"):
            topic, q_text = decisive
            add_message(session_id, role="assistant", msg_type="question", content=q_text)
            return {
                "session_id": session_id,
                "reply_type": "question",
                "text": q_text,
                "topic": topic,
                "rag_docs": [
                    {
                        "id": d["id"],
                        "title": d.get(f"title_{lang}", d.get("title_fi")),
                        "excerpt": d.get(f"text_{lang}", d.get("text_fi"))[:160] + "..."
                    } for d in rag_docs
                ]
            }

        # Otherwise, resolve to final advice
        rec = self.selector.decide(ctx, facts, mode="multi_turn")
        advice_text, steps, _, _ = generate_response(
            ctx=ctx,
            action=rec.primary_action,
            required_steps=rec.required_steps,
            decisive_question=None,
            escalation_required=rec.escalation_required,
            escalation_target=rec.escalation_target
        )

        candidate = {
            "case_id": session_id,
            "mode": "multi_turn",
            "risk_level": rec.risk_level,
            "primary_action": rec.primary_action,
            "urgency": rec.urgency,
            "advice_text": advice_text,
            "steps": steps,
            "questions_asked": [],
            "question_topics": [],
            "escalation_required": rec.escalation_required,
            "escalation_target": rec.escalation_target,
            "citations": [d["id"] for d in rag_docs] or rec.citations,
            "signals_used": ["artifact"] + (["link_check"] if links else []),
            "consent_requested_for": [],
            "confidence": 0.95,
            "abstained": False
        }

        final_ans, is_valid, _ = self.guard.verify_and_guard(candidate, lang=lang)
        save_decision(session_id, final_ans)
        add_message(session_id, role="assistant", msg_type="final", content=final_ans.get("advice_text", ""))

        return {
            "session_id": session_id,
            "reply_type": "final",
            "text": final_ans.get("advice_text", ""),
            "decision": final_ans,
            "rag_docs": [
                {
                    "id": d["id"],
                    "title": d.get(f"title_{lang}", d.get("title_fi")),
                    "excerpt": d.get(f"text_{lang}", d.get("text_fi"))[:160] + "..."
                } for d in rag_docs
            ]
        }

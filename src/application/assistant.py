# -*- coding: utf-8 -*-
"""Main Digital Security Assistant Pipeline for DNA Hackathon 2026.
Orchestrates signal fusion, decision logic, consent management,
action-first generation, and the output security gate.
"""
from typing import Any, Dict, List, Optional, Set
from src.intelligence.signal_fusion import fuse_signals
from src.decision.action_selector import ActionSelector
from src.consent.consent_manager import ConsentManager
from src.explanations.generator import generate_response
from src.security.output_guard import OutputSecurityGate

class DigitalSecurityAssistant:
    def __init__(self):
        self.selector = ActionSelector()
        self.guard = OutputSecurityGate()

    def process_case(
        self,
        case: Dict[str, Any],
        facts: Optional[Dict[str, str]] = None,
        mode: str = "single_turn",
        granted_consent: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Processes a single case or conversation turn into a schema-compliant answer."""
        facts = facts or {}
        granted_consent = granted_consent or set()
        
        # 1. Ingress & Signal Fusion
        ctx = fuse_signals(case, facts)
        lang = ctx.language if ctx.language in ("fi", "en", "sv") else "fi"
        
        # 2. Decision Engine
        rec = self.selector.decide(ctx, facts, mode=mode)
        
        # 3. Privacy & Consent Management
        signals_used, consent_requested = ConsentManager.get_signals_and_consent(
            ctx,
            is_multi_turn=(mode == "multi_turn"),
            granted_in_conv=granted_consent
        )
        
        # 4. Action-First Grounded Generation
        advice_text, steps, questions_asked, question_topics = generate_response(
            ctx=ctx,
            action=rec.primary_action,
            required_steps=rec.required_steps,
            decisive_question=rec.decisive_question,
            escalation_required=rec.escalation_required,
            escalation_target=rec.escalation_target,
        )
        
        # 5. Assemble Candidate Submission Record
        candidate = {
            "case_id": case.get("case_id", ""),
            "mode": mode,
            "risk_level": rec.risk_level,
            "primary_action": rec.primary_action,
            "urgency": rec.urgency,
            "advice_text": advice_text,
            "steps": steps,
            "questions_asked": questions_asked,
            "question_topics": question_topics,
            "escalation_required": rec.escalation_required,
            "escalation_target": rec.escalation_target,
            "citations": rec.citations,
            "signals_used": signals_used,
            "consent_requested_for": consent_requested,
            "confidence": 0.85,
            "abstained": False,
        }
        
        # 6. Independent Output Security Gate
        final_answer, is_valid, violations = self.guard.verify_and_guard(candidate, lang=lang)
        
        return final_answer

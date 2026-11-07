"""Response Orchestrator coordinating Decision Engine, Dense RAG, and Gemini Flash.

Enforces:
1. Decision engine authority over LLM outputs (action, risk, urgency).
2. Untrusted evidence separation.
3. Independent OutputSecurityGate validation.
4. Full audit trail logging.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from src.core.contracts import ContextualQuery, DecisionOutcome, RetrievedPassage
from src.db.repository import PostgresRepository
from src.decision.action_selector import ActionSelector
from src.decision.escalation_engine import EscalationEngine
from src.decision.twin_resolver import TwinResolver
from src.explanations.generator import ExplanationGenerator
from src.intelligence.benign_classifier import is_benign_control
from src.intelligence.signal_fusion import FusedContext, fuse_signals
from src.llm.client import VertexGeminiFlashClient
from src.llm.prompts import SYSTEM_INSTRUCTION, format_grounding_prompt
from src.rag.retriever import ContextualDenseRetriever
from src.security.output_guard import OutputSecurityGate

logger = logging.getLogger(__name__)


class ResponseOrchestrator:
    """Coordinates multi-turn cybersecurity incident response."""

    def __init__(
        self,
        llm_client: Optional[VertexGeminiFlashClient] = None,
        retriever: Optional[ContextualDenseRetriever] = None,
        repository: Optional[PostgresRepository] = None,
    ):
        self.llm = llm_client or VertexGeminiFlashClient()
        self.retriever = retriever or ContextualDenseRetriever()
        self.repo = repository or PostgresRepository()

        # Deterministic decision components
        self.action_selector = ActionSelector()
        self.twin_resolver = TwinResolver()
        self.escalator = EscalationEngine()
        self.template_gen = ExplanationGenerator()
        self.output_guard = OutputSecurityGate()

    def process_turn(
        self,
        conversation_id: str,
        user_message: str,
        turn_index: int = 1,
        language: str = "fi",
    ) -> Dict[str, Any]:
        """Processes a single conversational turn with full deterministic and LLM orchestration."""
        # 1. Record incoming user turn
        self.repo.add_turn(
            conversation_id=conversation_id,
            turn_index=turn_index,
            role="user",
            content=user_message,
            language=language,
        )

        # 2. Fetch history and case state
        history = self.repo.get_conversation_turns(conversation_id)
        state = self.repo.get_case_state(conversation_id)
        confirmed_facts = state.get("confirmed_facts", {})

        # 3. Deterministic Signal Analysis & Decision Making
        case_dict = {
            "case_id": conversation_id,
            "opening_message": history[0]["content"] if history else user_message,
            "journey": "suspicious_message",
            "audience": "consumer",
            "language": language,
            "signals": {
                "artifact": {"type": "sms", "body": user_message}
            }
        }
        ctx = fuse_signals(case_dict, confirmed_facts)
        is_benign = is_benign_control(ctx)

        # Authoritative action selection
        rec = self.action_selector.decide(ctx, confirmed_facts, mode="multi_turn")
        primary_action = rec.primary_action
        risk_level = rec.risk_level
        urgency = rec.urgency
        requires_specialist = bool(rec.escalation_required)
        escalation_target = rec.escalation_target

        # Twin disambiguation
        twin_decision = self.twin_resolver.resolve(user_message, ctx, confirmed_facts, lang=language)
        decisive_question = None
        if twin_decision and twin_decision.get("is_twin") and not twin_decision.get("resolved"):
            decisive_question = twin_decision.get("decisive_question")

        # 4. Contextual Dense Vector Retrieval
        ctx_query = self.retriever.build_contextual_query(
            user_message=user_message,
            conversation_history=history,
            confirmed_facts=confirmed_facts,
            unresolved_questions=[decisive_question] if decisive_question else [],
            language=language,
        )
        retrieved_passages = self.retriever.retrieve(
            contextual_query=ctx_query,
            top_k=3,
        )

        # 5. Response Generation (Gemini Flash with fallback to template generator)
        final_text = ""
        if self.llm.is_cloud_connected:
            prompt = format_grounding_prompt(
                user_message=user_message,
                action=primary_action,
                risk_level=risk_level,
                urgency=urgency,
                requires_specialist=requires_specialist,
                retrieved_passages=retrieved_passages,
                confirmed_facts=confirmed_facts,
                decisive_question=decisive_question,
                language=language,
            )
            final_text = self.llm.generate(prompt=prompt, system_instruction=SYSTEM_INSTRUCTION)

        if not final_text:
            # High-assurance deterministic bilingual template fallback
            steps = rec.required_steps
            citations = [p.doc_id for p in retrieved_passages]
            template_output = self.template_gen.generate(
                action=primary_action,
                steps=steps,
                citations=citations,
                language=language,
                decisive_question=decisive_question,
            )
            final_text = template_output.get("advice_text", "")

        # 6. Output Security Gate
        sanitized_text = self.output_guard.guard_output(final_text, allowed_action=primary_action)

        # 7. Persist decisions and assistant turn
        self.repo.add_turn(
            conversation_id=conversation_id,
            turn_index=turn_index,
            role="assistant",
            content=sanitized_text,
            language=language,
            metadata={"action": primary_action, "risk_level": risk_level},
        )

        self.repo.record_decision_outcome(
            conversation_id=conversation_id,
            turn_index=turn_index,
            action=primary_action,
            risk_level=risk_level,
            urgency=urgency,
            requires_specialist=requires_specialist,
            escalation_target=escalation_target,
            twin_decisive_question=decisive_question,
            rationale=f"Decided {primary_action} ({risk_level} risk, {urgency} urgency)",
        )

        diagnostics = self.retriever.get_last_diagnostics()

        return {
            "conversation_id": conversation_id,
            "turn_index": turn_index,
            "response": sanitized_text,
            "action": primary_action,
            "risk_level": risk_level,
            "urgency": urgency,
            "requires_specialist": requires_specialist,
            "escalation_target": escalation_target,
            "decisive_question": decisive_question,
            "retrieved_passages": [
                {"id": p.doc_id, "title": p.title, "url": p.url, "score": p.similarity_score}
                for p in retrieved_passages
            ],
            "retrieval_diagnostics": diagnostics.__dict__ if diagnostics else {},
        }

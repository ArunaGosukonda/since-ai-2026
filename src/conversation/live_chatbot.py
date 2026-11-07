# -*- coding: utf-8 -*-
"""Live Dynamic Chatbot Engine for Since AI — DNA Digital Security Assistant.

Processes arbitrary free-form security questions from human users,
determines threat intent, asks decisive questions to complete the journey,
grounds responses in DNA official guidance via RAG, and saves state to PostgreSQL.

Hardened with:
- Deterministic adversarial and jailbreak defense.
- Out-of-scope inquiry classification and redirection.
- Banking communication and employee validation (15 scenarios).
- User and session authorization enforcement.
- Standardized outcomes: BENIGN, SUSPICIOUS_OR_MALICIOUS, INCONCLUSIVE, OUT_OF_SCOPE, SECURITY_POLICY_REFUSAL, ACCESS_DENIED.
"""
from __future__ import annotations

import copy
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.data.db_session import (
    add_message,
    create_or_update_session,
    get_decision,
    get_facts,
    get_messages,
    save_decision,
    set_fact,
    validate_session_ownership,
)
from src.db.repository import PostgresRepository
from src.decision.action_selector import ActionSelector
from src.decision.twin_resolver import detect_decisive_question
from src.explanations.generator import generate_response
from src.intelligence.banking_validator import BankingValidator
from src.intelligence.benign_classifier import is_benign_control
from src.classifier import get_threat_classifier
from src.intelligence.signal_fusion import fuse_signals, matches_any
from src.knowledge.rag_retriever import GuidanceRAGRetriever
from src.security.adversarial_detector import AdversarialDetector
from src.security.output_guard import OutputSecurityGate
from src.security.scope_enforcer import ScopeEnforcer

logger = logging.getLogger(__name__)

_rag = GuidanceRAGRetriever()
_selector = ActionSelector()
_guard = OutputSecurityGate()
_repo = PostgresRepository()
_adversarial = AdversarialDetector()
_scope_enforcer = ScopeEnforcer()
_banking_validator = BankingValidator()
_classifier = get_threat_classifier()


def _detect_language(text: str) -> str:
    t = text.lower()
    # Swedish distinctive words
    if re.search(r"\b(jag|har|inte|och|på|det|som|med|ett|till|är|hur|kan|vad|mig|här|ditt|mitt|från)\b", t):
        return "sv"
    # Finnish distinctive words / stems
    fi_hits = len(re.findall(r"\b(hei|on|olen|ovat|ei|mitä|miten|kuinka|pankki|pankin|puhelu|soitti|viesti|linkki|salasana|rahaa|tili|tilille|tarkista|luovuta|tämä|voinko|luottaa|toimihenkilö)\b", t))
    # English common & distinctive words
    en_hits = len(re.findall(r"\b(the|is|are|am|and|to|in|of|my|me|you|your|he|she|it|we|they|have|has|had|what|which|who|whom|whose|why|how|can|could|would|should|do|does|did|will|shall|tell|say|said|ask|asked|chatbot|bot|code|coding|logic|upgrade|card|reset|password|account|call|called|calling|phone|employee|loans?|genuine|trust|person|received|message|scam|fraud|link|bank|banking|benefits)\b", t))
    if en_hits > fi_hits:
        return "en"
    if fi_hits > 0:
        return "fi"
    if en_hits > 0:
        return "en"
    return "en" if re.search(r"[a-z]", t) and not re.search(r"[äöå]", t) and en_hits >= fi_hits else "fi"


def _detect_journey(text: str) -> str:
    t = text.lower()
    if matches_any(t, [r"soitti|puhelu|soittaja|called|caller|phone call|ringde|samtal"]):
        return "suspicious_call"
    if matches_any(t, [r"latasin|asensin|apk|installed|downloaded|klikkasin|avasin.*link|klickade|clicked|opened.*link|clicked.*link|open.*link|laddade ner|virus|malware|takeover|take over|trojan|hacked|kaapattu|saastunut|tartunta|infektoitunut"]):
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
    """Coordinates arbitrary live chat sessions with multi-turn fact elicitation and hybrid security."""

    def __init__(self):
        self.rag = _rag
        self.selector = _selector
        self.guard = _guard
        self.adversarial = _adversarial
        self.scope = _scope_enforcer
        self.banking = _banking_validator
        self.classifier = _classifier

    def handle_user_message(
        self,
        session_id: str,
        message: str,
        user_id: Optional[str] = None,
        channel: str = "web",
        sender_identity_verified: bool = False,
    ) -> Dict[str, Any]:
        """Takes an arbitrary user message and advances the security journey."""
        message = message.strip()
        lang = _detect_language(message)

        # -------------------------------------------------------------
        # 1. Privacy & Session Isolation Authorization Check
        # -------------------------------------------------------------
        if user_id and not validate_session_ownership(session_id, user_id):
            return {
                "session_id": session_id,
                "reply_type": "final",
                "outcome_type": "ACCESS_DENIED",
                "user_language": lang,
                "text": "Pääsy estetty. Sinulla ei ole oikeutta tarkastella tai muokata toisen käyttäjän istuntoa.",
                "text_en": "Access denied. You do not have permission to access or modify another user's session.",
                "steps_primary": ["Käytä omaa istuntotunnistettasi tai aloita uusi istunto."],
                "steps_en": ["Use your authorized session identifier or start a new session."],
                "decision": {
                    "risk_level": "routine",
                    "primary_action": "access_denied",
                    "urgency": "routine",
                    "advice_text": "Access denied. You do not have permission to access or modify another user's session.",
                    "steps": ["Use your authorized session identifier or start a new session."],
                    "outcome_type": "ACCESS_DENIED",
                    "confidence": 1.0,
                    "abstained": False,
                },
                "rag_docs": [],
            }

        # -------------------------------------------------------------
        # 2. Adversarial & Direct Jailbreak & Protected Info Check
        # -------------------------------------------------------------
        is_attack, attack_category, reason = self.adversarial.scan_for_attacks(message)
        if is_attack:
            try:
                _repo.record_security_audit_event(
                    conversation_id=session_id,
                    event_type=attack_category or "jailbreak_attempt",
                    severity="high",
                    payload={"message": message, "reason": reason},
                )
            except Exception:
                pass
            return self.adversarial.format_refusal_response(lang=lang)

        # -------------------------------------------------------------
        # 3. Out-of-Scope Enforcement Check
        # -------------------------------------------------------------
        is_in_scope, out_topic, explanation = self.scope.evaluate_scope(message)
        if not is_in_scope:
            return self.scope.format_out_of_scope_response(topic=out_topic or "general", lang=lang)

        # -------------------------------------------------------------
        # 4. Record Incoming Turn & Retrieve Prior Session History
        # -------------------------------------------------------------
        add_message(session_id, role="user", msg_type="text", content=message, user_id=user_id)
        history = get_messages(session_id, user_id=user_id)
        facts = get_facts(session_id, user_id=user_id)

        # Check if answering a previous decisive question
        last_question_idx = None
        for i in range(len(history) - 2, -1, -1):
            if history[i]["role"] == "assistant" and history[i].get("msg_type") == "question":
                last_question_idx = i
                break
            elif history[i]["role"] == "assistant" and history[i].get("msg_type") == "final":
                break

        is_answering_question = (last_question_idx is not None)
        audience = _detect_audience(message)

        if is_answering_question:
            inquiry_msg = history[last_question_idx - 1]["content"] if last_question_idx > 0 else history[0]["content"]
            journey = _detect_journey(inquiry_msg)
            opening_text = inquiry_msg
            active_facts = facts
            active_facts["user_answer"] = message
            t = message.lower()
            if matches_any(t, [r"kyllä|joo|olen|syötin|annoin|maksoin|yes|did|gave|paid|ja"]):
                active_facts["confirmed_risk"] = "yes"
            else:
                active_facts["confirmed_risk"] = "no"
            set_fact(session_id, "user_answer", message)
            set_fact(session_id, "confirmed_risk", active_facts["confirmed_risk"])
        else:
            journey = _detect_journey(message)
            opening_text = message
            active_facts = {}

        create_or_update_session(session_id, journey=journey, audience=audience, language=lang, user_id=user_id)

        # -------------------------------------------------------------
        # 5. Grounding with Dense Vector RAG (pgvector Cosine Retrieval)
        # -------------------------------------------------------------
        rag_docs = self.rag.retrieve(
            query=message,
            top_k=3,
            audience=audience,
            language=lang,
            conversation_history=history[-3:] if is_answering_question else None,
            confirmed_facts=active_facts,
        )

        # -------------------------------------------------------------
        # 6. Banking Communication & Employee Validation Analysis
        # -------------------------------------------------------------
        links = re.findall(r"https?://[^\s]+", opening_text)
        banking_analysis = self.banking.analyze_banking_communication(
            message=message,
            channel=channel,
            sender_identity_verified=sender_identity_verified,
            links=links,
        )

        if banking_analysis and not is_answering_question:
            b_class = banking_analysis["classification"]
            rec_action = banking_analysis["recommended_action"]
            
            # Format multilingual responses for banking evaluation
            if b_class == "INCONCLUSIVE":
                risk_lvl = "medium"
                if lang == "fi":
                    advice = (
                        "Älä luovuta tietoja äläkä tee päätöksiä puhelussa. Pankin nimissä tulevaa puhelua "
                        "tai yhteydenottoa ei voi varmistaa pelkän puheen tai soittajan numeron perusteella. "
                        "Tarkista mahdollinen laina- tai korttitarjous suoraan verkkopankkisovelluksestasi tai "
                        "soita pankkiin korttisi kääntöpuolella olevaan numeroon."
                    )
                    steps = [
                        "Älä kerro salasanoja, koodeja tai korttitietoja puhelimessa.",
                        "Tarkista tarjoukset suoraan omasta verkkopankkisovelluksestasi.",
                        "Soita pankkiin numeroon, jonka tiedät jo entuudestaan tai joka lukee kortissasi.",
                    ]
                elif lang == "sv":
                    advice = (
                        "Lämna inte ut uppgifter och fatta inga beslut under samtalet. Ett inkommande samtal "
                        "som påstås komma från banken kan inte verifieras via telefonen, eftersom numret kan "
                        "vara förfalskat. Kontrollera ärendet i din officiella bankapp eller ring numret på baksidan av ditt kort."
                    )
                    steps = [
                        "Dela aldrig koder, lösenord eller kortuppgifter via telefon.",
                        "Kontrollera eventuella erbjudanden direkt i din officiella bankapp.",
                        "Ring banken på numret på baksidan av ditt kort.",
                    ]
                else:
                    advice = (
                        "Do not disclose details or agree to offers on the call. An inbound caller claiming "
                        "to be from your bank cannot be verified by voice alone, as caller ID can be faked. "
                        "Verify the offer inside your official mobile banking app or call the bank using the number on your card."
                    )
                    steps = [
                        "Never share codes, passwords, or card numbers over the phone.",
                        "Check for legitimate loan or card offers directly inside your bank app.",
                        "Call the bank using the number printed on the back of your card.",
                    ]
            elif b_class == "SUSPICIOUS_OR_MALICIOUS":
                risk_lvl = "critical" if "salasana" in message.lower() or "password" in message.lower() or "otp" in message.lower() else "high"
                if lang == "fi":
                    advice = (
                        "Älä avaa linkkiä, älä luovuta tietoja äläkä siirrä rahaa. Tämä on huijausyritys, "
                        "jolla yritetään kalastella verkkopankkitunnuksia tai varoja. Pankki ei koskaan kysy "
                        "tunnuslukuja tai pyydä siirtämään varoja turvatilille."
                    )
                    steps = [
                        "Älä koskaan kerro salasanaa, tunnuslukua tai vahvistuskoodia kenellekään.",
                        "Älä siirrä rahaa väitetylle 'turvatilille'.",
                        "Jos luovutit jo tietoja, soita heti pankkisi sulkupalveluun.",
                    ]
                elif lang == "sv":
                    advice = (
                        "Öppna inte länken, lämna inte ut uppgifter och överför inte pengar. Detta är ett bedrägeriförsök "
                        "för att stjäla bankuppgifter eller pengar. Banker ber aldrig om koder eller lösenord."
                    )
                    steps = [
                        "Dela aldrig lösenord eller koder med någon.",
                        "Överför inte pengar till något 'säkert konto'.",
                        "Om du redan lämnat ut uppgifter, kontakta bankens spärrtjänst omedelbart.",
                    ]
                else:
                    advice = (
                        "Do not open the link, do not share your login details, and do not transfer money. This is a fraud attempt "
                        "designed to steal bank access or funds. Banks never ask for passwords or codes."
                    )
                    steps = [
                        "Never share passwords, PINs, or one-time codes with anyone.",
                        "Never transfer funds to a supposed 'safe account'.",
                        "If you already disclosed your details, call your bank's blocking service immediately.",
                    ]
            else:  # BENIGN
                risk_lvl = "none" if rec_action == "no_action_needed" else "routine"
                if lang == "fi":
                    advice = (
                        "Ilmoitus vaikuttaa tavanomaiselta pankin ilmoitukselta ilman epäilyttäviä linkkejä tai "
                        "pyyntöjä luovuttaa tunnuksia. Voit turvallisesti tarkistaa asian avaamalla oman verkkopankkisovelluksesi."
                    )
                    steps = [
                        "Avaa pankin virallinen sovellus suoraan puhelimestasi.",
                        "Älä käytä ulkopuolisia linkkejä kirjautumiseen.",
                    ]
                elif lang == "sv":
                    advice = (
                        "Meddelandet verkar vara ett normalt bankmeddelande utan misstänkta länkar eller begäran om "
                        "uppgifter. Du kan säkert kontrollera saken genom att öppna din officiella bankapp."
                    )
                    steps = [
                        "Öppna den officiella bankappen direkt på din telefon.",
                        "Använd inga externa länkar för inloggning.",
                    ]
                else:
                    if "password" in message.lower() or "reset" in message.lower():
                        advice = (
                            "This appears to be a legitimate password reset notification. If you initiated this reset, "
                            "you can proceed through the official service. If not, ignore the message and check your account "
                            "directly in your official banking app."
                        )
                        steps = [
                            "If you requested this reset, proceed through the official service.",
                            "If unexpected, ignore the message and verify your account in your official app.",
                        ]
                    elif any(w in message.lower() for w in ("card", "gold", "loan", "upgrade", "benefits")):
                        advice = (
                            "Inquiries about official card upgrades and loan benefits are standard banking services. "
                            "Since no passwords or security codes were requested, this is considered routine. You can safely "
                            "review and accept genuine offers inside your official mobile banking app."
                        )
                        steps = [
                            "Check for official card upgrades directly inside your banking app.",
                            "Never share passwords or verification codes over the phone.",
                        ]
                    else:
                        advice = (
                            "The communication matches a legitimate bank notification without suspicious external links "
                            "or requests for security codes. You can safely check the update by opening your official bank app."
                        )
                        steps = [
                            "Open your official mobile banking app directly on your device.",
                            "Never use external links to log in.",
                        ]

            candidate = {
                "case_id": session_id,
                "mode": "multi_turn",
                "risk_level": risk_lvl,
                "primary_action": rec_action,
                "urgency": "immediate" if risk_lvl in ("critical", "high") else "routine",
                "advice_text": advice,
                "steps": steps,
                "questions_asked": [],
                "question_topics": [],
                "escalation_required": False,
                "escalation_target": None,
                "citations": [d["id"] for d in rag_docs] or ["guidance_bank_impostor_call", "guidance_bank_verification"],
                "signals_used": ["artifact", "banking_validator"],
                "consent_requested_for": [],
                "confidence": 0.95,
                "abstained": False,
                "outcome_type": b_class,
                "banking_validation": banking_analysis,
            }

            final_ans, is_valid, _ = self.guard.verify_and_guard(candidate, lang=lang)
            save_decision(session_id, final_ans)
            add_message(session_id, role="assistant", msg_type="final", content=final_ans.get("advice_text", ""), user_id=user_id)

            return {
                "session_id": session_id,
                "reply_type": "final",
                "outcome_type": b_class,
                "user_language": lang,
                "text": final_ans.get("advice_text", ""),
                "text_en": (
                    "Do not disclose details or agree to offers on the call. An inbound caller claiming "
                    "to be from your bank cannot be verified by voice alone, as caller ID can be faked. "
                    "Verify the offer inside your official mobile banking app or call the bank using the number on your card."
                    if b_class == "INCONCLUSIVE" else final_ans.get("advice_text", "")
                ),
                "steps_primary": final_ans.get("steps", steps),
                "steps_en": [
                    "Never share codes, passwords, or card numbers over the phone.",
                    "Check for legitimate loan or card offers directly inside your bank app.",
                    "Call the bank using the number printed on the back of your card.",
                ] if b_class == "INCONCLUSIVE" else steps,
                "decision": final_ans,
                "banking_validation": banking_analysis,
                "rag_docs": [
                    {
                        "id": d["id"],
                        "title": d.get(f"title_{lang}", d.get("title_en", d.get("title_fi"))),
                        "excerpt": d.get(f"text_{lang}", d.get("text_en", d.get("text_fi")))[:160] + "...",
                        "title_en": d.get("title_en", d.get("title_fi")),
                        "excerpt_en": d.get("text_en", d.get("text_fi"))[:160] + "...",
                    } for d in rag_docs
                ],
            }

        # -------------------------------------------------------------
        # 7. Standard Incident Analysis & Decision Making
        # -------------------------------------------------------------
        case_dict = {
            "case_id": session_id,
            "opening_message": opening_text,
            "journey": journey,
            "audience": audience,
            "language": lang,
            "signals": {
                "artifact": {
                    "type": "sms" if journey == "suspicious_message" else "call" if journey == "suspicious_call" else "email",
                    "body": opening_text,
                    "links": links,
                },
                "link_check": {"verdict": "malicious"} if links else None,
                "subscription": {
                    "network_status": {"service": "no_service" if "ei kenttää" in opening_text.lower() else "normal"},
                },
                "device": {
                    "summary": {"platform": "mobile"},
                },
            },
        }

        ctx = fuse_signals(case_dict, active_facts)
        is_benign = is_benign_control(ctx)

        # Check for decisive question
        decisive = detect_decisive_question(ctx, active_facts)
        if decisive and not active_facts.get("user_answer"):
            topic, _ = decisive
            from src.decision.twin_resolver import QUESTIONS
            q_topic_dict = QUESTIONS.get(topic, {})
            q_primary = q_topic_dict.get(lang, q_topic_dict.get("en", "Can you provide more details?"))
            q_en = q_topic_dict.get("en", q_primary)
            
            add_message(session_id, role="assistant", msg_type="question", content=q_primary, user_id=user_id)
            return {
                "session_id": session_id,
                "reply_type": "question",
                "outcome_type": "INCONCLUSIVE",
                "user_language": lang,
                "text": q_primary,
                "text_en": q_en,
                "topic": topic,
                "rag_docs": [
                    {
                        "id": d["id"],
                        "title": d.get(f"title_{lang}", d.get("title_en", d.get("title_fi"))),
                        "excerpt": d.get(f"text_{lang}", d.get("text_en", d.get("text_fi")))[:160] + "...",
                        "title_en": d.get("title_en", d.get("title_fi")),
                        "excerpt_en": d.get("text_en", d.get("text_fi"))[:160] + "...",
                    } for d in rag_docs
                ],
            }

        # Final action resolution
        rec = self.selector.decide(ctx, active_facts, mode="multi_turn")

        # ML Threat Classifier assessment
        try:
            ml_res = self.classifier.assess(
                opening_text,
                signals=case_dict.get("signals"),
                answers=active_facts,
                language=lang,
                audience=audience,
            )
            if ml_res.get("tri_state_verdict") == "BENIGN":
                is_benign = True
                if ml_res.get("action") == "no_action_needed":
                    rec.primary_action = "no_action_needed"
                    rec.risk_level = "none"
        except Exception as ml_err:
            logger.warning("ThreatClassifier evaluation encountered: %s", ml_err)
            ml_res = {}

        advice_text_primary, steps_primary, _, _ = generate_response(
            ctx=ctx,
            action=rec.primary_action,
            required_steps=rec.required_steps,
            decisive_question=None,
            escalation_required=rec.escalation_required,
            escalation_target=rec.escalation_target,
        )

        ctx_en = copy.deepcopy(ctx)
        ctx_en.language = "en"
        advice_text_en, steps_en, _, _ = generate_response(
            ctx=ctx_en,
            action=rec.primary_action,
            required_steps=rec.required_steps,
            decisive_question=None,
            escalation_required=rec.escalation_required,
            escalation_target=rec.escalation_target,
        )

        outcome = "BENIGN" if is_benign else "SUSPICIOUS_OR_MALICIOUS"

        candidate = {
            "case_id": session_id,
            "mode": "multi_turn",
            "risk_level": rec.risk_level,
            "primary_action": rec.primary_action,
            "urgency": rec.urgency,
            "advice_text": advice_text_primary,
            "steps": steps_primary,
            "questions_asked": [],
            "question_topics": [],
            "escalation_required": rec.escalation_required,
            "escalation_target": rec.escalation_target,
            "citations": [d["id"] for d in rag_docs] or rec.citations,
            "signals_used": ["artifact"] + (["link_check"] if links else []),
            "consent_requested_for": [],
            "confidence": 0.95,
            "abstained": False,
            "outcome_type": outcome,
            "threat_classification": ml_res,
        }

        final_ans, is_valid, _ = self.guard.verify_and_guard(candidate, lang=lang)
        save_decision(session_id, final_ans)
        add_message(session_id, role="assistant", msg_type="final", content=final_ans.get("advice_text", ""), user_id=user_id)

        try:
            _repo.add_turn(session_id, turn_index=len(history)+1, role="assistant", content=final_ans.get("advice_text", ""), language=lang)
            _repo.record_decision_outcome(
                conversation_id=session_id,
                turn_index=len(history)+1,
                action=rec.primary_action,
                risk_level=rec.risk_level,
                urgency=rec.urgency,
                requires_specialist=bool(rec.escalation_required),
                escalation_target=rec.escalation_target,
            )
        except Exception:
            pass

        return {
            "session_id": session_id,
            "reply_type": "final",
            "outcome_type": outcome,
            "user_language": lang,
            "text": final_ans.get("advice_text", ""),
            "text_en": advice_text_en,
            "steps_primary": final_ans.get("steps", steps_primary),
            "steps_en": steps_en,
            "decision": final_ans,
            "rag_docs": [
                {
                    "id": d["id"],
                    "title": d.get(f"title_{lang}", d.get("title_en", d.get("title_fi"))),
                    "excerpt": d.get(f"text_{lang}", d.get("text_en", d.get("text_fi")))[:160] + "...",
                    "title_en": d.get("title_en", d.get("title_fi")),
                    "excerpt_en": d.get("text_en", d.get("text_fi"))[:160] + "...",
                } for d in rag_docs
            ],
        }

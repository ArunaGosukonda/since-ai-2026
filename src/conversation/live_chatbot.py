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
        from src.intelligence.security_analyzer import SecurityAnalyzer
        self.rag = _rag
        self.selector = _selector
        self.guard = _guard
        self.adversarial = _adversarial
        self.scope = _scope_enforcer
        self.banking = _banking_validator
        self.classifier = _classifier
        self.security_analyzer = SecurityAnalyzer()

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
        try:
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
        except Exception:
            pass

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
        # 3b. Educational Scenario Inquiries
        # -------------------------------------------------------------
        edu_res = self.security_analyzer._check_educational_inquiry(message, lang=lang)
        if edu_res:
            return {
                "session_id": session_id,
                "reply_type": "final",
                "outcome_type": edu_res.get("outcome_type", "BENIGN"),
                "user_language": lang,
                "text": edu_res.get("advice_text", ""),
                "text_en": edu_res.get("advice_text", ""),
                "steps_primary": edu_res.get("steps", []),
                "steps_en": edu_res.get("steps", []),
                "decision": edu_res,
                "rag_docs": [],
            }

        # -------------------------------------------------------------
        # 4. Record Incoming Turn & Retrieve Prior Session History
        # -------------------------------------------------------------
        try:
            add_message(session_id, role="user", msg_type="text", content=message, user_id=user_id)
            history = get_messages(session_id, user_id=user_id)
            facts = get_facts(session_id, user_id=user_id)
        except Exception:
            history = [{"role": "user", "content": message}]
            facts = {}

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
            try:
                set_fact(session_id, "user_answer", message)
                set_fact(session_id, "confirmed_risk", active_facts["confirmed_risk"])
            except Exception:
                pass
        else:
            journey = _detect_journey(message)
            opening_text = message
            active_facts = {}

        try:
            create_or_update_session(session_id, journey=journey, audience=audience, language=lang, user_id=user_id)
        except Exception:
            pass

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
                risk_lvl = "critical" if any(w in message.lower() for w in ("salasana", "password", "otp", "pin", "mfa", "credential", "remote", "koodi", "code")) else "high"
                if lang == "fi":
                    advice = (
                        "Älä luovuta salasanaa tai pankkitietoja soittajalle äläkä avaa linkkejä. Oikea pankki tai yritys "
                        "ei koskaan kysy salasanaa, PIN-koodia tai OTP-koodia puhelimessa. Sulje puhelu heti ja ota yhteys pankkiin virallisen numeron kautta."
                    )
                    steps = [
                        "Älä jaa salasanaasi soittajan kanssa.",
                        "Älä koskaan kerro kertakäyttökoodia, PIN-koodia tai vahvistuskoodia puhelussa.",
                        "Lopeta puhelu välittömästi, jos soittaja pyytää tunnuksia.",
                        "Ota yhteys pankkiisi sen virallista puhelinnumeroa tai sovellusta käyttäen.",
                        "Jos olet jo luovuttanut tietoja, soita heti pankkisi sulkupalveluun ja suojaa tilisi.",
                    ]
                elif lang == "sv":
                    advice = (
                        "Dela inte ditt lösenord eller dina inloggningsuppgifter med den som ringer. En legitim bank eller "
                        "organisation frågar ALDRIG efter ditt lösenord, din PIN-kod eller engångskod via telefon. Lägg på omedelbart."
                    )
                    steps = [
                        "Dela inte ditt lösenord med den som ringer.",
                        "Uppge aldrig engångskod, PIN-kod eller BankID-kod i ett telefonsamtal.",
                        "Avsluta samtalet omedelbart om uppringaren ber om inloggningsuppgifter.",
                        "Kontakta din bank via det officiella numret eller öppna bankens officiella app självständigt.",
                        "Om du redan har delat uppgifter, kontakta bankens spärrtjänst omedelbart.",
                    ]
                else:
                    advice = (
                        "Do not share your password or authentication credentials with the caller. A legitimate bank or company "
                        "NEVER asks for your password, PIN, or OTP over the phone. End the call immediately if the caller "
                        "is asking for credentials, and contact your bank using the official number."
                    )
                    steps = [
                        "Do not share your password with the caller.",
                        "Never disclose your OTP, PIN, MFA code or other authentication credentials over a call.",
                        "End the call if the caller is asking for credentials.",
                        "Contact your bank using the official number or open its official app or website independently.",
                        "If you already shared credentials, contact the bank immediately and secure your account.",
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
            try:
                save_decision(session_id, final_ans)
                add_message(session_id, role="assistant", msg_type="final", content=final_ans.get("advice_text", ""), user_id=user_id)
            except Exception:
                pass

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
            
            try:
                add_message(session_id, role="assistant", msg_type="question", content=q_primary, user_id=user_id)
            except Exception:
                pass
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

        # Detect link presence or link mentions in the message
        has_link_mention = bool(links) or bool(re.search(
            r"\b(link|linkki|länk|url|linkin|linkistä|linkkiä|linkkini|website|sivusto|osoite)\b",
            opening_text,
            re.IGNORECASE,
        ))
        is_initiated_reset = bool(re.search(
            r"(?:password\s*reset|salasanan\s*palautus|reset\s*link|palautuslinkki|resetointi)",
            opening_text,
            re.IGNORECASE,
        ))

        # ML Threat Classifier assessment
        try:
            ml_res = self.classifier.assess(
                opening_text,
                signals=case_dict.get("signals"),
                answers=active_facts,
                language=lang,
                audience=audience,
            )
            if ml_res.get("tri_state_verdict") == "BENIGN" and not (has_link_mention and not is_initiated_reset):
                is_benign = True
                if ml_res.get("action") == "no_action_needed":
                    rec.primary_action = "no_action_needed"
                    rec.risk_level = "none"
        except Exception as ml_err:
            logger.warning("ThreatClassifier evaluation encountered: %s", ml_err)
            ml_res = {}

        # Post-Incident & Link Security Enforcement:
        has_malware = bool(re.search(
            r"(?:malware|virus|trojan|spyware|haittaohjelma|skadlig\s*kod|infected|saastunut|tartunta|hack|kaapattu)",
            opening_text,
            re.IGNORECASE,
        ))
        has_post_action = journey in ("clicked_link", "incident") or bool(re.search(
            r"(?:clicked|klikkasin|klickade|opened|avasin|oppnade|downloaded|installed|latasin|asensin|laddade|entered|syotin|skrev\s+in|gave|annoin|shared)",
            opening_text,
            re.IGNORECASE,
        ))

        if has_malware:
            is_benign = False
            rec.primary_action = "isolate_device_and_scan"
            rec.risk_level = "critical"
            rec.urgency = "immediate"
            rec.required_steps = ["avoid_banking_on_device", "contact_bank_now", "disconnect_device", "remove_app_or_profile"]
            outcome = "SUSPICIOUS_OR_MALICIOUS"
            if lang == "fi":
                advice_text_primary = (
                    "Älä käytä verkkopankkia tällä laitteella ennen kuin se on tarkistettu. Epäilyttävästä "
                    "linkistä ladattu ohjelma voi seurata viestejä ja koodeja. Laita laite heti lentotilaan tai "
                    "katkaise verkkoyhteys. Ota yhteys pankkiisi, jos olet käyttänyt pankkipalveluita laitteella."
                )
                steps_primary = [
                    "Älä käytä verkkopankkia tällä laitteella ennen kuin se on tarkistettu.",
                    "Ota heti yhteys pankkiisi ja kerro mitä tapahtui.",
                    "Laita laite lentotilaan tai katkaise verkkoyhteys.",
                    "Poista asennettu ohjelma tai sovellus.",
                ]
            elif lang == "sv":
                advice_text_primary = (
                    "Använd inte nätbanken på den enheten förrän den har kontrollerats. Ett program från en "
                    "länk kan läsa dina meddelanden och koder. Slå på flygplansläge eller koppla från internet omedelbart. "
                    "Kontakta din bank om du använt banktjänster på enheten."
                )
                steps_primary = [
                    "Använd inte nätbanken på den enheten förrän den har kontrollerats.",
                    "Ring din bank omedelbart och berätta vad som hänt.",
                    "Slå på flygplansläge eller koppla från internet.",
                    "Ta bort programmet eller appen som installerades.",
                ]
            else:
                advice_text_primary = (
                    "Do not use online banking on that device until it is checked. An app or program from an "
                    "unverified link can read your messages and security codes. Turn on flight mode or disconnect from "
                    "the internet immediately. Call your bank now if you accessed banking services on the device."
                )
                steps_primary = [
                    "Do not use online banking on that device until it is checked.",
                    "Call your bank now and tell them what happened.",
                    "Turn on flight mode or disconnect the device from the internet.",
                    "Remove the app or program that was installed.",
                ]
            advice_text_en = (
                "Do not use online banking on that device until it is checked. An app or program from an "
                "unverified link can read your messages and security codes. Turn on flight mode or disconnect from "
                "the internet immediately. Call your bank now if you accessed banking services on the device."
            )
            steps_en = [
                "Do not use online banking on that device until it is checked.",
                "Call your bank now and tell them what happened.",
                "Turn on flight mode or disconnect the device from the internet.",
                "Remove the app or program that was installed.",
            ]
        elif has_post_action and has_link_mention and not is_initiated_reset:
            is_benign = False
            rec.primary_action = "verify_via_official_channel"
            rec.risk_level = "medium"
            rec.urgency = "today"
            rec.required_steps = ["verify_official_channel"]
            outcome = "INCONCLUSIVE"
            if lang == "fi":
                advice_text_primary = (
                    "Koska avasit linkin, sulje sivu äläkä syötä salasanoja, koodeja tai korttitietoja. "
                    "Tarkista asia suoraan palvelun virallisesta sovelluksesta tai virallisilta verkkosivuilta. "
                    "Jos syötit pankkitietoja, ota heti yhteys pankkisi sulkupalveluun."
                )
                steps_primary = [
                    "Sulje sivu äläkä syötä tunnuksia tai koodeja.",
                    "Tarkista asia virallisesta sovelluksesta tai viralliselta sivustolta.",
                    "Jos luovutit pankkitietoja, soita heti pankkisi sulkupalveluun.",
                ]
            elif lang == "sv":
                advice_text_primary = (
                    "Eftersom du öppnade länken, stäng sidan och ange inga koder eller lösenord. "
                    "Kontrollera saken i den officiella appen eller på den officiella webbplatsen. "
                    "Om du angav bankuppgifter, kontakta bankens spärrtjänst omedelbart."
                )
                steps_primary = [
                    "Stäng sidan och ange inga lösenord eller koder.",
                    "Kontrollera ärendet i den officiella appen eller på webbplatsen.",
                    "Om du lämnat ut bankuppgifter, kontakta bankens spärrtjänst omedelbart.",
                ]
            else:
                advice_text_primary = (
                    "Since you clicked the link, close the page and do not enter passwords, security codes, or card details. "
                    "Check the matter directly in the official app or on the official website. "
                    "If you entered any codes or passwords, call your bank immediately."
                )
                steps_primary = [
                    "Close the page and do not enter any codes or passwords.",
                    "Check the matter in the official app or on the official website.",
                    "If you entered bank details, call your bank's blocking service immediately.",
                ]
            advice_text_en = (
                "Since you clicked the link, close the page and do not enter passwords, security codes, or card details. "
                "Check the matter directly in the official app or on the official website. "
                "If you entered any codes or passwords, call your bank immediately."
            )
            steps_en = [
                "Close the page and do not enter any codes or passwords.",
                "Check the matter in the official app or on the official website.",
                "If you entered bank details, call your bank's blocking service immediately.",
            ]
        elif has_link_mention and not is_initiated_reset:
            is_benign = False
            rec.primary_action = "verify_via_official_channel"
            rec.risk_level = "medium"
            rec.urgency = "today"
            rec.required_steps = ["dont_open_link", "verify_official_channel"]
            outcome = "INCONCLUSIVE"
            if lang == "fi":
                advice_text_primary = (
                    "Älä avaa linkkiä odottamattomasta viestistä. Linkit voivat johtaa väärennetyille "
                    "kirjautumissivuille, joilla kalastellaan henkilötietoja tai pankkitunnuksia. "
                    "Jos viesti väittää olevansa pankista tai tunnetulta organisaatiolta, tarkista asia "
                    "virallisesta sovelluksesta tai organisaation omilta verkkosivuilta."
                )
                steps_primary = [
                    "Älä avaa linkkiä äläkä kirjaudu sen kautta.",
                    "Tarkista asia virallisesta sovelluksesta tai organisaation omilta verkkosivuilta.",
                    "Älä koskaan luovuta koodeja tai salasanoja ulkoisten linkkien kautta.",
                ]
            elif lang == "sv":
                advice_text_primary = (
                    "Öppna inte länkar i oväntade meddelanden. Länkar kan leda till falska "
                    "inloggningssidor som försöker stjäla bankuppgifter eller personlig information. "
                    "Kontrollera alltid saken i den officiella appen eller på organisationens egen webbplats."
                )
                steps_primary = [
                    "Öppna inte länken och logga inte in via den.",
                    "Kontrollera saken i den officiella appen eller på organisationens egen webbplats.",
                    "Dela aldrig koder eller lösenord via externa länkar.",
                ]
            else:
                advice_text_primary = (
                    "Do not open links in unexpected messages. Links can lead to fake login pages "
                    "designed to steal personal details or bank access. If this message claims to be "
                    "from your bank or an organisation, check the matter directly in their official app "
                    "or on their official website instead of tapping the link."
                )
                steps_primary = [
                    "Do not open or click the link in the message.",
                    "Check the matter in the official app or on the organisation's own website.",
                    "Never enter banking codes, passwords, or personal details through external links.",
                ]
            advice_text_en = (
                "Do not open links in unexpected messages. Links can lead to fake login pages "
                "designed to steal personal details or bank access. If this message claims to be "
                "from your bank or an organisation, check the matter directly in their official app "
                "or on their official website instead of tapping the link."
            )
            steps_en = [
                "Do not open or click the link in the message.",
                "Check the matter in the official app or on the organisation's own website.",
                "Never enter banking codes, passwords, or personal details through external links.",
            ]
        else:
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
        try:
            save_decision(session_id, final_ans)
            add_message(session_id, role="assistant", msg_type="final", content=final_ans.get("advice_text", ""), user_id=user_id)
        except Exception:
            pass

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

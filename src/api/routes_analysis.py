# -*- coding: utf-8 -*-
"""Real-time Security Analysis and Message Classification Routes for Since AI.

Powers the phone simulator's live voice call transcription meter,
call scam verdict alert dialog, and SMS inbox threat classification.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from src.classifier import get_threat_classifier
from src.intelligence.banking_validator import BankingValidator
from src.security.adversarial_detector import AdversarialDetector
from src.security.output_guard import OutputSecurityGate
from src.security.scope_enforcer import ScopeEnforcer

logger = logging.getLogger(__name__)

_banking_validator = BankingValidator()
_classifier = get_threat_classifier()
_output_guard = OutputSecurityGate()
_adversarial = AdversarialDetector()
_scope_enforcer = ScopeEnforcer()

# Danger phrases to flag and underline in call transcript
DANGER_PATTERNS = [
    (r"(?:read.*codes?|give.*codes?|share.*codes?|send.*codes?|codes?.*banking\s*app|tunnusluku|salasana|koodi[a-z]*)", "asking for security codes"),
    (r"(?:suspicious payments?|nine hundred euros|epäilyttäviä maksuja|900 euroa)", "alleged suspicious account activity"),
    (r"(?:hurry|ten minutes|kymmenen minuuttia|kiire)", "urgency and artificial pressure"),
    (r"(?:don't tell anyone|don't call the bank|älä kerro kenellekään|älä soita pankkiin)", "isolation and secrecy trick"),
    (r"(?:safe account|turvatili)", "safe account lure"),
    (r"(?:anydesk|teamviewer|remote access|etätuki)", "remote access demand"),
]


def handle_analyze_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes a single spoken sentence or ongoing call transcript.
    
    Expected input:
    {
        "kind": "call" | "sms",
        "text": "sentence",
        "transcript_so_far": "whole transcript",
        "caller_signals": { ... },
        "lang": "en" | "fi" | "sv"
    }
    """
    kind = req.get("kind", "call")
    text = str(req.get("text") or req.get("sentence") or req.get("message") or "").strip()
    so_far = str(req.get("transcript_so_far", "")).strip()
    full_text = (so_far + " " + text).strip()
    lang = req.get("lang", "en")
    caller_signals = req.get("caller_signals", {})

    t_lower = full_text.lower()

    # Detect danger phrases in current sentence
    flagged_phrases: List[str] = []
    for pat, _ in DANGER_PATTERNS:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            if isinstance(m, str) and m not in flagged_phrases:
                flagged_phrases.append(m)

    # 1. Critical Ask: Passwords, OTP codes, or banking app codes requested
    asks_codes = bool(re.search(
        r"(?:read.*codes?|give.*codes?|send.*codes?|share.*codes?|codes?.*banking\s*app|koodi|salasana|tunnusluku)",
        t_lower,
        re.IGNORECASE,
    ))
    asks_money = bool(re.search(
        r"(?:safe\s*account|turvatil|transfer\s*(?:money|funds)|siirrä\s*rahaa)",
        t_lower,
        re.IGNORECASE,
    ))

    # 2. Banking claim from unverified inbound caller
    claims_bank = bool(re.search(
        r"(?:bank|pankki|security\s*department|turvaosasto|revontuli)",
        t_lower,
        re.IGNORECASE,
    )) or bool(caller_signals.get("claims_identity", False))

    if asks_codes or asks_money:
        stage = "scam"
        risk_level = "critical"
        action = "contact_bank_and_block_cards"
        outcome_type = "SUSPICIOUS_OR_MALICIOUS"
        reason_en = "The caller claims to be from your bank and asks for your codes. A bank never asks for codes on the phone."
        reason_fi = "Soittaja väittää olevansa pankista ja pyytää koodeja. Pankki ei koskaan kysy koodeja puhelimessa."
        reason_sv = "Inringaren påstår sig vara från banken och ber om koder. En bank ber aldrig om koder på telefon."
        verdict_title = "This could be a scam. You should hang up." if lang == "en" else "Tämä voi olla huijaus. Sulje puhelu heti."
    elif claims_bank or bool(re.search(r"(?:suspicious payments?|account|payments)", t_lower, re.IGNORECASE)):
        stage = "careful"
        risk_level = "medium"
        action = "verify_via_official_channel"
        outcome_type = "INCONCLUSIVE"
        reason_en = "An inbound caller claiming to be from your bank cannot be verified by voice alone. Caller ID can be faked."
        reason_fi = "Pankin nimissä tulevaa puhelua ei voi varmistaa pelkän puheen perusteella. Soittajan numero voi olla väärennetty."
        reason_sv = "Ett inkommande samtal från banken kan inte bekräftas enbart på rösten. Telefonnumret kan vara förfalskat."
        verdict_title = "Unknown caller. Be careful." if lang == "en" else "Tuntematon soittaja. Ole varovainen."
    else:
        stage = "listening"
        risk_level = "none"
        action = "no_action_needed"
        outcome_type = "BENIGN"
        reason_en = "Listening to call for security indicators."
        reason_fi = "Kuunnellaan puhelua turvallisuuden varmistamiseksi."
        reason_sv = "Lyssnar på samtalet för att upptäcka risker."
        verdict_title = "Call in progress"

    reason_dict = {
        "en": reason_en,
        "fi": reason_fi,
        "sv": reason_sv,
    }

    return {
        "stage": stage,
        "risk_level": risk_level,
        "flagged_phrases": flagged_phrases,
        "flags": flagged_phrases,
        "reason": reason_dict,
        "action": action,
        "outcome_type": outcome_type,
        "verdict_title": verdict_title,
        "verdict_reason": reason_dict.get(lang, reason_en),
        "safe_next_step": "Hang up and check your official banking app directly.",
    }


def handle_classify_sms(req: Dict[str, Any]) -> Dict[str, Any]:
    """Classifies an SMS text message, chat description, or call transcript using the DSA pipeline and BankingValidator.
    
    Expected input:
    {
        "sender": "Unknown",
        "body": "message text",
        "lang": "en" | "fi" | "sv",
        "mode": "sms" | "chat" | "call"
    }
    """
    sender = str(req.get("sender", "Unknown"))
    body = str(req.get("body") or req.get("message") or req.get("text") or "").strip()
    lang = req.get("lang", "en")
    mode = str(req.get("mode", "sms"))
    links = re.findall(r"https?://[^\s]+", body)

    # 1. Adversarial & Information Extraction Security Check (Categories 3, 4, 5, 7, 8)
    is_attack, attack_cat, attack_reason = _adversarial.scan_for_attacks(body)
    if is_attack:
        refusal = _adversarial.format_refusal_response(lang=lang)
        adv = refusal["text"]
        return {
            "risk_level": "low",
            "urgency": "routine",
            "primary_action": "security_policy_refusal",
            "verdict": "WARNING",
            "outcome_type": "SECURITY_POLICY_REFUSAL",
            "advice_text": adv,
            "advice": adv,
            "steps": refusal["steps_primary"],
            "situation_id": "SEC-POLICY-REFUSAL",
            "questions_asked": [],
            "question_topics": [],
            "consent_requested_for": [],
            "escalation_required": False,
            "escalation_target": None,
            "citations": [],
            "signals_used": ["adversarial_detector"],
            "confidence": 1.0,
            "trace": {"situation_id": "SEC-POLICY-REFUSAL", "facts_used": [], "rule_ids": ["POLICY:adversarial_defense"]},
            "facts": {},
        }

    # 2. Out-of-Scope Enforcement (Category 2)
    has_link = bool(links) or bool(re.search(
        r"\b(link|linkki|länk|url|website|sivusto|osoite)\b",
        body,
        re.IGNORECASE,
    ))
    if mode in ("chat", "call") or not has_link:
        is_in_scope, out_topic, _ = _scope_enforcer.evaluate_scope(body)
        if not is_in_scope:
            out_resp = _scope_enforcer.format_out_of_scope_response(topic=out_topic or "general", lang=lang)
            adv = out_resp["text"]
            return {
                "risk_level": "routine",
                "urgency": "routine",
                "primary_action": "out_of_scope_redirect",
                "verdict": "SAFE",
                "outcome_type": "OUT_OF_SCOPE",
                "advice_text": adv,
                "advice": adv,
                "steps": out_resp["steps_primary"],
                "situation_id": "OUT-OF-SCOPE",
                "questions_asked": [],
                "question_topics": [],
                "consent_requested_for": [],
                "escalation_required": False,
                "escalation_target": None,
                "citations": [],
                "signals_used": ["scope_enforcer"],
                "confidence": 1.0,
                "trace": {"situation_id": "OUT-OF-SCOPE", "facts_used": [], "rule_ids": ["POLICY:scope_redirect"]},
                "facts": {},
            }

    # 3. Banking Communication & Tri-State Security Evaluation (Categories 1 & 6)
    sender_verified = bool(req.get("sender_identity_verified", False))
    b_res = _banking_validator.analyze_banking_communication(
        body,
        links=links,
        channel=mode,
        sender_identity_verified=sender_verified,
    )
    if b_res:
        classification = b_res["classification"]
        if classification == "BENIGN":
            risk = "none"
            verdict = "SAFE"
            urgency = "routine"
        elif classification == "INCONCLUSIVE":
            risk = "medium"
            verdict = "WARNING"
            urgency = "today"
        else:  # SUSPICIOUS_OR_MALICIOUS
            risk = "critical"
            verdict = "SUSPICIOUS"
            urgency = "immediate"

        adv = b_res.get("explanation", "")
        adv = re.sub(r"\bspoofed\b", "faked", adv, flags=re.IGNORECASE)
        adv = re.sub(r"\bcredentials\b", "login details", adv, flags=re.IGNORECASE)
        safe_step = b_res.get("safe_next_step", "")
        steps = [adv]
        if safe_step:
            steps.append(safe_step)

        return {
            "risk_level": risk,
            "urgency": urgency,
            "primary_action": b_res.get("recommended_action", "verify_via_official_channel"),
            "verdict": verdict,
            "outcome_type": classification,
            "advice_text": adv,
            "advice": adv,
            "steps": steps,
            "situation_id": f"BANK-{classification}",
            "questions_asked": [],
            "question_topics": [],
            "consent_requested_for": [],
            "escalation_required": False,
            "escalation_target": None,
            "citations": [],
            "signals_used": ["banking_validator"],
            "confidence": 0.95,
            "trace": {"situation_id": f"BANK-{classification}", "facts_used": [], "rule_ids": [f"BANK:{classification}"]},
            "facts": {},
        }

    # 4. Run official DSA pipeline
    res = None
    try:
        from tools import classify_message
        clean_req = dict(req)
        clean_req["body"] = body
        clean_req["sender"] = sender
        clean_req["lang"] = lang
        clean_req.setdefault("mode", "sms")
        res = classify_message.run(clean_req)
    except Exception as e:
        logger.warning("classify_message execution failed: %s", e)

    # 5. Strict Link & Incident Security Enforcement:
    # A. Active malware or device compromise from a link -> CRITICAL risk (isolate device and scan)
    has_malware = bool(re.search(
        r"(?:malware\w*|virus\w*|virukse\w*|trojan\w*|spyware\w*|haittaohjelm\w*|skadlig\w*\s+kod\w*|infected\w*|saastun\w*|tartun\w*|hack\w*)",
        body,
        re.IGNORECASE,
    ))
    if has_malware and (not res or res.get("risk_level") != "critical"):
        if res is None:
            res = {}
        res["risk_level"] = "critical"
        res["urgency"] = "immediate"
        res["primary_action"] = "isolate_device_and_scan"
        res["situation_id"] = "S07"
        res["outcome_type"] = "SUSPICIOUS_OR_MALICIOUS"
        if lang == "fi":
            res["advice_text"] = "Älä käytä verkkopankkia tällä laitteella ennen kuin se on tarkistettu. Epäilyttävästä linkistä ladattu ohjelma voi seurata viestejä ja koodeja. Laita laite heti lentotilaan tai katkaise verkkoyhteys. Ota yhteys pankkiisi, jos olet käyttänyt pankkipalveluita laitteella."
            res["steps"] = [
                "Älä käytä verkkopankkia tällä laitteella ennen kuin se on tarkistettu.",
                "Ota heti yhteys pankkiisi ja kerro mitä tapahtui.",
                "Laita laite lentotilaan tai katkaise verkkoyhteys.",
                "Poista asennettu ohjelma tai sovellus.",
            ]
        elif lang == "sv":
            res["advice_text"] = "Använd inte nätbanken på den enheten förrän den har kontrollerats. Ett program från en länk kan läsa dina meddelanden och koder. Slå på flygplansläge eller koppla från internet omedelbart. Kontakta din bank om du använt banktjänster på enheten."
            res["steps"] = [
                "Använd inte nätbanken på den enheten förrän den har kontrollerats.",
                "Ring din bank omedelbart och berätta vad som hänt.",
                "Slå på flygplansläge eller koppla från internet.",
                "Ta bort programmet eller appen som installerades.",
            ]
        else:
            res["advice_text"] = "Do not use online banking on that device until it is checked. An app from a link can read your messages and codes. Call your bank now and tell them what happened. Turn on flight mode or disconnect the device from the internet. Remove the app or program that was installed."
            res["steps"] = [
                "Do not use online banking on that device until it is checked.",
                "Call your bank now and tell them what happened.",
                "Turn on flight mode or disconnect the device from the internet.",
                "Remove the app or program that was installed.",
            ]

    # B. Link security: Unopened SMS with link vs. Post-click chat inquiry
    is_initiated_reset = bool(re.search(r"(?:my\s+password\s+reset|requested\s+password|tilasin\s+salasanan)", body, re.IGNORECASE))
    is_chat_or_incident = req.get("mode") in ("chat", "call") or bool(re.search(
        r"(?:clicked|klikkasin|klickade|opened|avasin|oppnade|downloaded|installed|latasin|asensin|laddade|entered|syotin|skrev\s+in|gave|annoin|shared)",
        body,
        re.IGNORECASE,
    ))

    if has_link and not is_initiated_reset and not has_malware:
        if not is_chat_or_incident:
            # Unopened incoming SMS: always warn user not to open unexpected link -> INCONCLUSIVE
            if not res or res.get("risk_level") in ("none", "low", "routine"):
                if res is None:
                    res = {}
                res["risk_level"] = "medium"
                res["urgency"] = "today"
                res["primary_action"] = "verify_via_official_channel"
                adv = (
                    "Do not open links in unexpected messages. Check the matter in the service's official app or on their own website."
                    if lang == "en" else
                    "Älä avaa linkkiä odottamattomasta viestistä. Tarkista asia palvelun virallisesta sovelluksesta tai omilta verkkosivuilta."
                )
                res["advice_text"] = adv
                res["situation_id"] = "SM-UNVERIFIED-LINK"
                res["outcome_type"] = "INCONCLUSIVE"
                res["steps"] = [
                    "Do not open or click the link in the message.",
                    "Check the matter in the official app or on the organisation's own website.",
                    "Never enter banking codes, passwords, or personal details through external links.",
                ]
        else:
            # User reports already clicking link in chat: warn about credential/code exposure -> INCONCLUSIVE
            if not res or res.get("risk_level") in ("none", "low", "routine"):
                if res is None:
                    res = {}
                res["risk_level"] = "medium"
                res["urgency"] = "today"
                res["primary_action"] = "verify_via_official_channel"
                res["situation_id"] = "S03"
                res["outcome_type"] = "INCONCLUSIVE"
                if lang == "fi":
                    res["advice_text"] = "Koska avasit linkin, sulje sivu äläkä syötä salasanoja, koodeja tai korttitietoja. Tarkista asia suoraan palvelun virallisesta sovelluksesta tai virallisilta verkkosivuilta. Jos syötit pankkitietoja, ota heti yhteys pankkisi sulkupalveluun."
                    res["steps"] = [
                        "Sulje sivu äläkä syötä tunnuksia tai koodeja.",
                        "Tarkista asia virallisesta sovelluksesta tai viralliselta sivustolta.",
                        "Jos luovutit pankkitietoja, soita heti pankkisi sulkupalveluun.",
                    ]
                elif lang == "sv":
                    res["advice_text"] = "Eftersom du öppnade länken, stäng sidan och ange inga koder eller lösenord. Kontrollera saken i den officiella appen eller på den officiella webbplatsen. Om du angav bankuppgifter, kontakta bankens spärrtjänst omedelbart."
                    res["steps"] = [
                        "Stäng sidan och ange inga lösenord eller koder.",
                        "Kontrollera ärendet i den officiella appen eller på webbplatsen.",
                        "Om du lämnat ut bankuppgifter, kontakta bankens spärrtjänst omedelbart.",
                    ]
                else:
                    res["advice_text"] = "Since you clicked the link, close the page and do not enter passwords, security codes, or card details. Check the matter directly in the official app or on the official website. If you entered any codes or passwords, call your bank immediately."
                    res["steps"] = [
                        "Close the page and do not enter any codes or passwords.",
                        "Check the matter in the official app or on the official website.",
                        "If you entered bank details, call your bank's blocking service immediately.",
                    ]

    if not res:
        res = {
            "risk_level": "medium",
            "urgency": "today",
            "primary_action": "verify_via_official_channel",
            "advice_text": "Be cautious with unexpected communications. Verify directly in the official app.",
            "situation_id": "SM-GENERAL",
            "outcome_type": "INCONCLUSIVE",
        }

    # Ensure full Decision contract format for TanStack Start assess()
    r_lvl = res.get("risk_level", "medium")
    res["verdict"] = "SAFE" if r_lvl in ("none", "routine") else ("WARNING" if r_lvl == "medium" else "SUSPICIOUS")
    if "outcome_type" not in res:
        res["outcome_type"] = "BENIGN" if r_lvl in ("none", "routine") else ("INCONCLUSIVE" if r_lvl == "medium" else "SUSPICIOUS_OR_MALICIOUS")
    res["advice"] = res.get("advice_text", "")
    res.setdefault("steps", [res.get("advice_text", "")])
    res.setdefault("questions_asked", [])
    res.setdefault("question_topics", [])
    res.setdefault("consent_requested_for", [])
    res.setdefault("escalation_required", False)
    res.setdefault("escalation_target", None)
    res.setdefault("citations", [])
    res.setdefault("signals_used", ["artifact"])
    res.setdefault("confidence", 0.95)
    res.setdefault("trace", {"situation_id": res.get("situation_id", "S00"), "facts_used": [], "rule_ids": []})
    res.setdefault("facts", {})
    return res

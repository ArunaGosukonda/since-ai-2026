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
from src.security.output_guard import OutputSecurityGate

logger = logging.getLogger(__name__)

_banking_validator = BankingValidator()
_classifier = get_threat_classifier()
_output_guard = OutputSecurityGate()

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
    """Classifies an SMS text message or call transcript using the DSA pipeline and BankingValidator.
    
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
    links = re.findall(r"https?://[^\s]+", body)

    # Check for link presence or mentions
    has_link = bool(links) or bool(re.search(
        r"\b(link|linkki|länk|url|website|sivusto|osoite)\b",
        body,
        re.IGNORECASE,
    ))

    # 1. Run official DSA pipeline
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

    # 2. Strict Link Security Enforcement:
    # An unexpected or unverified message containing or mentioning a link must never be none or low risk.
    is_initiated_reset = bool(re.search(r"(?:my\s+password\s+reset|requested\s+password|tilasin\s+salasanan)", body, re.IGNORECASE))
    if has_link and not is_initiated_reset:
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
            res["steps"] = [
                "Do not open or click the link in the message.",
                "Check the matter in the official app or on the organisation's own website.",
                "Never enter banking codes, passwords, or personal details through external links.",
            ]

    if not res:
        # Fallback to BankingValidator and ThreatClassifier
        b_res = _banking_validator.analyze_banking_communication(body, links=links)
        if b_res:
            classification = b_res["classification"]
            risk = "critical" if classification == "SUSPICIOUS_OR_MALICIOUS" else ("medium" if classification == "INCONCLUSIVE" else "none")
            urgency = "immediate" if risk == "critical" else ("today" if risk == "medium" else "routine")
            adv = b_res.get("explanation", "")
            adv = re.sub(r"\bspoofed\b", "faked", adv, flags=re.IGNORECASE)
            adv = re.sub(r"\bcredentials\b", "login details", adv, flags=re.IGNORECASE)
            res = {
                "risk_level": risk,
                "urgency": urgency,
                "primary_action": b_res.get("recommended_action", "verify_via_official_channel"),
                "advice_text": adv,
                "situation_id": "SM-BANKING-NOTICE",
            }
        else:
            res = {
                "risk_level": "medium",
                "urgency": "today",
                "primary_action": "verify_via_official_channel",
                "advice_text": "Be cautious with unexpected messages. Verify directly in the official app.",
                "situation_id": "SM-GENERAL",
            }

    # Ensure full Decision contract format for TanStack Start assess()
    r_lvl = res.get("risk_level", "medium")
    res["verdict"] = "SAFE" if r_lvl in ("none", "routine") else ("WARNING" if r_lvl == "medium" else "SUSPICIOUS")
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

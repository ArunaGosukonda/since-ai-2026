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
    """Classifies an SMS text message using BankingValidator and ThreatClassifier.
    
    Expected input:
    {
        "sender": "Unknown",
        "body": "message text",
        "lang": "en" | "fi" | "sv"
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

    # Evaluate with BankingValidator
    b_res = _banking_validator.analyze_banking_communication(body, links=links)
    if b_res:
        classification = b_res["classification"]
        if classification == "SUSPICIOUS_OR_MALICIOUS":
            risk = "critical"
            urgency = "immediate"
        elif classification == "INCONCLUSIVE":
            risk = "medium"
            urgency = "today"
        else:
            risk = "none"
            urgency = "routine"
        
        advice = b_res.get("explanation", "")
        # Filter jargon from emitted text
        advice = re.sub(r"\bspoofed\b", "faked", advice, flags=re.IGNORECASE)
        advice = re.sub(r"\bcredentials\b", "login details", advice, flags=re.IGNORECASE)

        verdict = "SAFE" if risk in ("none", "routine") else ("WARNING" if risk == "medium" else "SUSPICIOUS")
        return {
            "risk_level": risk,
            "verdict": verdict,
            "urgency": urgency,
            "primary_action": b_res.get("recommended_action", "verify_via_official_channel"),
            "advice_text": advice,
            "advice": advice,
            "situation_id": "SM-BANKING-NOTICE",
        }

    # Evaluate with ThreatClassifier ML
    try:
        t_res = _classifier.assess(body, language=lang)
    except Exception:
        t_res = {}

    t_verdict = t_res.get("tri_state_verdict")
    
    # Strict rule: Unverified link in a message must ALWAYS trigger a warning, never safe / none
    if has_link:
        if t_verdict == "SUSPICIOUS_OR_MALICIOUS" or bool(re.search(r"(?:pay|maksa|tulli|fee|avgift|urgent|suljetaan)", body, re.IGNORECASE)):
            adv = (
                "Do not open the link or reply to this message. This is a common scam designed to capture details or steal money."
                if lang == "en" else
                "Älä avaa linkkiä äläkä vastaa viestiin. Tämä on tyypillinen huijausviesti, jolla kalastellaan tietoja tai rahaa."
            )
            return {
                "risk_level": "high",
                "verdict": "SUSPICIOUS",
                "urgency": "today",
                "primary_action": "do_not_interact_and_delete",
                "advice_text": adv,
                "advice": adv,
                "situation_id": "SM-SUSPICIOUS-LINK",
            }
        else:
            adv = (
                "Do not open links in unexpected messages. Check the matter in the service's official app or on their own website."
                if lang == "en" else
                "Älä avaa linkkiä odottamattomasta viestistä. Tarkista asia palvelun virallisesta sovelluksesta tai omilta verkkosivuilta."
            )
            return {
                "risk_level": "medium",
                "verdict": "WARNING",
                "urgency": "today",
                "primary_action": "verify_via_official_channel",
                "advice_text": adv,
                "advice": adv,
                "situation_id": "SM-UNVERIFIED-LINK",
            }

    # No link, check if parcel pickup code or doctor reminder
    if bool(re.search(r"JJFI[0-9]+", body)) or bool(re.search(r"(?:doctor|lääkäri|library|kirjasto|appointment)", body, re.IGNORECASE)):
        adv = (
            "This message looks genuine and no action is needed."
            if lang == "en" else
            "Tämä viesti vaikuttaa aidolta eikä vaadi toimenpiteitä."
        )
        return {
            "risk_level": "none",
            "verdict": "SAFE",
            "urgency": "none",
            "primary_action": "no_action_needed",
            "advice_text": adv,
            "advice": adv,
            "situation_id": "SM-GENUINE-NOTICE",
        }

    # General suspicious message default
    r_lvl = t_res.get("risk_level", "medium")
    v_map = "SAFE" if r_lvl in ("none", "routine") else ("WARNING" if r_lvl == "medium" else "SUSPICIOUS")
    adv = (
        "Be cautious with unsolicited messages. Do not share codes or transfer money."
        if lang == "en" else
        "Ole varovainen odottamattomien viestien kanssa. Älä luovuta koodeja tai siirrä rahaa."
    )
    return {
        "risk_level": r_lvl,
        "verdict": v_map,
        "urgency": "today",
        "primary_action": t_res.get("action", "verify_via_official_channel"),
        "advice_text": adv,
        "advice": adv,
        "situation_id": "SM-GENERAL-CHECK",
    }

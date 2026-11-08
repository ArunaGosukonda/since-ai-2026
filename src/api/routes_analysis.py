# -*- coding: utf-8 -*-
"""Real-time Security Analysis and Message Classification Routes for Since AI.

Powers the phone simulator's live voice call transcription meter,
call scam verdict alert dialog, and SMS inbox threat classification.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from src.intelligence.security_analyzer import SecurityAnalyzer

logger = logging.getLogger(__name__)

_security_analyzer = SecurityAnalyzer()

# Danger phrases to flag and underline in call transcript
DANGER_PATTERNS = [
    (r"(?:read.*codes?|give.*codes?|share.*codes?|send.*codes?|codes?.*banking\s*app|tunnusluku|salasana|koodi[a-z]*|password|pin|otp|mfa|credential[s]?)", "asking for security credentials"),
    (r"(?:asks?|asked|asking|demands?|demanded|demanding|wants?|tell\s+me)\b.*?(?:password|pin|otp|code|mfa|credential|remote\s*access)", "credential extraction demand"),
    (r"(?:suspicious payments?|nine hundred euros|epäilyttäviä maksuja|900 euroa)", "alleged suspicious account activity"),
    (r"(?:hurry|ten minutes|kymmenen minuuttia|kiire|blocked\s+unless|immediately)", "urgency and artificial pressure"),
    (r"(?:don't tell anyone|don't call the bank|älä kerro kenellekään|älä soita pankkiin)", "isolation and secrecy trick"),
    (r"(?:safe account|turvatili)", "safe account lure"),
    (r"(?:anydesk|teamviewer|remote access|etätuki|quicksupport)", "remote access demand"),
]


def handle_analyze_request(req: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes a single spoken sentence or ongoing call transcript.
    
    Expected input:
    {
        "kind": "call" | "sms",
        "text": "sentence",
        "transcript_so_far": "whole transcript",
        "caller_signals": { ... },
        "lang": "en" | "fi" | "sv",
        "sender": "+358...",
        "sender_identity_verified": false
    }
    """
    kind = req.get("kind", req.get("type", "call"))
    text = str(req.get("text") or req.get("sentence") or req.get("message") or "").strip()
    so_far = str(req.get("transcript_so_far", "")).strip()
    if not text and req.get("history"):
        hist = req.get("history")
        if isinstance(hist, list):
            lines = [h.get("text", "") for h in hist if isinstance(h, dict)]
            if lines:
                text = lines[-1]
                if len(lines) > 1:
                    so_far = " ".join(lines[:-1])
    full_text = (so_far + " " + text).strip()
    lang = req.get("lang", "en")
    sender = str(req.get("sender") or req.get("caller") or "Unknown")
    sender_verified = bool(req.get("sender_identity_verified", False))

    analysis = _security_analyzer.analyze(
        text=text,
        channel=kind,
        sender=sender,
        lang=lang,
        sender_identity_verified=sender_verified,
        conversation_history=[so_far] if so_far else None,
    )
    outcome = analysis.get("outcome_type", "INCONCLUSIVE")
    risk_lvl = analysis.get("risk_level", "medium")
    action = analysis.get("primary_action", "verify_via_official_channel")

    if outcome == "SUSPICIOUS_OR_MALICIOUS" or risk_lvl in ("critical", "high"):
        stage = "scam"
    elif outcome == "INCONCLUSIVE" or risk_lvl == "medium":
        stage = "careful"
    elif outcome in ("OUT_OF_SCOPE", "SECURITY_POLICY_REFUSAL"):
        stage = "careful"
    else:
        stage = "listening"

    # Flagged phrases
    flagged_phrases: List[str] = []
    for pat, _ in DANGER_PATTERNS:
        matches = re.findall(pat, full_text, re.IGNORECASE)
        for m in matches:
            if isinstance(m, str) and m not in flagged_phrases:
                flagged_phrases.append(m)

    reason_text = analysis.get("advice_text", "")
    safe_step = analysis.get("steps", ["Hang up and verify via official app."])[0] if analysis.get("steps") else "Hang up and check official app."

    return {
        "stage": stage,
        "risk_level": risk_lvl,
        "flagged_phrases": flagged_phrases,
        "flags": flagged_phrases,
        "reason": {"en": reason_text, "fi": reason_text, "sv": reason_text},
        "action": action,
        "outcome_type": outcome,
        "verdict": analysis.get("verdict", "WARNING"),
        "verdict_title": "Scam Warning" if stage == "scam" else "Caution",
        "verdict_reason": reason_text,
        "safe_next_step": safe_step,
        "decision": analysis,
    }


def handle_classify_sms(req: Dict[str, Any]) -> Dict[str, Any]:
    """Classifies an SMS text message, chat description, or call transcript using the unified SecurityAnalyzer.
    
    Expected input:
    {
        "sender": "Unknown",
        "body": "message text",
        "lang": "en" | "fi" | "sv",
        "mode": "sms" | "chat" | "call",
        "sender_identity_verified": false,
        "conversation_history": [...]
    }
    """
    sender = str(req.get("sender", "Unknown"))
    body = str(req.get("body") or req.get("message") or req.get("text") or "").strip()
    lang = req.get("lang", "en")
    mode = str(req.get("mode", "sms"))
    sender_verified = bool(req.get("sender_identity_verified", False))
    history = req.get("conversation_history") or []
    if isinstance(history, str):
        history = [history]

    res = _security_analyzer.analyze(
        text=body,
        channel=mode,
        sender=sender,
        lang=lang,
        sender_identity_verified=sender_verified,
        conversation_history=history,
    )
    risk = res.get("risk_level", "none")
    if risk == "none":
        res["stage"] = "listening" if mode == "call" else "safe"
    elif risk == "low":
        res["stage"] = "neutral"
    elif risk == "medium":
        res["stage"] = "careful"
    else:
        res["stage"] = "scam"
    return res

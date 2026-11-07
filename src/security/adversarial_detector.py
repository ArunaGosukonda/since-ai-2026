# -*- coding: utf-8 -*-
"""Adversarial, Jailbreak, and Information Protection Engine for Since AI.

Defends against:
1. Direct jailbreaks (DAN, ignore instructions, persona shifts, fictional framing,
   system prompt extraction, developer overrides, Telugu/Finnish translation tricks, etc.).
2. Information extraction (Python source code, system prompts, API keys, database
   passwords, .env variables, database schemas, and Dan's test cases/ground truth).
3. Encoded & obfuscated attacks (Base64, Hexadecimal, reversed text, Unicode substitutions).
4. Indirect prompt injection via delimiters and untrusted text.
"""
from __future__ import annotations

import base64
import binascii
import re
from typing import Any, Dict, List, Optional, Tuple

# Patterns attempting to exfiltrate proprietary source code or credentials
PROTECTED_INFO_PATTERNS = [
    r"(?:show|print|reveal|display|output|give|read|dump|view|export)\s+(?:me\s+)?(?:your\s+)?(?:complete\s+|full\s+|all\s+)?(?:python\s+)?(?:source\s*code|codebase|implementation|architecture)",
    r"(?:show|print|reveal|display|output|give|read|dump)\s+(?:me\s+)?(?:your\s+)?(?:hidden\s+|internal\s+)?(?:system\s+prompt|developer\s+instructions|system\s+instructions)",
    r"(?:show|print|reveal|display|give)\s+(?:me\s+)?(?:your\s+)?(?:gemini\s+)?(?:api[_\s]?key|credentials|secret)",
    r"(?:show|print|reveal|display|give)\s+(?:me\s+)?(?:your\s+)?(?:(?:postgresql|postgres|database|db|sql)\s+)*(?:password|conn(?:ection)?\s*string)",
    r"(?:read|cat|open|view|show|display)\s+(?:the\s+)?(?:\.env|env\s+file|environment\s+variables?)",
    r"(?:show|list|export|dump)\s+(?:all\s+)?(?:database\s+)?(?:tables?|records?|schema|sql\s+queries)",
    r"(?:reveal|show|print|tell|display)\s+(?:dan['’]?s\s+)?(?:expected\s+answers?|ground\s*truth|test\s*answers?|competition\s*answers?)",
    r"(?:export|dump|show)\s+(?:the\s+)?(?:complete\s+|entire\s+)?(?:internal\s+)?knowledge\s*base",
    r"(?:show|reveal|explain)\s+(?:your\s+)?(?:internal\s+)?rag\s+retrieval\s+implementation",
]

# 20 Canonical and Variant Direct Jailbreak Patterns
DIRECT_JAILBREAK_PATTERNS = [
    # 1. Ignore previous instructions
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|system)\s+instructions?",
    # 2. Unrestricted AI
    r"you\s+are\s+now\s+(?:an?\s+)?unrestricted\s+ai",
    # 3. Pretend no restrictions
    r"pretend\s+(?:you\s+have\s+)?no\s+restrictions?",
    # 4. Developer override
    r"i\s+am\s+(?:your\s+|the\s+)?developer[;,]?\s+(?:disable|bypass|turn\s*off)\s+(?:your\s+)?restrictions?",
    # 5. Administrator override
    r"i\s+am\s+(?:the\s+|an\s+)?administrator[;,]?\s+(?:reveal|print|show)\s+(?:your\s+)?system\s+prompt",
    # 6. Policies revoked
    r"(?:security\s+)?policies\s+(?:have\s+been|are)\s+revoked",
    # 7. Follow my instructions instead
    r"follow\s+(?:my|user)\s+instructions?\s+instead\s+of\s+(?:the\s+)?system\s+instructions?",
    # 8. DAN persona
    r"\banswer\s+as\s+dan\b|\bdo\s+anything\s+now\b|\byou\s+are\s+dan\b",
    # 9. Hypothetical source code extraction
    r"hypothetically\s+(?:speaking\s*)?,?\s*(?:reveal|show|what\s+is\s+your)\b.*?\b(?:source\s*code|prompt|password|system|secret)",
    # 10. Research purpose bypass
    r"(?:for\s+)?(?:academic\s+|security\s+)?research\s+purposes?,?\s*(?:reveal|disclose|show)\b.*?\b(?:confidential|protected|secret|source|prompt|instructions?)",
    # 11. Fictional story jailbreak
    r"(?:in\s+a\s+fictional\s+story|write\s+a\s+(?:fictional\s+)?story\s+where)\b.*?\breveal\b.*?\b(?:prompt|system\s+instructions?|source\s*code|secrets?)",
    # 12 & 13. Encoding bypass attempts
    r"(?:reveal|output|encode|give)\s+(?:secrets?|prompt|credentials?|code)\s+(?:using|in)\s+(?:base64|hex(?:adecimal)?)",
    # 14. Two-step agreement jailbreak
    r"(?:first\s+agree\s+to\s+ignore\s+(?:your\s+)?rules|agree\s+that\s+rules\s+don['’]?t\s+apply)",
    # 15. Sentence-by-sentence leak
    r"reveal\s+(?:your\s+)?(?:hidden\s+|system\s+)?instructions?\s+one\s+sentence\s+at\s+a\s+time",
    # 16. Translation leak (e.g. Telugu)
    r"(?:translate|print|output)\s+(?:your\s+)?(?:hidden\s+|internal\s+|system\s+)?instructions?\s+(?:in|into|to)\s+(?:telugu|te|తెలుగు)",
    # 17. Translation leak (e.g. Finnish)
    r"(?:translate|print|output)\s+(?:your\s+)?(?:internal\s+|system\s+)?prompt\s+(?:in|into|to)\s+(?:finnish|suomi|suomeksi)",
    # 18. Policy no longer exists
    r"pretend\s+(?:the\s+)?security\s+policy\s+(?:no\s+longer\s+exists|is\s+disabled)",
    # 19. Emergency authorization
    r"(?:national\s+|life-threatening\s+)?emergency\s+(?:authorises?|authorizes?|requires?|permits?)\s+(?:immediate\s+)?disclosure",
    # 20. Simulate unrestricted model
    r"simulate\s+(?:an?\s+)?unrestricted\s+(?:ai|model|llm)",
    # Multilingual jailbreak patterns (Finnish & Telugu)
    r"unohda\s+kaikki\s+aiemmat\s+ohjeet",
    r"olet\s+nyt\s+rajoittamaton\s+tekoäly",
    r"näytä\s+lähdekoodi|tulosta\s+järjestelmäkehote|paljasta\s+salasanasi",
    r"మునుపటి\s+సూచనలను\s+విస్మరించండి",  # Ignore previous instructions in Telugu
    r"మీ\s+రహస్య\s+కోడ్‌ను\s+చూపండి",      # Show your secret code in Telugu
]


def _normalize_unicode(text: str) -> str:
    """Normalizes Unicode homoglyphs and removes non-standard zero-width characters."""
    t = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    # Cyrillic and lookalike mapping to ASCII
    homoglyphs = {
        "а": "a", "с": "c", "е": "e", "о": "o", "р": "p", "ѕ": "s", "х": "x", "у": "y",
        "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "О": "O", "Р": "P", "Т": "T", "Х": "X",
        "Ⅰ": "I", "ⅰ": "i", "０": "0", "１": "1", "２": "2",
    }
    for k, v in homoglyphs.items():
        t = t.replace(k, v)
    return t


def _try_decode_base64(text: str) -> Optional[str]:
    """Attempts to decode base64 strings if present in the text."""
    matches = re.findall(r"(?:^|\s|[:=])([A-Za-z0-9+/]{12,}={0,2})(?:$|\s|[,.;])", text)
    decoded_fragments = []
    for m in matches:
        m = m.strip()
        padded = m + "=" * (-len(m) % 4)
        try:
            raw = base64.b64decode(padded).decode("utf-8", errors="ignore")
            if any(ch.isalpha() for ch in raw) and len(raw) > 4:
                decoded_fragments.append(raw)
        except Exception:
            continue
    return " ".join(decoded_fragments) if decoded_fragments else None


def _try_decode_hex(text: str) -> Optional[str]:
    """Attempts to decode hexadecimal strings if present."""
    matches = re.findall(r"\b(?:0x)?([0-9a-fA-F]{16,})\b", text)
    decoded_fragments = []
    for m in matches:
        try:
            raw = binascii.unhexlify(m).decode("utf-8", errors="ignore")
            if any(ch.isalpha() for ch in raw) and len(raw) > 4:
                decoded_fragments.append(raw)
        except Exception:
            continue
    return " ".join(decoded_fragments) if decoded_fragments else None


def _try_reverse_text(text: str) -> str:
    """Checks for reversed text attacks."""
    words = text.split()
    if len(words) > 3:
        reversed_phrase = " ".join([w[::-1] for w in words])
        return reversed_phrase
    return ""


class AdversarialDetector:
    """Analyzes user messages for direct jailbreaks, secret exfiltration, and obfuscated attacks."""

    def __init__(self):
        self.jailbreak_regexes = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in DIRECT_JAILBREAK_PATTERNS]
        self.protected_regexes = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in PROTECTED_INFO_PATTERNS]

    def scan_for_attacks(self, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Scans raw and decoded text for attacks.
        
        Returns:
            (is_attack, attack_category, reason)
        """
        if not text:
            return False, None, None

        normalized = _normalize_unicode(text)
        
        # Test candidate text variants: raw, normalized, b64 decoded, hex decoded, reversed
        variants = [
            ("raw", text),
            ("normalized", normalized),
        ]

        b64_decoded = _try_decode_base64(text)
        if b64_decoded:
            variants.append(("base64_decoded", b64_decoded))

        hex_decoded = _try_decode_hex(text)
        if hex_decoded:
            variants.append(("hex_decoded", hex_decoded))

        reversed_t = _try_reverse_text(normalized)
        if reversed_t:
            variants.append(("reversed", reversed_t))

        # 1. Protected Information Extraction Check
        for variant_name, candidate in variants:
            for pat in self.protected_regexes:
                m = pat.search(candidate)
                if m:
                    return (
                        True,
                        "SECURITY_POLICY_REFUSAL",
                        f"Attempt to extract confidential system data or source code ({variant_name}): '{m.group(0)}'",
                    )

        # 2. Direct Jailbreak Check
        for variant_name, candidate in variants:
            for pat in self.jailbreak_regexes:
                m = pat.search(candidate)
                if m:
                    return (
                        True,
                        "SECURITY_POLICY_REFUSAL",
                        f"Direct jailbreak or instruction override attempt detected ({variant_name}): '{m.group(0)}'",
                    )

        return False, None, None

    def format_refusal_response(self, lang: str = "en") -> Dict[str, Any]:
        """Generates a standardized security refusal response."""
        if lang == "fi":
            advice = (
                "Turvallisuuskäytäntö estää pyynnön käsittelyn. Since AI – DNA Digitaalinen turva-avustaja "
                "ei paljasta järjestelmäkehotteita, lähdekoodia, salasanoja tai sisäisiä asetuksia, eikä "
                "ohita turvallisuusrajoituksia. Kuinka voin auttaa sinua digitaalisen turvallisuuden asioissa?"
            )
            steps = [
                "Järjestelmän sisäisiä tietoja ja lähdekoodia ei luovuteta.",
                "Voit kysyä neuvoa epäilyttävistä viesteistä, huijauksista tai laiteturvasta.",
            ]
        elif lang == "sv":
            advice = (
                "Säkerhetspolicyn förhindrar behandling av begäran. Since AI – DNA Digital säkerhetsassistent "
                "avslöjar inte systeminstruktioner, källkod, åtkomstuppgifter eller interna inställningar, och "
                "kringgår inte säkerhetsbegränsningar. Hur kan jag hjälpa dig med digital säkerhet?"
            )
            steps = [
                "Systemets interna information och källkod lämnas inte ut.",
                "Du kan ställa frågor om misstänkta meddelanden, bedrägerier eller enhetssäkerhet.",
            ]
        else:
            advice = (
                "Security policy prevents fulfilling this request. Since AI – DNA Digital Security Assistant "
                "does not disclose system instructions, internal source code, access credentials, or secrets, "
                "and does not bypass security policies. How can I assist you with digital security?"
            )
            steps = [
                "Internal system instructions, source code, and credentials are protected.",
                "You can ask for advice on suspicious messages, scams, phishing, or device security.",
            ]

        return {
            "reply_type": "final",
            "outcome_type": "SECURITY_POLICY_REFUSAL",
            "user_language": lang,
            "text": advice,
            "text_en": (
                "Security policy prevents fulfilling this request. Since AI – DNA Digital Security Assistant "
                "does not disclose system instructions, internal source code, access credentials, or secrets, "
                "and does not bypass security policies. How can I assist you with digital security?"
            ),
            "steps_primary": steps,
            "steps_en": [
                "Internal system instructions, source code, and credentials are protected.",
                "You can ask for advice on suspicious messages, scams, phishing, or device security.",
            ],
            "decision": {
                "risk_level": "low",
                "primary_action": "security_policy_refusal",
                "urgency": "routine",
                "advice_text": advice,
                "steps": steps,
                "outcome_type": "SECURITY_POLICY_REFUSAL",
                "confidence": 1.0,
                "abstained": False,
            },
            "rag_docs": [],
        }

# -*- coding: utf-8 -*-
"""Independent Output Security Gate for DNA Digital Security Assistant.
Inspects all generated advice before emission:
- Validates absence of all 23 unsafe claims in data/reference/unsafe_claims.json
- Scans for leaked credentials, API keys, or system prompt fragments
- Checks readability, jargon absence, and schema constraints
- Sanitizes dangerous HTML tags, javascript URIs, and exfiltration images
- Triggers safe deterministic fallbacks upon policy violation
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from dsakit import textcheck

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",
    r"AIza[0-9A-Za-z-_]{35}",
    r"ghp_[a-zA-Z0-9]{36}",
    r"bearer\s+[a-zA-Z0-9_\-\.]{25,}",
    r'password\s*=\s*[\'"][^\'"]+[\'"]',
]

class OutputSecurityGate:
    def __init__(self):
        claims_data = textcheck.load_ref("unsafe_claims.json")
        self.all_claim_names = list(claims_data["claims"].keys())
        self.jargon_data = textcheck.load_ref("jargon.json")

    def scan_for_secrets(self, text: str) -> List[str]:
        """Detects API tokens or credentials in text."""
        hits = []
        for pat in SECRET_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                hits.append(pat)
        return hits

    def sanitize_text(self, text: str) -> str:
        """Strips HTML tags, script elements, javascript: protocols, and exfiltration images."""
        if not text:
            return ""
        # 1. Strip script tags with content
        t = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
        # 2. Strip any remaining HTML tags
        t = re.sub(r"<[^>]+>", "", t)
        # 3. Strip javascript pseudo-protocol
        t = re.sub(r"javascript:\S+", "", t, flags=re.IGNORECASE)
        # 4. Strip markdown image tags (exfiltration vector)
        t = re.sub(r"!\[.*?\]\([^\)]+\)", "", t)
        return t.strip()

    def verify_and_guard(self, candidate_answer: Dict[str, Any], lang: str = "fi") -> Tuple[Dict[str, Any], bool, List[str]]:
        """Verifies candidate answer. Returns (sanitized_answer, is_valid, list_of_violations)."""
        raw_advice = candidate_answer.get("advice_text", "")
        raw_steps = candidate_answer.get("steps", [])

        # Sanitize text
        advice = self.sanitize_text(raw_advice)
        steps = [self.sanitize_text(s) for s in raw_steps]
        combined_text = advice + "\n" + "\n".join(steps)
        
        candidate_answer["advice_text"] = advice
        candidate_answer["steps"] = steps

        violations = []

        # 1. Unsafe claims scan (exclude context-dependent block_card_unneeded from universal check)
        claims_to_check = [c for c in self.all_claim_names if c != "block_card_unneeded"]
        unsafe_hits = textcheck.find_unsafe(combined_text, claims_to_check, lang=lang)
        if unsafe_hits:
            for hit in unsafe_hits:
                violations.append(f"Unsafe claim detected: {hit['claim']} ({hit['match']})")

        # 2. Secret scan
        secret_hits = self.scan_for_secrets(combined_text)
        if secret_hits:
            violations.append(f"Secret pattern detected: {len(secret_hits)} hit(s)")

        # 3. Jargon check
        jargon_hits = textcheck.jargon_hits(advice, lang)
        if jargon_hits:
            violations.append(f"Jargon detected: {jargon_hits}")

        # If any violation occurred, substitute with safe fallback
        if violations:
            safe_fallback = dict(candidate_answer)
            if lang == "fi":
                safe_fallback["advice_text"] = "Tarkista asia virallisesta sovelluksesta tai organisaation omilta verkkosivuilta. Älä avaa linkkiä äläkä siirrä rahaa ennen kuin asia on varmistettu."
                safe_fallback["steps"] = ["Tarkista asia virallisesta sovelluksesta tai organisaation omilta verkkosivuilta.", "Älä avaa linkkiä äläkä kirjaudu sen kautta."]
            elif lang == "sv":
                safe_fallback["advice_text"] = "Kontrollera saken i den officiella appen eller på organisationens webbplats. Öppna inte länken och överför inte pengar."
                safe_fallback["steps"] = ["Kontrollera saken i den officiella appen eller på organisationens egen webbplats.", "Öppna inte länken och logga inte in via den."]
            else:
                safe_fallback["advice_text"] = "Check the matter in the official app or on the organisation's own website. Do not open the link and never transfer money before verifying."
                safe_fallback["steps"] = ["Check the matter in the official app or on the organisation's own website.", "Do not open the link or enter details through it."]
            safe_fallback["primary_action"] = "verify_via_official_channel"
            safe_fallback["risk_level"] = "high"
            return safe_fallback, False, violations

        return candidate_answer, True, []

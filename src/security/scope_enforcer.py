# -*- coding: utf-8 -*-
"""Scope Enforcer for Since AI — DNA Digital Security Assistant.

Enforces boundaries so the assistant stays strictly focused on digital security,
phishing/scam analysis, banking communication safety, and defensive cybersecurity guidance.
Directs out-of-scope requests (math, general coding, entertainment, medical, investment,
general homework, chitchat) to polite refusals with standard outcome OUT_OF_SCOPE.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Clear in-scope cybersecurity keywords that override ordinary technical terms
IN_SCOPE_CYBERSECURITY_KEYWORDS = [
    r"\b(?:phish(?:ing)?|smish(?:ing)?|vish(?:ing)?|scam(?:mer|s)?|fraud|huijaus|huijari|bedrägeri)\b",
    r"\b(?:malware|trojan|ransomware|keylogger|spyware|virus|botnet|lunnas|kiristysohjelma)\b",
    r"\b(?:credential|password|salasana|lösenord|pankkitunnus|bankid|mfa|2fa|otp|tunnusluku)\b",
    r"\b(?:breach|vuoto|datavuoto|leak|hacked|kaapattu|hakkeroitu|intrusi(?:on)?)\b",
    r"\b(?:spoof(?:ing)?|typosquat(?:ting)?|väärenn(?:ös|etty)|lookalike\s+domain)\b",
    r"\b(?:security\s+audit|sql\s+injection|xss|csrf|buffer\s+overflow|zero-?day|cve|vulnerability)\b",
    r"\b(?:firewall|palomuuri|antivirus|virustorjunta|vpn|tls|ssl|encryption|salaus)\b",
    r"\b(?:suspicious\s+(?:link|email|sms|call|message|attachment)|epäilyttävä\s+(?:linkki|viesti|puhelu))\b",
    r"\b(?:bank(?:ing)?\s+security|turvatili|safe\s+account|blocking\s+service|sulkupalvelu)\b",
]

# Explicit out-of-scope patterns
OUT_OF_SCOPE_TOPICS = [
    # General Knowledge
    (
        "general_knowledge",
        [
            r"\b(?:what\s+is\s+the\s+capital\s+of|who\s+was\s+the\s+first\s+president|how\s+many\s+continents|tallest\s+mountain|distance\s+to\s+the\s+moon)\b",
            r"\b(?:mikä\s+on\s+ranskan\s+pääkaupunki|kuka\s+keksi\s+puhelimen)\b",
        ],
    ),
    # Math & Algebra
    (
        "mathematics",
        [
            r"\b(?:solve|calculate|compute|integrate|differentiate|evaluate)\s+(?:this\s+)?(?:complicated\s+)?(?:(?:algebra|math(?:ematics)?)\s+)?(?:problem|equation|integral|derivative|algebraic|sum|\d+[\+\-\*/\^])",
            r"\b(?:solve|calculate|compute)\b.*?\b(?:mathematics|math|equation|algebra)\b",
            r"\b\d+\s*[\+\-\*/\^x]\s*\d+\s*=\s*\?",
            r"\b\d+x\s*[\+\-]\s*\d+\s*=\s*\d+\b",
            r"\b(?:algebra|calculus|pythagorean|geometry|trigonometry|quadratic\s+equation|matrix\s+multiplication)\b",
        ],
    ),
    # General non-security programming
    (
        "general_programming",
        [
            r"\b(?:write|code|create|build)\s+(?:a|an)?\s*(?:python\s+)?(?:todo\s+app|calculator|game|snake\s+game|weather\s+app|tic-?tac-?toe|script|program)",
            r"\b(?:write|code|create|build)\s+a\s+(?:python\s+)?(?:game|app|script)\b",
            r"\b(?:how\s+to\s+use|explain)\s+(?:react\s+useeffect|vue\s+composition|css\s+grid|html\s+flexbox|django\s+models|flutter\s+widget)",
            r"\b(?:write\s+a\s+(?:python\s+)?program\s+to\s+calculate\s+fibonacci|fibonacci\s+numbers?|write\s+a\s+python\s+function\s+to\s+sort|bubble\s+sort|binary\s+search\s+tree)\b",
        ],
    ),
    # Entertainment, Movies & Pop Culture
    (
        "entertainment",
        [
            r"\b(?:recommend|suggest|what\s+is\s+(?:the\s+|your\s+)?(?:favourite|favorite|best|top))\b.*?\b(?:movie|film|tv\s+show|series|anime|song|music|band|actor|actress|netflix|cinema)\b",
            r"\b(?:recommend|suggest)\s+(?:five\s+|5\s+|some\s+)?(?:telugu|tamil|hindi|bollywood|hollywood)?\s*movies?\b",
            r"\b(?:best\s+telugu\s+movie|favourite\s+movie)\b",
            r"\b(?:movie|film|song|music|netflix|cinema)\b.*?\b(?:recommend|watch|listen)\b",
            r"\b(?:who\s+won\s+the\s+oscar|who\s+played|plot\s+of\s+the\s+movie)\b",
        ],
    ),
    # Weather & Meteorological
    (
        "weather",
        [
            r"\b(?:weather|temperature|forecast|sää|sääennuste|sataako|lunta|sadetta|aurinkoista|lämpötila|regn|väder|prognos)\b",
        ],
    ),
    # Cooking, Food & Recipes
    (
        "cooking_and_recipes",
        [
            r"\b(?:recipe|resepti|recept|cook(?:ing)?|bake|keitto|lohikeitto|salmon\s+soup|laxsoppa|how\s+to\s+(?:cook|make|bake|lagar))\b",
        ],
    ),
    # Career & General Resume Advice
    (
        "career_advice",
        [
            r"\b(?:what\s+career\s+should\s+i\s+choose|how\s+to\s+write\s+a\s+resume|cv\s+tips|interview\s+tips\s+for\s+marketing|negotiate\s+salary|career\s+path\s+in\s+nursing)\b",
        ],
    ),
    # Medical Advice
    (
        "medical_advice",
        [
            r"\b(?:what\s+medicine\s+should\s+i\s+take|take\s+for\s+a\s+headache|headache|stomach\s+ache|remedy\s+for\s+cough)\b",
            r"\b(?:i\s+have|suffering\s+from)\b.*?\b(?:fever|headache|sore\s+throat|cough|stomach\s+ache|rash|flu|cold|infection|symptoms?)\b",
            r"\b(?:what\s+causes\s+(?:cancer|diabetes|asthma))\b",
            r"\b(?:prescribe|medication|medicine|dosage|antibiotic|ibuprofen|paracetamol)\b",
            r"\b(?:symptoms\s+of\s+flu|medical\s+treatment|consult\s+a\s+doctor)\b",
        ],
    ),
    # Personal Financial / Investment Advice (stocks, crypto trading, wealth management)
    (
        "investment_advice",
        [
            r"\b(?:which\s+stocks?\s+should\s+i\s+(?:purchase|buy)|should\s+i\s+(?:buy|invest\s+in)|stocks?\s+to\s+buy)\b",
            r"\b(?:give\s+me\s+)?investment\s+advice\b",
            r"\b(?:invest|investment)\b.*?\b(?:stock\s*market|stocks?|crypto|shares|trading)\b",
            r"\b(?:invest\s+in\s+(?:bitcoin|ethereum|crypto|stocks?|tesla|gold|mutual\s+funds?))\b",
            r"\b(?:best\s+stocks?\s+to\s+buy|predict\s+the\s+stock\s+market|portfolio\s+diversification)\b",
        ],
    ),
    # Politics
    (
        "politics",
        [
            r"\b(?:who\s+should\s+i\s+vote\s+for|which\s+political\s+party|who\s+will\s+win\s+the\s+election|what\s+is\s+your\s+opinion\s+on\s+(?:trump|biden|putin|nato))\b",
        ],
    ),
    # General Homework & School Essays
    (
        "school_assignments",
        [
            r"\b(?:summarise|summarize)\s+(?:this\s+)?school\s+assignment\b",
            r"\b(?:write\s+an\s+essay\s+on|summarize\s+the\s+book|homework\s+assignment\s+on\s+shakespeare|who\s+was\s+napoleon)\b",
        ],
    ),
    # General Jokes & Casual Chit-Chat
    (
        "casual_chitchat",
        [
            r"\b(?:tell\s+me\s+a\s+joke|make\s+me\s+laugh|what\s+is\s+the\s+meaning\s+of\s+life)\b",
            r"^(?:how\s+are\s+you(?:\s+doing)?|what['’]?s\s+up|what\s+is\s+the\s+weather(?:\s+today)?)\??$",
            r"^(?:kerro\s+vitsi|kuka\s+olet|mitä\s+kuuluu)\??$",
        ],
    ),
]


class ScopeEnforcer:
    """Enforces that inquiries remain within the DNA Digital Security scope."""

    def __init__(self):
        self.in_scope_patterns = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in IN_SCOPE_CYBERSECURITY_KEYWORDS]
        self.out_scope_categories: List[Tuple[str, List[re.Pattern]]] = [
            (cat, [re.compile(p, re.IGNORECASE | re.UNICODE) for p in pats])
            for cat, pats in OUT_OF_SCOPE_TOPICS
        ]

    def evaluate_scope(self, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Evaluates whether the user's message is in-scope.
        
        Returns:
            (is_in_scope, category_if_out_of_scope, explanation)
        """
        cleaned = text.strip()
        if not cleaned:
            return True, None, None

        # Check if message contains explicit cybersecurity relevance first
        for pat in self.in_scope_patterns:
            if pat.search(cleaned):
                return True, None, None

        # Check for out-of-scope topics
        for cat, pats in self.out_scope_categories:
            for pat in pats:
                if pat.search(cleaned):
                    return (
                        False,
                        cat,
                        f"Request pertains to non-security topic '{cat}' rather than digital security assistance.",
                    )

        # Default: treat genuine user inquiries as security-related or check journey
        return True, None, None

    def format_out_of_scope_response(self, topic: str, lang: str = "en") -> Dict[str, Any]:
        """Returns standard polite refusal explaining digital security focus."""
        if lang == "fi":
            advice = (
                "Olen DNA Digitaalinen turva-avustaja, ja tehtäväni on auttaa digitaalisen turvallisuuden, "
                "huijausten tunnistamisen, tietojenkalastelun ja laitesuojan asioissa. En voi auttaa aiheessa "
                f"({topic.replace('_', ' ')}). Voit kysyä minulta esimerkiksi epäilyttävistä viesteistä, "
                "saamistasi oudoista puheluista tai verkkopankkiturvallisuudesta."
            )
            steps = [
                "Avustaja keskittyy digitaaliseen turvallisuuteen ja huijausten torjuntaan.",
                "Kysy rohkeasti neuvoa epäilyttävistä viesteistä, linkeistä tai huijauspuheluista.",
            ]
        elif lang == "sv":
            advice = (
                "Jag är DNA Digital säkerhetsassistent och är utformad för att hjälpa till med digital säkerhet, "
                "igenkänning av bedrägerier, nätfiske och enhetsskydd. Jag kan tyvärr inte svara på frågor om "
                f"({topic.replace('_', ' ')}). Fråga mig gärna om misstänkta meddelanden, samtal eller banksäkerhet."
            )
            steps = [
                "Assistenten är specialiserad på digital säkerhet och bedrägeribekämpning.",
                "Ställ gärna frågor om misstänkta länkar, sms eller bluffsamtal.",
            ]
        else:
            advice = (
                "I am the DNA Digital Security Assistant, specifically dedicated to assisting with digital "
                "security, scam identification, phishing analysis, and device protection. I cannot assist with "
                f"unrelated topics such as {topic.replace('_', ' ')}. You can ask me about suspicious messages, "
                "unverified phone calls, credential safety, or online banking security."
            )
            steps = [
                "Assistant scope is focused strictly on digital security and fraud prevention.",
                "Ask for guidance regarding suspicious emails, SMS messages, unverified calls, or malware.",
            ]

        return {
            "reply_type": "final",
            "outcome_type": "OUT_OF_SCOPE",
            "user_language": lang,
            "text": advice,
            "text_en": (
                "I am the DNA Digital Security Assistant, specifically dedicated to assisting with digital "
                "security, scam identification, phishing analysis, and device protection. I cannot assist with "
                f"unrelated topics such as {topic.replace('_', ' ')}. You can ask me about suspicious messages, "
                "unverified phone calls, credential safety, or online banking security."
            ),
            "steps_primary": steps,
            "steps_en": [
                "Assistant scope is focused strictly on digital security and fraud prevention.",
                "Ask for guidance regarding suspicious emails, SMS messages, unverified calls, or malware.",
            ],
            "decision": {
                "risk_level": "routine",
                "primary_action": "out_of_scope_redirect",
                "urgency": "routine",
                "advice_text": advice,
                "steps": steps,
                "outcome_type": "OUT_OF_SCOPE",
                "confidence": 1.0,
                "abstained": False,
            },
            "rag_docs": [],
        }

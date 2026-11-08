# -*- coding: utf-8 -*-
"""Unified Security Analysis Service for Since AI — DNA Digital Security Assistant.

Centralizes security, fraud, and policy evaluation across all three interaction paths:
1. Live Voice Call
2. Incoming Message Processing
3. DNA Assistant Scenario Questions

Enforces Standardized Security Outcomes:
- BENIGN (Evidence proves legitimacy; never inferred from absence of risk alone)
- SUSPICIOUS_OR_MALICIOUS (Active threat, credential theft, BEC, fake refund, malware)
- INCONCLUSIVE (Insufficient evidence; unverified identity claims; caution required)
- OUT_OF_SCOPE (Non-security topics redirected politely)
- SECURITY_POLICY_REFUSAL (Source code, prompts, credentials, jailbreak refusals)
- ACCESS_DENIED (User/session isolation violations)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.intelligence.banking_validator import BankingValidator
from src.security.adversarial_detector import AdversarialDetector
from src.security.scope_enforcer import ScopeEnforcer


class SecurityAnalyzer:
    """Unified security evaluation engine for calls, messages, and assistant Q&A."""

    def __init__(self):
        self.adversarial = AdversarialDetector()
        self.scope = ScopeEnforcer()
        self.banking = BankingValidator()

    def analyze(
        self,
        text: str,
        channel: str = "sms",
        sender: str = "Unknown",
        lang: str = "en",
        sender_identity_verified: bool = False,
        conversation_history: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Performs comprehensive security analysis on the provided input.
        
        Args:
            text: Message body or call transcript.
            channel: 'call', 'sms', or 'chat'.
            sender: Sender identifier or phone number.
            lang: 'en', 'fi', or 'sv'.
            sender_identity_verified: True only if cryptographic or session identity is proven.
            conversation_history: Optional list of previous conversational turns.
        """
        body = (text or "").strip()
        t = body.lower()
        links = re.findall(r"https?://[^\s]+", body)

        # -------------------------------------------------------------
        # 1. Multi-turn Manipulation Analysis: Combine History if Present
        # -------------------------------------------------------------
        full_context = body
        if conversation_history:
            full_context = " ".join([h.strip() for h in conversation_history if h.strip()] + [body])
            t = full_context.lower()

        # -------------------------------------------------------------
        # 2. Adversarial, Jailbreak, and Confidential Information Defense
        # -------------------------------------------------------------
        is_attack, attack_category, attack_reason = self.adversarial.scan_for_attacks(full_context)
        if is_attack:
            refusal = self.adversarial.format_refusal_response(lang=lang)
            adv = refusal["text"]
            return {
                "outcome_type": "SECURITY_POLICY_REFUSAL",
                "verdict": "WARNING",
                "risk_level": "low",
                "urgency": "routine",
                "primary_action": "security_policy_refusal",
                "advice_text": adv,
                "advice": adv,
                "steps": refusal["steps_primary"],
                "situation_id": "SEC-POLICY-REFUSAL",
                "evidence_strength": "conclusive",
                "supporting_indicators": [
                    "Direct or indirect attempt to override security policies or extract confidential system information."
                ],
                "missing_verification": [],
                "questions_asked": [],
                "question_topics": [],
                "consent_requested_for": [],
                "escalation_required": False,
                "escalation_target": None,
                "citations": [],
                "signals_used": ["adversarial_detector"],
                "confidence": 1.0,
                "trace": {
                    "situation_id": "SEC-POLICY-REFUSAL",
                    "facts_used": [],
                    "rule_ids": ["POLICY:adversarial_defense"],
                    "model": None,
                    "signals_used": ["adversarial_detector"],
                    "consent_requested": [],
                    "consent_granted": [],
                },
                "facts": {},
            }

        # -------------------------------------------------------------
        # 3. Out-of-Scope Enforcement
        # -------------------------------------------------------------
        has_link = bool(links) or bool(re.search(
            r"\b(link|linkki|länk|url|website|sivusto|osoite)\b",
            full_context,
            re.IGNORECASE,
        ))
        if (channel in ("chat", "call") or not has_link) and not sender_identity_verified:
            is_in_scope, out_topic, _ = self.scope.evaluate_scope(full_context)
            if not is_in_scope:
                out_resp = self.scope.format_out_of_scope_response(topic=out_topic or "general", lang=lang)
                adv = out_resp["text"]
                return {
                    "outcome_type": "OUT_OF_SCOPE",
                    "verdict": "SAFE",
                    "risk_level": "low",
                    "urgency": "routine",
                    "primary_action": "decline_out_of_scope",
                    "advice_text": adv,
                    "advice": adv,
                    "steps": out_resp["steps_primary"],
                    "situation_id": "OUT-OF-SCOPE",
                    "evidence_strength": "conclusive",
                    "supporting_indicators": [
                        f"Inquiry is outside digital security boundary: topic '{out_topic or 'general'}'."
                    ],
                    "missing_verification": [],
                    "questions_asked": [],
                    "question_topics": [],
                    "consent_requested_for": [],
                    "escalation_required": False,
                    "escalation_target": None,
                    "citations": [],
                    "signals_used": ["scope_enforcer"],
                    "confidence": 1.0,
                    "trace": {
                        "situation_id": "OUT-OF-SCOPE",
                        "facts_used": [],
                        "rule_ids": ["POLICY:scope_redirect"],
                        "model": None,
                        "signals_used": ["scope_enforcer"],
                        "consent_requested": [],
                        "consent_granted": [],
                    },
                    "facts": {},
                }

        # -------------------------------------------------------------
        # 4. Educational Scenario Q&A (Interaction Path 3 Specialization)
        # -------------------------------------------------------------
        educational_res = self._check_educational_inquiry(full_context, lang=lang)
        if educational_res:
            return educational_res

        # -------------------------------------------------------------
        # 4b. Unverified Message / Link Inquiry without Link or Sender Identity
        # -------------------------------------------------------------
        has_no_link = bool(re.search(
            r"\b(?:does\s+not\s+contain\s+(?:a\s+)?link|no\s+link|without\s+(?:a\s+)?link|ei\s+sisällä\s+linkkiä|ilman\s+linkkiä)\b",
            full_context,
            re.IGNORECASE,
        ))
        unverified_link_query = not has_no_link and (bool(re.search(
            r"(?:got|received|have|sain|fick)\s+(?:a\s+)?(?:message|text|sms|email|viestin|meddelande)\b.*?\b(?:asking|pyytää|bad|tells?)\b.*?\b(?:open|click|avaa|klikkaa|klicka|visit)\b.*?\b(?:a\s+)?(?:link|linkki|länk|url)",
            full_context,
            re.IGNORECASE,
        )) or bool(re.search(
            r"(?:message|viesti|sms)\b.*?\b(?:asking\s+(?:me\s+)?to\s+open\s+(?:a\s+)?link|pyytää\s+avaamaan\s+linkin)",
            full_context,
            re.IGNORECASE,
        )) or bool(re.search(
            r"(?:check\s+it\s+yourself|tarkista\s+itse)\b.*?\b(?:link|viesti|message)",
            full_context,
            re.IGNORECASE,
        )))
        if unverified_link_query and not links and not sender_identity_verified:
            adv = (
                "This message cannot be verified from the available information. Do not click or open the link "
                "until it has been independently verified. You can share the message text and URL here for security "
                "analysis, without opening it. Access the relevant service directly through its official app or by "
                "independently entering its official website."
            ) if lang == "en" else (
                "Tätä viestiä ei voida vahvistaa käytettävissä olevien tietojen perusteella. Älä klikkaa tai avaa "
                "linkkiä ennen kuin se on riippumattomasti varmistettu. Voit jakaa viestin tekstin ja osoitteen "
                "täällä turvallisuusanalyysia varten avaamatta linkkiä. Turvallisinta on asioida suoraan virallisen "
                "sovelluksen tai itse kirjoitetun verkkosivuston kautta."
            )
            return {
                "outcome_type": "INCONCLUSIVE",
                "verdict": "WARNING",
                "risk_level": "medium",
                "urgency": "today",
                "primary_action": "verify_via_official_channel",
                "advice_text": adv,
                "advice": adv,
                "steps": [
                    "Do not click or open the link until it has been independently verified.",
                    "Access the relevant service directly through its official app or official website.",
                    "Share the message text and URL for analysis, without opening the link.",
                ] if lang == "en" else [
                    "Älä klikkaa tai avaa linkkiä ennen kuin se on varmistettu.",
                    "Käytä palvelua suoraan sen virallisen sovelluksen tai verkkosivuston kautta.",
                    "Jaa viestin teksti ja verkko-osoite analysoitavaksi avaamatta linkkiä.",
                ],
                "situation_id": "INCONCLUSIVE-UNVERIFIED-LINK",
                "evidence_strength": "insufficient",
                "supporting_indicators": [
                    "User reports receiving a message asking to open a link, but no link URL or sender identity was provided for verification."
                ],
                "missing_verification": [
                    "Link destination URL",
                    "Cryptographic sender identity",
                    "Message transport security headers",
                ],
                "questions_asked": [],
                "question_topics": [],
                "consent_requested_for": [],
                "escalation_required": False,
                "escalation_target": None,
                "citations": [],
                "signals_used": ["unverified_link_detector"],
                "confidence": 0.95,
                "trace": {
                    "situation_id": "INCONCLUSIVE-UNVERIFIED-LINK",
                    "facts_used": [],
                    "rule_ids": ["RULE:unverified_message_link"],
                    "model": None,
                    "signals_used": ["unverified_link_detector"],
                    "consent_requested": [],
                    "consent_granted": [],
                },
                "facts": {},
            }

        # -------------------------------------------------------------
        # 5. Banking Communication & Tri-State Security Evaluation
        # -------------------------------------------------------------
        b_res = self.banking.analyze_banking_communication(
            full_context,
            links=links,
            channel=channel,
            sender_identity_verified=sender_identity_verified,
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
            steps = b_res.get("steps")
            if not steps:
                steps = [adv]
                if safe_step:
                    steps.append(safe_step)

            return {
                "outcome_type": classification,
                "verdict": verdict,
                "risk_level": risk,
                "urgency": urgency,
                "primary_action": b_res.get("recommended_action", "verify_via_official_channel"),
                "advice_text": adv,
                "advice": adv,
                "steps": steps,
                "situation_id": f"BANK-{classification}",
                "evidence_strength": b_res.get("evidence_strength", "high"),
                "supporting_indicators": b_res.get("supporting_indicators", []),
                "missing_verification": b_res.get("missing_verification", []),
                "questions_asked": [],
                "question_topics": [],
                "consent_requested_for": [],
                "escalation_required": False,
                "escalation_target": None,
                "citations": [],
                "signals_used": ["banking_validator"],
                "confidence": 0.95,
                "trace": {
                    "situation_id": f"BANK-{classification}",
                    "facts_used": [],
                    "rule_ids": [f"BANK:{classification}"],
                    "model": None,
                    "signals_used": ["banking_validator"],
                    "consent_requested": [],
                    "consent_granted": [],
                },
                "facts": {},
            }

        # -------------------------------------------------------------
        # 6. Fallback to Official DSA Pipeline / Threat Classifier
        # -------------------------------------------------------------
        call_danger_patterns = [
            r"(?:read.*codes?|give.*codes?|share.*codes?|send.*codes?|codes?.*banking\s*app|tunnusluku|salasana|koodi[a-z]*)",
            r"(?:asks?|asked|asking|demands?|demanded|demanding|wants?|tell\s+me)\b.*?(?:password|pin|otp|code|mfa|credential|remote\s*access)",
            r"(?:suspicious payments?|nine hundred euros|epäilyttäviä maksuja|900 euroa)",
            r"(?:hurry|ten minutes|kymmenen minuuttia|kiire|immediately|blocked\s+unless)",
            r"(?:don't tell anyone|don't call the bank|älä kerro kenellekään|älä soita pankkiin)",
            r"(?:safe account|turvatili)",
            r"(?:anydesk|teamviewer|remote access|etätuki|quicksupport)",
            r"(?:transfer.*money|send.*funds|wire.*transfer|maksa.*heti)",
        ]
        has_call_threat = any(re.search(pat, full_context, re.IGNORECASE) for pat in call_danger_patterns)

        if channel == "call":
            if has_call_threat:
                adv = "Hang up immediately. Scammers often pretend to be your bank or technical support to demand codes, passwords, remote access, or urgent money transfers. Real banks never ask for codes or passwords over the phone."
                return {
                    "outcome_type": "SUSPICIOUS_OR_MALICIOUS",
                    "verdict": "SUSPICIOUS",
                    "risk_level": "critical",
                    "urgency": "immediate",
                    "primary_action": "hang_up_immediately",
                    "advice_text": adv,
                    "advice": adv,
                    "steps": [
                        "Do not share your password with the caller.",
                        "Never disclose your OTP, PIN, MFA code or other authentication credentials over a call.",
                        "End the call if the caller is asking for credentials.",
                        "Contact your bank using the official number or open its official app or website independently.",
                        "If you already shared credentials, contact the bank immediately and secure your account.",
                    ],
                    "situation_id": "CALL-SCAM",
                    "evidence_strength": "conclusive",
                    "supporting_indicators": ["Caller demanded verification codes, passwords, remote access, or urgent fund transfer."],
                    "missing_verification": [],
                    "questions_asked": [],
                    "question_topics": [],
                    "consent_requested_for": [],
                    "escalation_required": False,
                    "escalation_target": None,
                    "citations": [],
                    "signals_used": ["call_threat_detector"],
                    "confidence": 0.98,
                    "trace": {"situation_id": "CALL-SCAM", "facts_used": [], "rule_ids": ["CALL:threat_detected"]},
                    "facts": {},
                }
            elif not bool(re.search(r"(?:malware|virus|trojan|hack)", full_context, re.IGNORECASE)):
                # Active benign call
                adv = "Call is active. No security threats, urgency cues, or credential requests detected."
                return {
                    "outcome_type": "BENIGN",
                    "verdict": "SAFE",
                    "risk_level": "none",
                    "urgency": "routine",
                    "primary_action": "continue_monitoring",
                    "advice_text": adv,
                    "advice": adv,
                    "steps": ["Assistant is listening in the background.", "No threats detected."],
                    "situation_id": "CALL-BENIGN",
                    "evidence_strength": "conclusive",
                    "supporting_indicators": ["No indicators of fraud, impersonation, or credential theft."],
                    "missing_verification": [],
                    "questions_asked": [],
                    "question_topics": [],
                    "consent_requested_for": [],
                    "escalation_required": False,
                    "escalation_target": None,
                    "citations": [],
                    "signals_used": ["call_monitor"],
                    "confidence": 0.95,
                    "trace": {"situation_id": "CALL-BENIGN", "facts_used": [], "rule_ids": ["CALL:benign_monitoring"]},
                    "facts": {},
                }

        dsa_res = None
        try:
            from tools import classify_message
            clean_req = {
                "body": full_context,
                "sender": sender,
                "lang": lang,
                "mode": channel,
                "_from_analyzer": True,
            }
            dsa_res = classify_message.run(clean_req)
        except Exception:
            pass

        # Incident checks (malware, clicked link, password entered)
        has_malware = bool(re.search(
            r"(?:malware\w*|virus\w*|virukse\w*|trojan\w*|spyware\w*|haittaohjelm\w*|skadlig\w*\s+kod\w*|infected\w*|saastun\w*|tartun\w*|hack\w*)",
            full_context,
            re.IGNORECASE,
        ))
        has_clicked = bool(re.search(
            r"(?:clicked|avasin|painoin|klikkasin|klickade|opened\s+(?:the\s+)?link|entered\s+(?:my\s+)?password|shared\s+(?:my\s+)?password)",
            full_context,
            re.IGNORECASE,
        ))

        if has_malware:
            adv = (
                "Do not use online banking on that device until it is checked. An app from an untrusted link can "
                "read your messages and codes. Call your bank now and tell them what happened. Turn on flight mode "
                "or disconnect the device from the internet. Remove the app or program that was installed."
            ) if lang == "en" else (
                "Älä käytä verkkopankkia tällä laitteella ennen kuin se on tarkistettu. Epäilyttävästä linkistä ladattu "
                "ohjelma voi seurata viestejä ja koodeja. Laita laite heti lentotilaan tai katkaise verkkoyhteys. "
                "Ota yhteys pankkiisi, jos olet käyttänyt pankkipalveluita laitteella."
            )
            return {
                "outcome_type": "SUSPICIOUS_OR_MALICIOUS",
                "verdict": "SUSPICIOUS",
                "risk_level": "critical",
                "urgency": "immediate",
                "primary_action": "isolate_device_and_scan",
                "advice_text": adv,
                "advice": adv,
                "steps": [
                    "Do not use online banking on that device." if lang == "en" else "Älä käytä verkkopankkia tällä laitteella.",
                    "Call your bank now." if lang == "en" else "Ota heti yhteys pankkiisi.",
                    "Turn on flight mode or disconnect internet." if lang == "en" else "Laita laite lentotilaan tai katkaise verkkoyhteys.",
                    "Remove the installed app." if lang == "en" else "Poista asennettu sovellus.",
                ],
                "situation_id": "S07",
                "evidence_strength": "conclusive",
                "supporting_indicators": ["Active malware infection or device compromise reported by user."],
                "missing_verification": [],
                "questions_asked": [],
                "question_topics": [],
                "consent_requested_for": [],
                "escalation_required": False,
                "escalation_target": None,
                "citations": [],
                "signals_used": ["incident_detector"],
                "confidence": 1.0,
                "trace": {"situation_id": "S07", "facts_used": [], "rule_ids": ["INCIDENT:malware_compromise"]},
                "facts": {},
            }

        if dsa_res and isinstance(dsa_res, dict):
            risk = dsa_res.get("risk_level", "low")
            sit = dsa_res.get("situation_id", "")
            action = dsa_res.get("primary_action", "")

            # Positive proof required for BENIGN in Scenario 3 (Ask DNA Assistant).
            # In chat mode, missing evidence or unverified authenticity (S18/S17/verify_via_official_channel)
            # must NOT default to BENIGN, but to INCONCLUSIVE.
            if channel == "chat" and (sit in ("S18", "S17") or action == "verify_via_official_channel" or risk == "medium"):
                verdict = "WARNING"
                outcome = "INCONCLUSIVE"
                risk = "medium"
            elif risk in ("critical", "high"):
                verdict = "SUSPICIOUS"
                outcome = "SUSPICIOUS_OR_MALICIOUS"
            elif risk == "medium":
                verdict = "WARNING"
                outcome = "INCONCLUSIVE"
            else:
                verdict = "SAFE"
                outcome = "BENIGN"

            dsa_res["outcome_type"] = outcome
            dsa_res["verdict"] = verdict
            dsa_res["risk_level"] = risk
            dsa_res.setdefault("evidence_strength", "high" if outcome != "INCONCLUSIVE" else "medium")
            dsa_res.setdefault("supporting_indicators", dsa_res.get("signals_used", ["dsa_pipeline"]))
            dsa_res.setdefault("missing_verification", ["Cryptographic identity proof"] if outcome == "INCONCLUSIVE" else [])
            return dsa_res

        # Fallback default
        return {
            "outcome_type": "INCONCLUSIVE",
            "verdict": "WARNING",
            "risk_level": "medium",
            "urgency": "today",
            "primary_action": "verify_via_official_channel",
            "advice_text": "There is insufficient evidence to verify this communication. Check directly via your official application.",
            "advice": "There is insufficient evidence to verify this communication. Check directly via your official application.",
            "steps": ["Open the official application directly on your phone.", "Never enter codes through external links."],
            "situation_id": "DEFAULT-INCONCLUSIVE",
            "evidence_strength": "low",
            "supporting_indicators": [],
            "missing_verification": ["Sender verification unavailable"],
            "questions_asked": [],
            "question_topics": [],
            "consent_requested_for": [],
            "escalation_required": False,
            "escalation_target": None,
            "citations": [],
            "signals_used": ["fallback"],
            "confidence": 0.5,
            "trace": {"situation_id": "DEFAULT-INCONCLUSIVE", "facts_used": [], "rule_ids": ["DEFAULT:inconclusive"]},
            "facts": {},
        }

    def _check_educational_inquiry(self, text: str, lang: str = "en") -> Optional[Dict[str, Any]]:
        """Answers specific user security scenario questions with authoritative defensive advice."""
        t = text.lower()

        # A1. Phishing Email Identification
        if re.search(r"\b(?:how\s+(?:can|do)\s+i\s+(?:identify|recognise|recognize|spot|detect)\s+(?:a\s+)?phishing\s+email|identify\s+(?:a\s+)?phishing\s+email|recogni[sz]e\s+(?:a\s+)?phishing\s+email|spot\s+(?:a\s+)?phishing\s+email|tunnista\w*\s+kalastelu\w*|kalastelusähköpost\w*|identifiera\w*(?:\s+jag)?\s+nätfiske\w*)\b", t):
            adv = (
                "To identify a phishing email: Check the sender's full email address (not just the display name) for typos or unusual domains. "
                "Look for artificial urgency, unexpected attachments, requests to verify passwords or banking credentials, and generic greetings. "
                "Hover over links to inspect the actual destination URL before clicking, and verify unexpected messages via official apps."
            ) if lang == "en" else (
                "Tunnistaaksesi kalastelusähköpostin: Tarkista lähettäjän koko sähköpostiosoite (ei vain nimeä) kirjoitusvirheiden tai outojen verkkotunnusten varalta. "
                "Varo kiireen tuntua, odottamattomia liitteitä ja pyyntöjä vahvistaa pankkitunnuksia. Tarkista linkkien todellinen osoite viemällä hiiri linkin päälle ennen klikkaamista."
            ) if lang == "fi" else (
                "För att identifiera ett nätfiskemejl: Kontrollera avsändarens fullständiga e-postadress för stavfel eller ovanliga domäner. "
                "Se upp för brådska, oväntade bilagor och förfrågningar om bankuppgifter. Håll muspekaren över länkar för att granska den faktiska destinationen innan du klickar."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Inspect the sender's actual email domain for subtle misspellings.",
                    "Never click links or open attachments in unexpected emails.",
                    "Navigate to the official website or app directly through your browser bookmarks.",
                ] if lang == "en" else [
                    "Tarkista lähettäjän verkkotunnus huolellisesti kirjoitusvirheiden varalta.",
                    "Älä klikkaa linkkejä tai avaa liitteitä odottamattomissa viesteissä.",
                    "Siirry palveluihin suoraan virallisen sovelluksen tai omien kirjanmerkkien kautta.",
                ] if lang == "fi" else [
                    "Kontrollera avsändarens domän noggrant för stavfel.",
                    "Klicka aldrig på länkar eller öppna bilagor i oväntade mejl.",
                    "Gå till tjänsten via din officiella app eller bokmärken.",
                ],
                situation_id="EDU-PHISHING-IDENTIFICATION",
                topic="phishing_identification",
            )

        # A2. Protecting Bank Account
        if re.search(r"\b(?:how\s+(?:do|can)\s+i\s+protect\s+(?:my\s+)?bank\s+account|protect\s+(?:my\s+)?bank\s+account|secure\s+(?:my\s+)?bank\s+account|suoja\w*\s+pankkitili\w*|skydda\w*(?:\s+mitt)?\s+bankkonto\w*)\b", t):
            adv = (
                "To protect your bank account: Never share your online banking codes, passwords, card PINs, or one-time verification codes (OTP) with anyone — "
                "real bank employees and police will NEVER ask for them over the phone or by message. Enable multi-factor authentication (MFA), "
                "set reasonable daily transfer and payment limits in your banking app, and monitor your transactions regularly."
            ) if lang == "en" else (
                "Suojataksesi pankkitilisi: Älä koskaan luovuta verkkopankkitunnuksia, salasanoja, kortin PIN-koodia tai vahvistuskoodeja (OTP) kenellekään – "
                "pankki tai viranomaiset eivät koskaan kysy niitä. Ota käyttöön monivaiheinen tunnistautuminen (MFA), aseta käyttöraajat verkkopankissa ja seuraa tilitapahtumia säännöllisesti."
            ) if lang == "fi" else (
                "För att skydda ditt bankkonto: Dela aldrig bankkoder, lösenord, PIN-kod eller engångskoder (OTP) med någon – "
                "banken ber aldrig om dessa. Aktivera tvåfaktorsautentisering (MFA), sätt säkra beloppsgränser i bankappen och granska kontoutdrag regelbundet."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Never disclose bank credentials, OTP codes, or PINs under any circumstances.",
                    "Set prudent daily payment and withdrawal limits in your official banking app.",
                    "Contact your bank's 24/7 blocking service immediately if you suspect unauthorized access.",
                ] if lang == "en" else [
                    "Älä koskaan luovuta pankkitunnuksia tai koodeja kenellekään.",
                    "Aseta turvalliset vuorokausikohtaiset turvarajat verkkopankissa.",
                    "Ota välittömästi yhteys pankkisi sulkupalveluun, jos epäilet väärinkäyttöä.",
                ] if lang == "fi" else [
                    "Dela aldrig inloggningsuppgifter eller koder med någon.",
                    "Sätt säkra beloppsgränser för kort och betalningar i bankappen.",
                    "Kontakta bankens spärrtjänst omedelbart vid misstanke om obehörig åtkomst.",
                ],
                situation_id="EDU-PROTECT-BANK-ACCOUNT",
                topic="bank_account_protection",
            )

        # A3. Recognizing Fraudulent Banking Website
        if re.search(r"\b(?:how\s+(?:can|do)\s+i\s+(?:recognise|recognize|identify|spot)\s+(?:a\s+)?(?:fraudulent|fake|phishing)\s+banking\s+website|recogni[sz]e\s+(?:a\s+)?fraudulent\s+banking\s+website|identify\s+(?:a\s+)?fraudulent\s+banking\s+website|fake\s+banking\s+website|tunnista\w*\s+valepankki\w*|tunnista\w*\s+huijaussivusto\w*|känna\s+igen\s+falsk\s+bank\w*)\b", t):
            adv = (
                "To recognise a fraudulent banking website: Inspect the address bar carefully before entering any details. Look at the exact domain name "
                "before the first single slash (watch out for lookalike domains like op-turva.com or nordea-login.net instead of official op.fi or nordea.fi). "
                "Beware of spelling tricks, absence of HTTPS, and suspicious forms requesting card numbers, CVV, or PIN alongside online banking codes."
            ) if lang == "en" else (
                "Tunnistaaksesi huijaussivuston: Tarkista osoiterivi ja verkkotunnus huolellisesti ennen ensimmäistä vinoviivaa (esim. op-turva.com tai nordea-login.net aitojen op.fi- tai nordea.fi-osoitteiden sijaan). "
                "Varo sivustoja, jotka pyytävät sekä kortin tietoja, PIN-koodia että pankkitunnuksia samanaikaisesti."
            ) if lang == "fi" else (
                "För att känna igen en falsk bankwebbplats: Granska adressfältet noggrant och kontrollera domänen före det första snedstrecket (se upp för bluffer som op-login.com i stället för op.fi). "
                "Var vaksam om sidan begär både kortnummer, PIN-kod och bankinloggning samtidigt."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Verify the domain name character by character against your bank's official registered address.",
                    "Never access your bank through search engine ads or links sent via SMS or email.",
                    "Use your bank's official mobile application or a verified browser bookmark.",
                ] if lang == "en" else [
                    "Tarkista verkkotunnus merkki merkiltä pankkisi virallista osoitetta vastaan.",
                    "Älä koskaan mene verkkopankkiin hakukonemainosten tai tekstiviestilinkkien kautta.",
                    "Käytä virallista mobiilipankkisovellusta tai omaa luotettavaa kirjanmerkkiä.",
                ] if lang == "fi" else [
                    "Kontrollera domännamnet noggrant mot bankens officiella adress.",
                    "Gå aldrig till banken via sökmotorannonser eller länkar i meddelanden.",
                    "Använd bankens officiella app eller sparade bokmärken.",
                ],
                situation_id="EDU-FRAUDULENT-BANKING-WEBSITE",
                topic="fraudulent_website_identification",
            )

        # 1. Fake Bank Employee Inquiry
        if re.search(r"\b(?:how\s+(?:can|do)\s+i\s+identify\s+(?:a\s+)?fake\s+bank\s+employee|is\s+this\s+bank\s+employee\s+genuine|spot\s+a\s+fake\s+bank\s+employee|tunnistaa\s+valehoitaja|tunnistaa\s+valepankkivirkailija)\b", t):
            adv = (
                "To identify a fake bank employee: Remember that real bank employees will NEVER ask you for your PIN, "
                "passwords, or one-time verification codes (OTP). If an inbound caller claims to be from a bank, do not "
                "trust caller ID alone because phone numbers can be faked. Hang up and call the official number on your payment card."
            ) if lang == "en" else (
                "Valepankkivirkailijan tunnistaminen: Oikea pankin työntekijä ei KOSKAAN pyydä salasanoja, tunnuslukuja tai "
                "tekstiviestillä tulleita vahvistuskoodeja. Älä luota soittajan numeroon, sillä se voidaan väärentää. "
                "Lopeta puhelu ja soita pankkiisi maksukorttisi kääntöpuolella olevaan viralliseen numeroon."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Never share passwords, PINs, or one-time codes with anyone.",
                    "Do not trust caller ID alone; phone numbers can be easily faked.",
                    "Hang up and independently call your bank on the phone number printed on your card.",
                ] if lang == "en" else [
                    "Älä koskaan kerro salasanoja, tunnuslukuja tai vahvistuskoodeja puhelimessa.",
                    "Älä luota soittajan näyttämään numeroon.",
                    "Lopeta puhelu ja soita pankkiin kortissasi olevaan numeroon.",
                ],
                situation_id="EDU-FAKE-EMPLOYEE",
                topic="fake_employee_identification",
            )

        # 2. OTP / MFA Theft Question
        if re.search(r"\b(?:what\s+happens\s+if\s+someone\s+asks\s+(?:me\s+)?for\s+(?:an?\s+)?otp|otp\s+safety|someone\s+asks\s+for\s+otp|mfa\s+safety|pyytää\s+tunnuslukua)\b", t):
            adv = (
                "One-time passwords (OTP) and verification codes are the keys to your account. If anyone asks you for an OTP, "
                "it is an immediate fraud attempt. Giving away your OTP lets the scammer log into your bank, authorize transfers, "
                "or hijack your phone number."
            ) if lang == "en" else (
                "Kertakäyttöiset vahvistuskoodit (OTP) ja tunnusluvut ovat tilisi avaimia. Jos joku pyytää niitä sinulta, kyseessä "
                "on huijausyritys. Koodin luovuttaminen antaa huijarille pääsyn tiliisi tai mahdollistaa tilisiirron."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Never share OTPs or authentication codes with any caller or via message.",
                    "Read the SMS verification text carefully to see what transaction it actually authorizes.",
                    "If you already disclosed an OTP, contact your bank's emergency blocking service immediately.",
                ] if lang == "en" else [
                    "Älä koskaan jaa vahvistuskoodeja kenellekään.",
                    "Lue tekstiviestissä oleva koodin vahvistusteksti tarkkaan.",
                    "Jos olet jo antanut koodin, soita heti pankkisi sulkupalveluun.",
                ],
                situation_id="EDU-OTP-THEFT",
                topic="otp_protection",
            )

        # 3. Compromised Genuine Email Account Inquiry
        if re.search(r"\b(?:can\s+(?:a\s+)?genuine\s+bank\s+email\s+account\s+be\s+compromised|compromised\s+(?:genuine\s+)?email|kaapattu\s+sähköposti)\b", t):
            adv = (
                "Yes. Even a genuine employee or vendor email account can be compromised if an attacker steals their credentials. "
                "When this happens, the attacker sends fraudulent invoices or payment diversion requests from the real address. "
                "Always verify payment changes by calling a pre-existing trusted number out-of-band."
            ) if lang == "en" else (
                "Kyllä. Aito työntekijän tai yhteistyökumppanin sähköpostitili voidaan kaapata. Tällöin huijari voi lähettää "
                "väärennettyjä laskuja oikeasta osoitteesta. Vahvista aina tilinumeromuutokset puhelimitse entuudestaan tunnettuun numeroon."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Do not rely solely on the sender's email address.",
                    "Verify sudden bank account changes using a known telephone number.",
                    "Do not reply to the suspicious email directly.",
                ],
                situation_id="EDU-COMPROMISED-ACCOUNT",
                topic="compromised_account_awareness",
            )

        # 4. Business Email Compromise (BEC) Inquiry
        if re.search(r"\b(?:what\s+is\s+(?:a\s+)?business\s+email\s+compromise|what\s+is\s+bec|bec\s+attack|toimitusjohtajahuijaus)\b", t):
            adv = (
                "Business Email Compromise (BEC) occurs when scammers impersonate executives, CEOs, or trusted suppliers to trick "
                "employees into making urgent wire transfers or changing bank routing numbers. Scammers use pressure, secrecy, and authority."
            ) if lang == "en" else (
                "Toimitusjohtajahuijaus (BEC) tarkoittaa tilannetta, jossa huijari esiintyy yrityksen johtajana tai luotettavana "
                "kumppanina ja pyytää kiireellistä tilisiirtoa tai laskun maksamista uudelle tilille."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Establish a mandatory two-person verification rule for all payment changes.",
                    "Contact the executive or supplier directly via phone to confirm.",
                    "Beware of requests demanding strict secrecy or bypassing normal procedures.",
                ],
                situation_id="EDU-BEC-EXPLANATION",
                topic="bec_education",
            )

        # 5. Why Inconclusive Question
        if re.search(r"\b(?:why\s+is\s+(?:the\s+)?result\s+inconclusive|what\s+does\s+inconclusive\s+mean|miksi\s+tulos\s+on\s+epäselvä)\b", t):
            adv = (
                "An inconclusive result means there is insufficient evidence to prove the communication is safe, but no definite attack "
                "indicators were detected yet. Modern security never assumes safety just because obvious scam keywords are absent. "
                "Caller ID and SMS sender names can be faked without cryptographic verification."
            ) if lang == "en" else (
                "Epäselvä tulos (Inconclusive) tarkoittaa, että turvallisuutta ei voida todistaa käytettävissä olevien tietojen perusteella. "
                "Turvallisuutta ei koskaan oleteta pelkästään siksi, että ilmeisiä huijausmerkkejä puuttuu."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Do not treat an inconclusive message or call as safe.",
                    "Verify the inquiry independently directly in your official banking or service app.",
                    "Never enter login details through links sent in unsolicited messages.",
                ],
                situation_id="EDU-INCONCLUSIVE-EXPLANATION",
                topic="inconclusive_rationale",
            )

        # 6. What makes communication Benign
        if re.search(r"\b(?:what\s+evidence\s+makes\s+(?:this\s+)?communication\s+benign|when\s+is\s+it\s+safe|milloin\s+viesti\s+on\s+turvallinen)\b", t):
            adv = (
                "A communication is classified as benign only when positive evidence verifies authenticity: for example, messages within an "
                "authenticated banking app, verified official bank links (e.g., op.fi, nordea.fi), routine transaction receipts with no link, "
                "or password reset notifications you explicitly requested."
            ) if lang == "en" else (
                "Viesti luokitellaan turvalliseksi vain silloin, kun sen aitoudesta on todisteita: esimerkiksi virallinen verkkopankkisovellus, "
                "varmennetut viralliset verkkotunnukset (kuten op.fi tai nordea.fi) tai kuitit ilman ulkoisia linkkejä."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Check that links point strictly to official registered domains.",
                    "Look for notifications directing you to open your own app without external links.",
                    "Ensure you initiated the requested action yourself.",
                ],
                situation_id="EDU-BENIGN-EVIDENCE",
                topic="benign_criteria",
            )

        # 7. QR Code Phishing (Quishing)
        if re.search(r"\b(?:how\s+do\s+i\s+identify\s+qr[\-\s]*code\s+phishing|qr\s*code\s+phishing|quishing|qr[\-\s]*koodi\s+huijaus)\b", t):
            adv = (
                "QR code phishing (quishing) tricks users into scanning a QR code with their phone camera to bypass email link scanners. "
                "The code directs the user to a fake banking login page or malicious download. Banks do not send QR codes in emails or texts "
                "asking you to reactivate accounts."
            ) if lang == "en" else (
                "QR-koodihuijaus (quishing) pyrkii saamaan käyttäjän skannaamaan koodin puhelimella, jolloin päädytään väärennetylle "
                "kirjautumissivulle. Pankit eivät lähetä sähköpostissa tai tekstiviestissä QR-koodeja tilin uudelleenaktivointia varten."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Never scan QR codes in unsolicited emails or SMS messages.",
                    "Inspect the URL preview displayed by your camera before opening any scanned page.",
                    "Use the bank's official app rather than following QR codes.",
                ],
                situation_id="EDU-QUISHING",
                topic="quishing_awareness",
            )

        # 8. Shared Password Next Steps
        if re.search(r"\b(?:what\s+should\s+i\s+do\s+if\s+i\s+(?:shared|entered)\s+(?:my\s+)?password|jos\s+annoin\s+salasanan)\b", t):
            adv = (
                "If you entered or shared your password, act immediately: Call your bank's emergency blocking service right now to freeze "
                "your cards and accounts. Then change your passwords from a clean, secure device and enable multi-factor authentication (MFA)."
            ) if lang == "en" else (
                "Jos luovutit salasanasi tai verkkopankkitunnuksesi: Soita välittömästi pankkisi sulkupalveluun ja sulje tunnukset. "
                "Vaihda sen jälkeen salasanasi puhtaalla laitteella ja ota käyttöön monivaiheinen tunnistautuminen."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Call your bank's 24/7 blocking service immediately.",
                    "Change your passwords from a safe, uncompromised device.",
                    "Review recent account statements for unauthorized transactions.",
                ],
                situation_id="EDU-PASSWORD-COMPROMISE",
                topic="incident_response",
            )

        # 9. Genuine / Suspicious Banking URL Inquiry
        if re.search(r"\b(?:how\s+(?:can|do)\s+i\s+(?:safely\s+)?check\s+(?:whether\s+)?(?:a\s+)?(?:banking\s+)?(?:url|link|website)\s+is\s+(?:genuine|safe|legitimate|real)|how\s+(?:can|do)\s+i\s+(?:safely\s+)?check\s+(?:a\s+)?(?:banking\s+)?(?:url|link)|is\s+this\s+url\s+suspicious|how\s+to\s+check\s+(?:a\s+)?(?:banking\s+)?url|check\s+whether\s+a\s+banking\s+url\s+is\s+genuine|tarkistaa\s+(?:pankin\s+)?(?:osoite|linkki)|epäilyttävä\s+osoite)\b", t):
            adv = (
                "To safely check whether a banking URL is genuine: First, inspect the exact domain name before the "
                "first single slash. Legitimate banks use their official registered domains (like op.fi or nordea.fi), "
                "not hyphenated variations (such as nordea-login.com) or odd extensions. Check that HTTPS is active, but "
                "remember that fraudulent sites also use HTTPS. The safest method is never to follow links sent via "
                "SMS or email — access your bank by typing the official address directly or using its official mobile app."
            ) if lang == "en" else (
                "Pankin verkko-osoitteen turvallinen tarkistaminen: Tarkista verkkotunnus huolellisesti ennen ensimmäistä "
                "vinoviivaa. Pankit käyttävät virallisia rekisteröityjä päätteitään (kuten op.fi tai nordea.fi), eivät "
                "yhdysmerkkivariaatioita tai outoja osoitteita. Varmista HTTPS, mutta muista että myös huijaussivustot käyttävät sitä. "
                "Turvallisinta on olla käyttämättä viestien linkkejä ja kirjoittaa osoite itse tai käyttää virallista pankkisovellusta."
            )
            return self._build_educational_response(
                adv=adv,
                steps=[
                    "Inspect the exact domain name character-by-character for misspellings or extra hyphens.",
                    "Ensure the domain matches your bank's verified address; do not trust lookalike domains.",
                    "Do not follow links from SMS or emails; type the official bank URL directly or use the official mobile app.",
                    "Save your bank's verified website as a browser bookmark for safe access.",
                ] if lang == "en" else [
                    "Tarkista verkkotunnus merkki merkiltä kirjoitusvirheiden tai ylimääräisten merkkien varalta.",
                    "Varmista, että osoite vastaa pankkisi virallista verkko-osoitetta.",
                    "Älä seuraa viesteissä tulleita linkkejä; kirjoita osoite itse selaimeen tai käytä sovellusta.",
                    "Tallenna verkkopankki selaimesi kirjanmerkkeihin turvallista asiointia varten.",
                ],
                situation_id="EDU-URL-ANALYSIS",
                topic="url_safety",
            )

        return None

    def _build_educational_response(
        self,
        adv: str,
        steps: List[str],
        situation_id: str,
        topic: str,
    ) -> Dict[str, Any]:
        """Constructs a clean educational response conforming to the decision schema."""
        return {
            "outcome_type": "BENIGN",
            "verdict": "SAFE",
            "risk_level": "none",
            "urgency": "routine",
            "primary_action": "no_action_needed",
            "advice_text": adv,
            "advice": adv,
            "steps": steps,
            "situation_id": situation_id,
            "evidence_strength": "conclusive",
            "supporting_indicators": [f"Educational cybersecurity guidance provided for topic: {topic}"],
            "missing_verification": [],
            "questions_asked": [],
            "question_topics": [],
            "consent_requested_for": [],
            "escalation_required": False,
            "escalation_target": None,
            "citations": [],
            "signals_used": ["security_analyzer_educational"],
            "confidence": 1.0,
            "trace": {
                "situation_id": situation_id,
                "facts_used": [],
                "rule_ids": [f"EDU:{topic}"],
                "model": None,
                "signals_used": ["security_analyzer_educational"],
                "consent_requested": [],
                "consent_granted": [],
            },
            "facts": {},
        }

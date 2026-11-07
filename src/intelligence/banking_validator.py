# -*- coding: utf-8 -*-
"""Banking Communication and Employee Validation Engine for Since AI.

Implements rigorous identity, channel, and content validation across 15 banking scenarios:
1. Verified bank employee communicating through an authenticated/authorized channel.
2. Genuine bank email from a verified sender.
3. Legitimate bank transaction notification.
4. Genuine password-reset notification.
5. Genuine bank fraud alert.
6. Legitimate bank security notification.
7. Legitimate official bank URL.
8. Genuine but urgent bank communication.
9. Unverified person claiming to be a bank employee.
10. Compromised genuine employee account sending malicious communications.
11. Legitimate bank communication containing a link.
12. Genuine communication containing unusual wording.
13. Fake bank employee attempting to obtain customer information.
14. Messages requesting passwords, OTPs or MFA codes.
15. Messages requesting urgent money transfers.

Enforces 3 Standardized Primary Outcomes:
- BENIGN
- SUSPICIOUS_OR_MALICIOUS
- INCONCLUSIVE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class BankingValidator:
    """Validates banking communications, employee claims, and transaction alerts."""

    def __init__(self):
        # Known official Finnish bank domains (for exact match verification)
        self.official_bank_domains = {
            "op.fi", "nordea.fi", "danskebank.fi", "s-pankki.fi", "aktia.fi",
            "saastopankki.fi", "omasp.fi", "pop-pankki.fi", "handelsbanken.fi"
        }

    def analyze_banking_communication(
        self,
        message: str,
        channel: str = "unknown",
        sender_identity_verified: bool = False,
        links: Optional[List[str]] = None,
        account_compromise_suspected: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Analyzes a banking-related communication.
        
        Returns None if message is not banking-related, or structured analysis if it is.
        """
        t = message.lower()
        links = links or re.findall(r"https?://[^\s]+", message)

        # Detect banking domain presence
        is_banking = bool(re.search(
            r"\b(pank[a-zäö]*|bank[a-zäö]*|verkkopank[a-zäö]*|tili[a-zäö]*|lain[a-zäö]*|account[a-zäö]*|loan[a-zäö]*|gold\s*card|credit\s*card|kort[a-zäö]*|siirto|transfer|iban|otp|mfa|tunnusluk[a-zäö]*)\b",
            t,
            re.IGNORECASE,
        ))
        if not is_banking:
            return None

        # Critical attack triggers that immediately make communication SUSPICIOUS_OR_MALICIOUS
        asks_credentials = bool(re.search(
            r"(?:salasana|password|pin|tunnusluku|pankkitunnus|bankid|mobiiliavain|koodi|code|otp|mfa|cvv|cvc|approve.*(?:login|prompt)|accept.*prompt|approve.*mobiiliavain|vahvista.*kirjautumi|kuittaa.*kirjautumi|hyväksy.*kirjautumi)",
            t,
            re.IGNORECASE,
        ))
        asks_money_transfer = bool(re.search(
            r"(?:siirrä\s+(?:rahaa|varat|summa)|transfer\s+(?:funds|money|amount)|turvatil|safe\s*account|maksa\s+heti|urgent\s+wire)",
            t,
            re.IGNORECASE,
        ))
        unsolicited_inbound_call = bool(re.search(
            r"(?:soitti|puhelu|soittaja|called\s+me|inbound\s+call|claimed\s+to\s+be\s+(?:a\s+)?bank\s+employee|sanoi\s+olevansa\s+pankista)",
            t,
            re.IGNORECASE,
        ))
        remote_access_request = bool(re.search(
            r"(?:anydesk|teamviewer|etätuki|remote\s+support|asenna.*ohjelma|quicksupport)",
            t,
            re.IGNORECASE,
        ))

        # Check links against official bank domains
        has_suspicious_link = False
        has_official_link = False
        for link in links:
            # Extract hostname
            m = re.search(r"https?://([^/]+)", link)
            if m:
                host = m.group(1).lower()
                if any(host == d or host.endswith("." + d) for d in self.official_bank_domains):
                    has_official_link = True
                else:
                    has_suspicious_link = True

        # -------------------------------------------------------------
        # Evaluate Scenarios
        # -------------------------------------------------------------

        # Scenario 14: Requests passwords, OTPs, or MFA codes -> SUSPICIOUS_OR_MALICIOUS
        if asks_credentials:
            return {
                "is_banking": True,
                "classification": "SUSPICIOUS_OR_MALICIOUS",
                "evidence_strength": "conclusive",
                "supporting_indicators": [
                    "Requests sensitive authentication credentials, passwords, or OTP/MFA codes.",
                    "Legitimate financial institutions never ask customers to disclose passwords or verification codes.",
                ],
                "missing_verification": [],
                "explanation": (
                    "Banks and financial institutions will NEVER ask you to disclose your passwords, PINs, "
                    "or one-time security codes. Any message or call requesting these is a critical fraud attempt."
                ),
                "recommended_action": "isolate_and_block",
                "safe_next_step": "Hang up or delete the message immediately. Do not share any codes. Contact your bank via the number on your payment card.",
            }

        # Scenario 15: Requests urgent money transfers or 'safe account' -> SUSPICIOUS_OR_MALICIOUS
        if asks_money_transfer:
            return {
                "is_banking": True,
                "classification": "SUSPICIOUS_OR_MALICIOUS",
                "evidence_strength": "conclusive",
                "supporting_indicators": [
                    "Requests an urgent transfer of money or moving funds to a 'safe account'.",
                    "There is no such thing as a 'safe account' at another bank for protecting compromised funds.",
                ],
                "missing_verification": [],
                "explanation": (
                    "Demands to move money urgently or transfer funds to a 'safe account' are definite signs of "
                    "authorized push payment (APP) fraud. Banks never instruct customers to move funds to protect them."
                ),
                "recommended_action": "verify_via_official_channel",
                "safe_next_step": "Refuse to transfer any money. Contact your bank immediately using the verified phone number printed on your card.",
            }

        # Scenario 10: Compromised Genuine Employee Account
        if account_compromise_suspected:
            return {
                "is_banking": True,
                "classification": "SUSPICIOUS_OR_MALICIOUS",
                "evidence_strength": "high",
                "supporting_indicators": [
                    "Genuine sender address used, but communication exhibits abnormal behavioral patterns.",
                    "An authenticated employee email account may have been hijacked (Business Email Compromise).",
                ],
                "missing_verification": ["Out-of-band phone confirmation with known representative"],
                "explanation": (
                    "Even if an email originates from a genuine bank or vendor domain, the individual account "
                    "may be compromised by attackers. Treat unusual payment or account requests with extreme caution."
                ),
                "recommended_action": "verify_via_official_channel",
                "safe_next_step": "Do not reply to the email. Call the bank or contact person on a pre-existing trusted telephone number.",
            }

        # Scenario 9 & 13: Unverified Person Claiming to be Bank Employee (Inbound Phone Call)
        if unsolicited_inbound_call and not sender_identity_verified:
            return {
                "is_banking": True,
                "classification": "INCONCLUSIVE",
                "evidence_strength": "medium",
                "supporting_indicators": [
                    "Unsolicited inbound call from an individual claiming to represent a bank.",
                    "Caller ID can be forged/spoofed by scammers to display official phone numbers.",
                    "No cryptographic or channel authentication exists on standard telephone voice calls.",
                ],
                "missing_verification": [
                    "Cryptographic identity authentication",
                    "Confirmation in authenticated mobile banking app",
                    "Independent outbound call callback verification",
                ],
                "explanation": (
                    "An inbound caller claiming to be a bank employee cannot be verified by voice alone, as caller ID "
                    "is easily spoofed. Even if offering loans or card upgrades, you must independently verify the offer."
                ),
                "recommended_action": "verify_via_official_channel",
                "safe_next_step": "Do not disclose personal data or agree to offers on the call. Check your authenticated bank app or call customer service on the back of your card.",
            }

        # Scenario 1 & 3: Verified channel, verified sender, legitimate notification
        if sender_identity_verified or (channel in ("in_app", "authenticated_session")):
            if not has_suspicious_link and not asks_credentials:
                return {
                    "is_banking": True,
                    "classification": "BENIGN",
                    "evidence_strength": "high",
                    "supporting_indicators": [
                        "Message received through verified authenticated banking session or official app channel.",
                        "No credential harvesting, external suspicious links, or unauthorized transfer requests.",
                    ],
                    "missing_verification": [],
                    "explanation": (
                        "Communication is sent within an authenticated banking session without suspicious links or "
                        "demands for sensitive credentials. It matches legitimate operational notifications."
                    ),
                    "recommended_action": "proceed_normally",
                    "safe_next_step": "Proceed normally within your authenticated banking application.",
                }

        # Scenario 7 & 11: Official vs Suspicious links
        if has_suspicious_link:
            return {
                "is_banking": True,
                "classification": "SUSPICIOUS_OR_MALICIOUS",
                "evidence_strength": "high",
                "supporting_indicators": [
                    "Communication includes a link directing to an unauthorized third-party domain.",
                    "Impersonates a bank while directing user to an unofficial web address.",
                ],
                "missing_verification": [],
                "explanation": (
                    "The link in this banking communication does not belong to the official bank domain. "
                    "This is a phishing attempt designed to intercept login credentials."
                ),
                "recommended_action": "do_not_interact_and_delete",
                "safe_next_step": "Do not click or open the link. Delete the message and navigate to the bank website manually.",
            }

        # Scenario 2, 4, 5, 6: Genuine notice without links directing user to open own app
        if not links and bool(re.search(r"(?:kirjaudu\s+omaan\s+sovellukseen|open\s+(?:your\s+)?app|new\s+message\s+in\s+online\s+bank|uusi\s+viesti\s+verkkopankissa)", t)):
            return {
                "is_banking": True,
                "classification": "BENIGN",
                "evidence_strength": "high",
                "supporting_indicators": [
                    "Notification informs of an update without including external clickable links or requesting data.",
                    "Instructs user to verify within their own existing banking application.",
                ],
                "missing_verification": [],
                "explanation": (
                    "This notification conforms to modern banking security standards by avoiding external links and "
                    "advising you to check your account directly inside the official app."
                ),
                "recommended_action": "proceed_normally",
                "safe_next_step": "Open your official banking app directly from your phone to check the message.",
            }

        # Transaction receipt / confirmation without links or requests
        if not links and not asks_credentials and not asks_money_transfer and not unsolicited_inbound_call:
            if bool(re.search(r"(?:käsitelty\s+onnistuneesti|processed\s+successfully|maksettu|completed\s+successfully|vastaanotettu|kuitti|kuitattu|saldo)", t)):
                return {
                    "is_banking": True,
                    "classification": "BENIGN",
                    "evidence_strength": "high",
                    "supporting_indicators": [
                        "Informational transaction confirmation receipt with no external links.",
                        "No credentials or action required from the user.",
                    ],
                    "missing_verification": [],
                    "explanation": "This is a standard informational transaction confirmation notification.",
                    "recommended_action": "proceed_normally",
                    "safe_next_step": "You can verify the transaction record in your account history inside your banking app.",
                }

        # Default fallback for ambiguous banking notices without sufficient evidence -> INCONCLUSIVE
        return {
            "is_banking": True,
            "classification": "INCONCLUSIVE",
            "evidence_strength": "insufficient",
            "supporting_indicators": [
                "Communication references banking matters but sender identity and transport security are unverified.",
            ],
            "missing_verification": [
                "Sender identity proof",
                "Authentication headers (SPF/DKIM/DMARC for email, in-app session for mobile)",
                "Independent confirmation in official banking app",
            ],
            "explanation": (
                "There is insufficient evidence to determine whether this communication is genuine or fraudulent. "
                "Because scammers can mimic banks convincingly, you should treat it as unverified."
            ),
            "recommended_action": "verify_via_official_channel",
            "safe_next_step": "Do not click any links or share information. Verify the notification directly in your official banking app.",
        }

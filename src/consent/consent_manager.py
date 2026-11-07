# -*- coding: utf-8 -*-
"""Consent and Privacy Management Module for DNA Digital Security Assistant.
Ensures strict data minimization, handles pre-granted permissions,
tracks consent requests, and eliminates unnecessary sensitive signal access.
"""
from typing import Any, Dict, List, Optional, Set, Tuple
from src.intelligence.signal_fusion import FusedContext, matches_any
from src.intelligence.benign_classifier import is_benign_control

CONSENT_EXPLANATIONS = {
    "subscription.recent_events": {
        "fi": "Saanko tarkistaa liittymäsi viimeaikaiset tapahtumat selvittääkseni mahdolliset SIM-kortin muutokset?",
        "en": "May I check your subscription's recent events to check for any unexpected SIM changes?",
        "sv": "Får jag kontrollera de senaste händelserna på ditt abonnemang för att upptäcka eventuella SIM-ändringar?",
    },
    "device.recent_app_installs": {
        "fi": "Saanko tarkistaa laitteelle äskettäin asennetut sovellukset mahdollisen haittaohjelman varalta?",
        "en": "May I inspect recently installed apps on your device to check for potential malware?",
        "sv": "Får jag kontrollera nyligen installerade appar på din enhet för att undersöka skadlig programvara?",
    },
    "device.security_findings": {
        "fi": "Saanko tarkistaa laitteen tietoturvalöydökset ja sovellusoikeudet?",
        "en": "May I check device security findings and accessibility permissions?",
        "sv": "Får jag kontrollera enhetens säkerhetsfynd och behörigheter?",
    },
    "operator_account.recent_logins": {
        "fi": "Saanko tarkistaa viimeaikaiset kirjautumiset operaattoritilillesi?",
        "en": "May I check recent logins to your operator account to verify active sessions?",
        "sv": "Får jag kontrollera de senaste inloggningarna på ditt operatörskonto?",
    },
    "business.staff_accounts": {
        "fi": "Saanko tarkistaa yrityksen henkilöstötilit ja käyttöoikeudet?",
        "en": "May I review your company's staff accounts and access permissions?",
        "sv": "Får jag granska företagets personalkonton och behörigheter?",
    },
    "subscription.network_status": {
        "fi": "Saanko tarkistaa liittymäsi verkkoyhteyden tilan?",
        "en": "May I check your subscription network connection status?",
        "sv": "Får jag kontrollera nätverksstatusen för ditt abonnemang?",
    },
}

class ConsentManager:
    @staticmethod
    def get_consent_request_text(fields: List[str], lang: str = "fi") -> str:
        """Generates a polite consent request in the user's language."""
        lang = lang if lang in ("fi", "en", "sv") else "fi"
        parts = []
        for f in fields:
            exp = CONSENT_EXPLANATIONS.get(f, {}).get(lang)
            if exp:
                parts.append(exp)
        if not parts:
            default = {
                "fi": "Saanko luvan tarkistaa tarvittavat järjestelmätiedot tilanteen selvittämiseksi?",
                "en": "May I have permission to check the relevant system signals to assist you?",
                "sv": "Får jag tillstånd att kontrollera nödvändiga systemuppgifter för att utreda situationen?",
            }
            return default.get(lang, default["fi"])
        return " ".join(parts)

    @staticmethod
    def determine_necessary_signals(ctx: FusedContext) -> List[str]:
        """Identifies sensitive signals that are genuinely necessary for the case."""
        # Genuine benign controls do not need sensitive signals (except order verification)
        t = ctx.full_text
        j = ctx.journey
        req = set(ctx.requires_consent)
        nec = set()

        if j == "breach_notice":
            if matches_any(t, [r"seurantasovellu|tracking app|stalk|\bex\b|entinen kumppani|spionprogram|fd partner"]):
                if "device.recent_app_installs" in req:
                    nec.add("device.recent_app_installs")
            if matches_any(t, [r"esim|sim-kort|puhelin.*toimi|ei kenttää|no service|siirtokoodi|ingen täckning"]):
                if "subscription.recent_events" in req:
                    nec.add("subscription.recent_events")
            if matches_any(t, [r"uusi laite|new device|malaga|espanja|ip-osoite|tuntematon laite|unrecognized device|okänd enhet"]) and not matches_any(t, [r"vahvistuspyyntö|mfa|kaksivaiheisen|authenticator"]):
                if "operator_account.recent_logins" in req:
                    nec.add("operator_account.recent_logins")

        elif j == "suspicious_call":
            if matches_any(t, [r"sim-päivity|sim upgrade|sim-uppgradering|sim-kort|esim|operaattor|operatör|vahvistuskoodi|kod"]):
                if "subscription.recent_events" in req:
                    nec.add("subscription.recent_events")

        elif j == "clicked_link":
            if matches_any(t, [r"etätu|ohjas|hallit|remote|controlled my|anydesk|teamviewer|turvallisuustuki|quicksupport|fjärr"]):
                if "device.security_findings" in req:
                    nec.add("device.security_findings")
            elif matches_any(t, [r"\.apk|asens|install|lata|tuntematon lähde|unknown source|sovellus|laddade ner"]):
                if "device.recent_app_installs" in req:
                    nec.add("device.recent_app_installs")

        elif j == "smb_incident":
            if matches_any(t, [r"irtisan|läht|entinen työntekij|former employee|employee who left|anställd som slutade|slutade"]):
                if "business.staff_accounts" in req:
                    nec.add("business.staff_accounts")
            if matches_any(t, [r"tilausvahvistus|order confirmation|uutta liittym|viisi uutta|five new|subscriptions|nya abonnemang"]):
                if "subscription.recent_events" in req:
                    nec.add("subscription.recent_events")
                if "operator_account.recent_logins" in req and matches_any(t, [r"viisi|five|5|odottamaton|unexpected|lupa|tuntematon"]):
                    nec.add("operator_account.recent_logins")

        return sorted(nec)

    @staticmethod
    def get_signals_and_consent(ctx: FusedContext, is_multi_turn: bool = False, granted_in_conv: Optional[Set[str]] = None) -> Tuple[List[str], List[str]]:
        """Returns (signals_used, consent_requested_for)."""
        granted_in_conv = granted_in_conv or set()
        
        # Base non-sensitive signals always used when present
        used = ["artifact"]
        if ctx.link_verdict:
            used.append("link_check")
        if ctx.call_warning:
            used.append("call_warning")
            
        nec_sensitive = ConsentManager.determine_necessary_signals(ctx)
        pre_granted = set(ctx.pre_granted)
        consent_requested = []
        
        for sig in nec_sensitive:
            if sig in pre_granted:
                used.append(sig)
            elif is_multi_turn:
                if sig in granted_in_conv:
                    used.append(sig)
                else:
                    consent_requested.append(sig)
            else:
                # In single-turn, request consent and self-report
                consent_requested.append(sig)
                used.append(sig)
                
        return sorted(set(used)), sorted(set(consent_requested))

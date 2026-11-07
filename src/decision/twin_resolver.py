# -*- coding: utf-8 -*-
"""Twin and Ambiguity Resolver for DNA Digital Security Assistant.
Detects scenarios where visible inputs require decisive hidden facts,
selects the exact question topic, and defines safe single-turn fallbacks.
"""
from typing import Any, Dict, List, Optional, Tuple
from src.intelligence.signal_fusion import FusedContext, matches_any
from src.intelligence.benign_classifier import is_benign_control

# Standard questions per topic in FI, EN, SV
QUESTIONS = {
    "self_initiated": {
        "fi": "Tilasitko tai teitkö tämän muutoksen itse?",
        "en": "Did you order or make this change yourself?",
        "sv": "Beställde eller gjorde du ändringen själv?",
    },
    "code_shared": {
        "fi": "Kerroitko soittajalle jonkin koodin?",
        "en": "Did you give the caller any code?",
        "sv": "Gav du uppringaren någon kod?",
    },
    "credentials_entered": {
        "fi": "Kirjauduitko verkkopankkiin tai syötitkö salasanan?",
        "en": "Did you log in to your bank or type a password?",
        "sv": "Loggade du in på banken eller skrev du ett lösenord?",
    },
    "card_details_entered": {
        "fi": "Syötitkö sivulle korttitietoja tai maksoitko jotain?",
        "en": "Did you enter card details or pay anything on the page?",
        "sv": "Skrev du in kortuppgifter eller betalade du något?",
    },
    "payment_status": {
        "fi": "Onko maksu jo maksettu?",
        "en": "Has the payment already been made?",
        "sv": "Är betalningen redan gjord?",
    },
    "app_installed": {
        "fi": "Avasitko tiedoston ja sallitko sisällön tai asensitko jotain?",
        "en": "Did you open the file and enable content or install anything?",
        "sv": "Öppnade du filen och tillät innehåll eller installerade något?",
    },
    "user_safety": {
        "fi": "Oletko fyysisesti turvassa juuri nyt?",
        "en": "Are you physically safe right now?",
        "sv": "Är du fysiskt säker just nu?",
    },
    "link_details": {
        "fi": "Voitko kertoa linkin osoitteen?",
        "en": "Can you tell me the link address?",
        "sv": "Kan du berätta länkens adress?",
    },
}

def detect_decisive_question(ctx: FusedContext, facts: Optional[Dict[str, str]] = None) -> Optional[Tuple[str, str]]:
    """Detects if a decisive question must be asked.
    Returns (topic_name, question_text) or None.
    """
    facts = facts or {}
    if is_benign_control(ctx):
        return None

    t = ctx.full_text
    j = ctx.journey
    lang = ctx.language if ctx.language in ("fi", "en", "sv") else "fi"
    
    # 1. Stalking / Monitoring app (Domestic abuse / safety) -> user_safety
    if matches_any(t, [r"\bex\b|entinen kumppani|seurantasovellu|tracking app|stalk"]):
        if "user_safety" not in facts:
            return "user_safety", QUESTIONS["user_safety"][lang]
            
    # 2. eSIM swap / SIM takeover -> self_initiated
    if j == "breach_notice" and (ctx.has_esim_activation or ctx.network_service == "no_service" or matches_any(t, [r"esim|sim-kort|puhelin.*toimi|ei kenttää|no service"])):
        if "self_initiated" not in facts and not matches_any(t, [r"itse tilasin|tilasin itse|i ordered.*myself"]):
            return "self_initiated", QUESTIONS["self_initiated"][lang]
            
    # 3. Operator SIM upgrade call offering 5G / asking for code -> code_shared
    if j == "suspicious_call" and (ctx.has_sim_transfer_code or matches_any(t, [r"sim-päivity|sim upgrade|sim-uppgradering|sim-kort|esim|operaattor.*koodi|operator.*code"])):
        if "code_shared" not in facts:
            return "code_shared", QUESTIONS["code_shared"][lang]
            
    # 4. Bank impostor call asking for code / verification -> code_shared
    # Exclude police safe account and genuine bank verification calls
    if j == "suspicious_call" and matches_any(t, [r"pankin turva|turvallisuusosasto|pankki.*koodi|bank.*code|verkkopankkitunnuk"]):
        if not matches_any(t, [r"poliisi|police|turvatili|safe account|ei kysynyt mitään|didn't ask"]):
            if "code_shared" not in facts:
                return "code_shared", QUESTIONS["code_shared"][lang]
            
    # 5. Remote support session -> credentials_entered
    # Exclude payment terminal support
    if matches_any(t, [r"etätu|remote support|controlled my|anydesk|teamviewer|quicksupport|fjärr"]) and not matches_any(t, [r"maksupääte|terminal|maksukort"]):
        if "credentials_entered" not in facts and not matches_any(t, [r"sovittu etätuki|tilattu it-tuki"]):
            return "credentials_entered", QUESTIONS["credentials_entered"][lang]

    # 6. Clicked parcel / payment link -> card_details_entered
    if j == "clicked_link" and matches_any(t, [r"\bpaketti\b|\bparcel\b|\btulli\b|\bcustoms\b|\bposti\b|postnord|toimitusmaksu|delivery fee"]):
        if not matches_any(t, [r"postilaatikko|mailbox|sähköposti.*täynnä"]):
            if "card_details_entered" not in facts and not matches_any(t, [r"syötin kortin|maksoin jo|en syöttänyt"]):
                return "card_details_entered", QUESTIONS["card_details_entered"][lang]

    # 7. SME CEO fraud / urgent invoice -> payment_status
    if j == "smb_incident" and matches_any(t, [r"toimitusjohtaja|ceo\b|vd\b|\bpomo\b|urgent.*transfer|kiireellinen.*maksu"]):
        if "payment_status" not in facts and not matches_any(t, [r"maksoin jo|already paid|ei maksettu|unpaid"]):
            return "payment_status", QUESTIONS["payment_status"][lang]

    # 8. SME attachment (.zip, .docm) -> app_installed
    if j == "smb_incident" and matches_any(t, [r"\.zip|\.docm|makro|invoice.*zip"]):
        if "app_installed" not in facts:
            return "app_installed", QUESTIONS["app_installed"][lang]

    # 9. SME unexpected SIM order -> self_initiated
    if j == "smb_incident" and (ctx.has_new_sub_order or matches_any(t, [r"tilausvahvistus|order confirmation|uutta liittym|five new|uusia liittymiä|nya abonnemang"])):
        if "self_initiated" not in facts:
            return "self_initiated", QUESTIONS["self_initiated"][lang]

    # 10. Unknown login notice -> self_initiated
    if j == "breach_notice" and matches_any(t, [r"uusi laite|new device|uudelta laitteelta|tuntematon laite|unrecognized device|malaga|espanja"]) and not matches_any(t, [r"kaksivaiheisen|mfa|authenticator|vahvistuspyyntö"]):
        if "self_initiated" not in facts:
            return "self_initiated", QUESTIONS["self_initiated"][lang]

    return None

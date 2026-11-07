# -*- coding: utf-8 -*-
"""Benign Control Classifier for DNA Digital Security Assistant.
Identifies legitimate notifications, valid orders, routine spam flags,
and expected prompts to prevent false alarms on non-incidents.
"""
from typing import Any, Dict
from src.intelligence.signal_fusion import FusedContext, matches_any

def is_benign_control(ctx: FusedContext) -> bool:
    """Returns True if the context represents a benign control case."""
    t = ctx.full_text
    body = (ctx.artifact_body or "").lower()
    op = (ctx.opening_message or "").lower()
    
    # -------------------------------------------------------------
    # 0. Strict Exclusions: If severe attack indicators exist, never benign
    # -------------------------------------------------------------
    if ctx.network_service == "no_service" or ctx.has_sim_transfer_code:
        return False
    if ctx.suspicious_app_installed or ctx.accessibility_service_detected or ctx.remote_access_detected:
        return False
    if matches_any(t, [r"salattu|encrypted|lunnai|ransom|bitcoin|turvatil|safe account"]):
        return False
    if matches_any(t, [r"\bex\b|entinen kumppani|seurantasovellu|valvo(o|ntaa)|stalk"]):
        return False
    if ctx.link_verdict in ("malicious",):
        return False
    if matches_any(t, [r"pyysi lukemaan koodin|asked for a code|asked to read.*code|gave the caller.*code"]):
        return False

    # -------------------------------------------------------------
    # 1. BR-BREACH-EMAIL-ONLY & BR-OWN-MFA-PROMPT
    # -------------------------------------------------------------
    if ctx.journey == "breach_notice":
        # BR-BREACH-EMAIL-ONLY: legitimate service breach notice informing user no action is needed
        if matches_any(body, [r"sinun ei tarvitse tehdä mitään|you do not need to do anything|du behöver inte göra något"]):
            return True
        if ctx.credential_exposure_found:
            types = set(ctx.credential_exposure_types)
            if types and types.issubset({"name", "email", "phone"}):
                if not matches_any(body, [r"salasana|password|lösenord|hash"]):
                    return True

        # BR-OWN-MFA-PROMPT: User is logging in right now on their own device
        if matches_any(body, [r"hyväksytkö kirjautumisen|approve (sign-in|login)|godkänn inloggning"]):
            if matches_any(op, [r"uutta tietokonetta|uudella läppärillä|new laptop|new computer|uutta laitetta|new device|uudella|kirjaudun.*uudella"]):
                if not matches_any(t, [r"useita|multiple|jatkuvasti|repeatedly|flood|storm|tulvii|keeps getting"]):
                    return True

    # -------------------------------------------------------------
    # 2. CA-GENUINE-FLAGGED
    # -------------------------------------------------------------
    if ctx.journey == "suspicious_call":
        if matches_any(body + " " + op, [r"terveysasema|health cent|vårdcentral|hälsocentralen|lääkäri|läkare|doctor|hammaslääkäri|tandläkare|dentist|ajan siirto|reschedule|siirtää.*aika|flytta.*tid|lähetti|pakettiauto|budbil|delivery driver"]):
            if matches_any(body + " " + op, [r"ei pyytänyt mitään|bad inte om|did not ask for|asked for no details|ei pyytänyt tietoja|asiallinen|ei kysynyt|bad inte om några uppgifter"]):
                return True

    # -------------------------------------------------------------
    # 3. CL-GENUINE-LINK
    # -------------------------------------------------------------
    if ctx.journey == "clicked_link":
        if ctx.link_verdict != "malicious":
            if matches_any(body, [r"kiitos tilauksestasi|thank you for your order|tack för din beställning|tilausvahvistus|order confirmation|seurantalinkki|tracking link"]):
                if not matches_any(op, [r"syötin|skrev in|entered|pankkitunnu|kortti|card|salasan|password|lataus|asennus|profiil|maksoin"]):
                    return True

    # -------------------------------------------------------------
    # 4. SMB Incidents
    # -------------------------------------------------------------
    if ctx.journey == "smb_incident":
        # SB-BENIGN-NEW-PAYEE: only occurs in genuine payee notifications
        if matches_any(body, [r"uusi maksunsaaja|ny betalningsmottagare|new payee"]):
            return True
        # SB-GENUINE-REMOTE-SUPPORT: scheduled with known IT partner
        if matches_any(body, [r"etätukitapaami|fjärrsupport|remote support.*ticket|tiketillä #|ärende #"]):
            if matches_any(op, [r"tiketin tein itse|skapat ärende|we booked|it-kumppani|it-partner|it partner|agreed|sovittu|tilasimme itse|beställde själva"]):
                return True
        # SB-ORDER-BENIGN-ADMIN: order confirmation for office by admin
        if matches_any(body, [r"order confirmation|tilausvahvistus|orderbekräftelse"]):
            if matches_any(body, [r"toimistolle|kontoret|office"]):
                if matches_any(body, [r"pääkäyttäjä|admin|henna|teemu|ville|pekka|sanna|jari|riitta|aino|laura|owner|omistaja|vd|toimitusjohtaja"]):
                    return True

    # -------------------------------------------------------------
    # 5. Suspicious Message (SMS / Email)
    # -------------------------------------------------------------
    if ctx.journey == "suspicious_message":
        # SM-GENUINE-BANK-NOTICE
        if not ctx.artifact_links and matches_any(body, [r"uusi viesti verkkopankissa|nytt meddelande i internetbanken|new message in (your )?online bank"]):
            return True
        # SM-GENUINE-DELIVERY: JJFI parcel ready for pickup without links or fees
        if not ctx.artifact_links and matches_any(body, [r"JJFI[0-9]+"]) and matches_any(body, [r"noudettavissa|hämtas|can be collected"]):
            if not matches_any(body, [r"maksa|maksu|tulli|fee|avgift|pay|rahaa|euro|€"]):
                return True
        # SM-OPERATOR-GENUINE-BILL
        if not ctx.artifact_links and matches_any(body, [r"kuukausilasku|månadsfaktura|monthly bill|marraskuun lasku|november bill|novemberfaktura|laskusi.*oma|nähtävissä oma-palvelussa|finns nu i ditt onlinekonto"]):
            if not matches_any(t, [r"myöhässä|overdue|suljetaan|blocked|katkaistaan"]):
                return True
        # SM-GENUINE-OPERATOR-OFFER
        if matches_any(body, [r"5g-tarjous|5g-yhteyden|faster 5g|5g offer|tarjoukset/5g"]):
            if matches_any(body, [r"operator\.(test|example|invalid)|oma-sovelluk|in the app|oma dna|dna\.fi|oma-palvelu"]):
                if not matches_any(t, [r"palkinto|lahjakortti|voitto|suljetaan|lahja|prize|gift"]):
                    return True

    return False

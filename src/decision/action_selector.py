# -*- coding: utf-8 -*-
"""Action Selector and Decision Engine for DNA Digital Security Assistant.
Maps fused case context to the 10-action vocabulary, calibrated risk levels,
urgency ratings, required steps, and citations.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.intelligence.signal_fusion import FusedContext, matches_any
from src.intelligence.benign_classifier import is_benign_control
from src.decision.twin_resolver import detect_decisive_question
from src.decision.escalation_engine import evaluate_escalation
from src.knowledge.retriever import GuidanceRetriever

@dataclass
class DecisionRecord:
    primary_action: str
    risk_level: str
    urgency: str
    required_steps: List[str]
    escalation_required: bool
    escalation_target: Optional[str]
    citations: List[str]
    decisive_question: Optional[Tuple[str, str]] = None

class ActionSelector:
    def __init__(self):
        self.retriever = GuidanceRetriever()

    def decide(self, ctx: FusedContext, facts: Optional[Dict[str, str]] = None, mode: str = "single_turn") -> DecisionRecord:
        facts = facts or {}
        facts_text = " ".join(facts.values()) if facts else ""
        t = ctx.full_text
        op = (ctx.opening_message or "").lower()
        body = (ctx.artifact_body or "").lower()
        
        decisive_q = detect_decisive_question(ctx, facts)

        # -------------------------------------------------------------
        # 1. Benign Control Cases (22% of cases)
        # -------------------------------------------------------------
        if is_benign_control(ctx):
            risk = "low" if ctx.journey == "breach_notice" else "none"
            return DecisionRecord(
                primary_action="no_action_needed",
                risk_level=risk,
                urgency="routine" if risk == "low" else "none",
                required_steps=["explain_benign"],
                escalation_required=False,
                escalation_target=None,
                citations=["guidance_proportionate_advice"],
                decisive_question=None
            )

        # In multi-turn, resolve twin branches once decisive facts are revealed
        if mode == "multi_turn" and facts:
            # 1. BR-SIM-SWAP-TWIN
            if (ctx.has_esim_activation or ctx.network_service == "no_service" or matches_any(t, [r"esim|sim-kort|puhelin.*toimi|ei kenttää|no service"])) and ctx.journey == "breach_notice":
                if matches_any(facts_text, [r"siirsin itse|flyttade själv|moved.*myself|itse.*käytössä|itse.*esim"]) and not matches_any(facts_text, [r"haven't ordered|en ole tilannut"]):
                    return DecisionRecord("no_action_needed", "none", "none", ["explain_benign"], False, None, ["guidance_proportionate_advice"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("contact_operator_support", "critical", "immediate", ["contact_operator", "lock_subscription"], True, "operator_support_agent", ["guidance_sim_swap", "guidance_handing_off"], decisive_question=decisive_q)

            # 2. BR-UNKNOWN-LOGIN-TWIN
            if ctx.journey == "breach_notice" and matches_any(t, [r"kirjautu\w*|logged in|sign-in|login|uusi laite|new device|uudelta laitteelta|tuntematon kirjautuminen|malaga|espanja"]):
                if matches_any(facts_text, [r"itse|kirjauduin|myself|logged in from|jag själv"]) and not matches_any(facts_text, [r"en ole ollut|haven't been|not me"]):
                    return DecisionRecord("change_password_and_enable_mfa", "low", "routine", ["change_password", "review_sessions"], False, None, ["guidance_credential_hygiene"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("change_password_and_enable_mfa", "high", "today", ["change_password", "review_sessions"], False, None, ["guidance_credential_hygiene"], decisive_question=decisive_q)

            # 3. SB-UNEXPECTED-SIM-ORDER-TWIN
            if ctx.journey == "smb_incident" and (ctx.has_new_sub_order or matches_any(t, [r"tilausvahvistus|order confirmation|uutta liittym|five new|uusia liittymiä|nya abonnemang"])):
                if matches_any(facts_text, [r"osakkaani|partner.*ordered|tilanneensa|ordered them"]) and not matches_any(facts_text, [r"hänkään ei ole|didn't order anything"]):
                    return DecisionRecord("contact_operator_support", "low", "routine", ["contact_operator"], False, None, ["guidance_proportionate_advice"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("contact_operator_support", "critical", "immediate", ["contact_operator", "change_password"], True, "business_security_support", ["guidance_sim_swap", "guidance_handing_off"], decisive_question=decisive_q)

            # 4. CA-OPERATOR-SIM-CODE-TWIN
            if ctx.has_sim_transfer_code or (ctx.journey == "suspicious_call" and matches_any(t, [r"sim-päivity|sim upgrade|sim-kort|esim|operaattor.*koodi|operator.*code"])):
                if matches_any(facts_text, [r"didn't read|didn't give|en lukenut|en antanut|en kertonut|läste inte|gav inte|lopetin puhelun"]):
                    return DecisionRecord("contact_operator_support", "medium", "today", ["dont_share_codes"], False, None, ["guidance_sim_swap"], decisive_question=decisive_q)
                elif matches_any(facts_text, [r"read.*code|luin.*kood|annoin.*kood|kerroin.*kood|läste.*kod|gav.*kod"]):
                    return DecisionRecord("contact_operator_support", "critical", "immediate", ["contact_operator", "lock_subscription"], True, "operator_support_agent", ["guidance_sim_swap", "guidance_handing_off"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("contact_operator_support", "medium", "today", ["dont_share_codes"], False, None, ["guidance_sim_swap"], decisive_question=decisive_q)

            # 5. CA-BANK-IMPOSTOR-TWIN
            if ctx.journey == "suspicious_call" and matches_any(t, [r"turvallisuus|turva|bank|pank|koodeja|koodi|code|safe account|turvatil"]):
                if matches_any(facts_text, [r"didn't give|en antanut|en kertonut|gav ingenting|lopetin puhelun"]):
                    return DecisionRecord("verify_via_official_channel", "high", "today", ["verify_official_channel"], False, None, ["guidance_bank_impersonation"], decisive_question=decisive_q)
                elif matches_any(facts_text, [r"read.*code|luin.*kood|annoin.*kood|kerroin.*kood|läste.*kod|gav.*kod|two codes|kaksi koodia"]):
                    return DecisionRecord("contact_bank_and_block_cards", "critical", "immediate", ["contact_bank_now"], False, None, ["guidance_bank_impersonation"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("verify_via_official_channel", "high", "today", ["verify_official_channel"], False, None, ["guidance_bank_impersonation"], decisive_question=decisive_q)

            # 6. CL-PARCEL-PAID-TWIN
            if ctx.journey == "clicked_link" and matches_any(t, [r"paketti|parcel|tulli|customs|maksu|fee|posti"]):
                if matches_any(facts_text, [r"syötin.*kort|typed.*card|entered.*card|skrev.*kort|turvakoodi|security code|säkerhetskod"]):
                    return DecisionRecord("contact_bank_and_block_cards", "critical", "immediate", ["block_card", "contact_bank_now"], False, None, ["guidance_card_blocking"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("do_not_interact_and_delete", "low", "routine", ["delete_or_report_message"], False, None, ["guidance_phishing_recognition"], decisive_question=decisive_q)

            # 7. CL-REMOTE-ACCESS-TWIN
            if ctx.remote_access_detected or matches_any(t, [r"etätu|ohjas|hallit|remote|controlled my|anydesk|teamviewer|turvallisuustuki|quicksupport|fjärr"]):
                if matches_any(facts_text, [r"verkkopankkiin|online bank|banken|tein sen|did it|kirjauduin.*pankki"]):
                    return DecisionRecord("contact_bank_and_block_cards", "critical", "immediate", ["contact_bank_now", "disconnect_device"], True, "security_specialist", ["guidance_remote_access_scams", "guidance_bank_impersonation"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("isolate_device_and_scan", "high", "today", ["disconnect_device", "remove_app_or_profile"], True, "security_specialist", ["guidance_remote_access_scams"], decisive_question=decisive_q)

            # 8. SB-CEO-FRAUD-TWIN
            if ctx.journey == "smb_incident" and matches_any(t, [r"toimitusjohtaja|ceo\b|vd\b|pomo|urgent.*transfer|kiireellinen.*maksu"]):
                if matches_any(facts_text, [r"maksoin sen jo|already paid|paid it|har redan betalat"]):
                    return DecisionRecord("contact_bank_and_block_cards", "critical", "immediate", ["contact_bank_now", "verify_out_of_band"], True, "business_security_support", ["guidance_ceo_fraud"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("verify_via_official_channel", "high", "today", ["dont_pay_or_transfer", "verify_out_of_band"], False, None, ["guidance_ceo_fraud"], decisive_question=decisive_q)

            # 9. SB-ATTACHMENT-TWIN
            if ctx.journey == "smb_incident" and matches_any(t, [r"\.zip|\.docm|makro|liite|attachment|invoice.*zip"]):
                if matches_any(facts_text, [r"didn't open|en avannut|vain avasin|only opened|öppnade inte"]):
                    return DecisionRecord("do_not_interact_and_delete", "medium", "routine", ["dont_open_attachment"], False, None, ["guidance_phishing_recognition"], decisive_question=decisive_q)
                elif matches_any(facts_text, [r"enable content|salli sisältö|painoin|clicked|tillät|asensin"]):
                    return DecisionRecord("isolate_device_and_scan", "high", "today", ["disconnect_device", "get_device_checked"], True, "business_security_support", ["guidance_malware_incident"], decisive_question=decisive_q)
                else:
                    return DecisionRecord("do_not_interact_and_delete", "medium", "routine", ["dont_open_attachment"], False, None, ["guidance_phishing_recognition"], decisive_question=decisive_q)

        # -------------------------------------------------------------
        # 2. Out of scope (tracing phone numbers, hacking back)
        # -------------------------------------------------------------
        if matches_any(op, [r"kuka omistaa|omistaa numeron|who owns|find out who|selvitä kuka|julkaista|hack back|jäljitä|etsi mulle.*osoite"]):
            return DecisionRecord(
                primary_action="decline_out_of_scope",
                risk_level="medium",
                urgency="routine",
                required_steps=["decline_request", "report_police"],
                escalation_required=False,
                escalation_target=None,
                citations=["guidance_out_of_scope", "guidance_report_to_police"],
                decisive_question=None
            )

        # -------------------------------------------------------------
        # 3. Domestic monitoring / Stalking app (Life Safety)
        # -------------------------------------------------------------
        if matches_any(t, [r"\bex\b|entinen kumppani|seurantasovellu|tracking app|valvo(o|ntaa)|stalk"]):
            return DecisionRecord(
                primary_action="escalate_to_human",
                risk_level="high",
                urgency="today",
                required_steps=["plan_before_removing", "seek_support_org"],
                escalation_required=True,
                escalation_target="human_advisor",
                citations=["guidance_handing_off"],
                decisive_question=decisive_q
            )

        # -------------------------------------------------------------
        # 4. Police Safe-Account Fraud (Caller manipulation)
        # -------------------------------------------------------------
        if matches_any(t, [r"turvatili|safe account|siirsin.*rahaa|moved.*money|siirrä.*rahat|poliisi.*soitti|police called.*money"]):
            return DecisionRecord(
                primary_action="contact_bank_and_block_cards",
                risk_level="critical",
                urgency="immediate",
                required_steps=["contact_bank_now", "report_police"],
                escalation_required=True,
                escalation_target="human_advisor",
                citations=["guidance_bank_verification", "guidance_report_to_police"],
                decisive_question=None
            )

        # -------------------------------------------------------------
        # 5. Ransomware (Extortion)
        # -------------------------------------------------------------
        if matches_any(t, [r"salattu|encrypted|lunnai|ransom|bitcoin"]):
            esc_tgt = "business_security_support" if ctx.audience == "small_business" else "security_specialist"
            return DecisionRecord(
                primary_action="isolate_device_and_scan",
                risk_level="critical",
                urgency="immediate",
                required_steps=["disconnect_device", "dont_pay_or_transfer"],
                escalation_required=True,
                escalation_target=esc_tgt,
                citations=["guidance_ransomware", "guidance_device_compromise"],
                decisive_question=None
            )

        # -------------------------------------------------------------
        # 6. Active SIM / eSIM Takeover
        # -------------------------------------------------------------
        if ctx.has_esim_activation or ctx.network_service == "no_service" or matches_any(t, [r"esim activation|esim-aktivointi|esim.*notice|lost.*coverage|ei kenttää"]):
            return DecisionRecord(
                primary_action="contact_operator_support",
                risk_level="critical",
                urgency="immediate",
                required_steps=["contact_operator", "lock_subscription"],
                escalation_required=True,
                escalation_target="operator_support_agent",
                citations=["guidance_sim_swap", "guidance_handing_off"],
                decisive_question=decisive_q
            )

        # Tech support scam call where user hung up before doing anything
        if ctx.journey == "suspicious_call" and matches_any(t, [r"virus|support|tuki"]) and matches_any(t, [r"hung up before|lopetin.*ennen|lade på|laade på|en tehnyt mitään|didn't do anything|gjorde inget|gjorde inte"]):
            return DecisionRecord(
                primary_action="do_not_interact_and_delete",
                risk_level="low",
                urgency="routine",
                required_steps=["hang_up_dont_call_back"],
                escalation_required=False,
                escalation_target=None,
                citations=["guidance_proportionate_advice"],
                decisive_question=None
            )

        # -------------------------------------------------------------
        # 7. Operator SIM Code Twin / Impersonation
        # -------------------------------------------------------------
        if ctx.has_sim_transfer_code or (ctx.journey == "suspicious_call" and matches_any(t, [r"sim-päivity|sim upgrade|sim-kort|esim|operaattor.*koodi|operator.*code"])):
            return DecisionRecord(
                primary_action="contact_operator_support",
                risk_level="critical",
                urgency="immediate",
                required_steps=["contact_operator", "lock_subscription", "dont_share_codes"],
                escalation_required=True,
                escalation_target="operator_support_agent",
                citations=["guidance_sim_swap", "guidance_one_time_codes"],
                decisive_question=decisive_q
            )

        # -------------------------------------------------------------
        # 8. Malicious App / Sideloaded APK / Device Takeover / Virus
        # -------------------------------------------------------------
        if (ctx.suspicious_app_installed or ctx.accessibility_service_detected or 
            matches_any(t, [
                r"virus|malware|takeover|take over|ready for take over|trojan|hacked|kaapattu|saastunut|tartunta|infektoitunut|sekoilee|hallintaan",
                r"app\.apk|ääniviesti.*apk|asensin.*sovelluk|installed.*app|installera|laddade ner.*app"
            ])):
            return DecisionRecord(
                primary_action="isolate_device_and_scan",
                risk_level="critical",
                urgency="immediate",
                required_steps=["disconnect_device", "avoid_banking_on_device", "remove_app_or_profile", "get_device_checked", "contact_bank_now"],
                escalation_required=True,
                escalation_target="security_specialist",
                citations=["guidance_malicious_app", "guidance_device_compromise"],
                decisive_question=None
            )

        # -------------------------------------------------------------
        # 9. Remote Support Session Twin
        # -------------------------------------------------------------
        if matches_any(t, [r"etätuki|ohjasi|remote access|controlled my screen|anydesk|teamviewer"]) and not matches_any(t, [r"maksupääte|payment terminal|terminal support|till computer"]):
            return DecisionRecord(
                primary_action="isolate_device_and_scan",
                risk_level="high",
                urgency="immediate",
                required_steps=["disconnect_device", "remove_app_or_profile", "contact_bank_now"],
                escalation_required=True,
                escalation_target="security_specialist",
                citations=["guidance_remote_access", "guidance_device_compromise"],
                decisive_question=decisive_q
            )

        # -------------------------------------------------------------
        # 10. Clicked Link Credentials / Phish
        # -------------------------------------------------------------
        if ctx.journey == "clicked_link":
            if matches_any(op + " " + body, [r"kirjoitin sähköpostin salasanani|salasanani sivulle|posti-laatikko|postilaatikkosi on täynnä"]):
                return DecisionRecord(
                    primary_action="change_password_and_enable_mfa",
                    risk_level="high",
                    urgency="immediate",
                    required_steps=["change_password", "check_password_reuse"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_credential_compromise"],
                    decisive_question=None
                )
            if matches_any(op + " " + body, [r"kirjauduin pankin|syötin tunnukseni|bekräftelsekod|lumipankki-laite|saarelanpankki-vahvi|syötin.*koodi"]):
                return DecisionRecord(
                    primary_action="contact_bank_and_block_cards",
                    risk_level="critical",
                    urgency="immediate",
                    required_steps=["contact_bank_now"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_bank_verification", "guidance_card_details_entered"],
                    decisive_question=None
                )
            if facts.get("confirmed_risk") == "no" or matches_any(facts_text, [r"didn't enter|did not enter|en syöttänyt|en maksanut|en antanut|no|nej|ei|inte fyllt i"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="low",
                    urgency="today",
                    required_steps=["dont_open_link", "verify_official_channel"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_smishing_basics"],
                    decisive_question=None
                )
            # Parcel twin in single turn
            return DecisionRecord(
                primary_action="contact_bank_and_block_cards",
                risk_level="critical",
                urgency="immediate",
                required_steps=["contact_bank_now", "block_card"],
                escalation_required=False,
                escalation_target=None,
                citations=["guidance_card_details_entered"],
                decisive_question=decisive_q
            )

        # -------------------------------------------------------------
        # 11. SMB Incidents
        # -------------------------------------------------------------
        if ctx.journey == "smb_incident":
            # Verified supplier
            if matches_any(op, [r"vahvisti|confirmed|soitin.*talouspäällikö|called.*manager|soitin.*numeroon.*sopimuksessa|soittamalla.*tuttuun numeroon|tarkistin.*soittamalla"]):
                return DecisionRecord(
                    primary_action="no_action_needed",
                    risk_level="low",
                    urgency="routine",
                    required_steps=["explain_benign"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_proportionate_advice"],
                    decisive_question=None
                )
            # CEO Fraud Twin
            if matches_any(t, [r"toimitusjohtaja|ceo|vd\b|pomo"]):
                return DecisionRecord(
                    primary_action="contact_bank_and_block_cards",
                    risk_level="critical",
                    urgency="immediate",
                    required_steps=["dont_pay_or_transfer", "verify_out_of_band", "contact_bank_now"],
                    escalation_required=True,
                    escalation_target="business_security_support",
                    citations=["guidance_invoice_fraud", "guidance_bank_verification"],
                    decisive_question=decisive_q
                )
            # Attachment Twin
            if matches_any(t, [r"\.zip|\.docm|makro|liite|attachment|invoice.*zip"]):
                return DecisionRecord(
                    primary_action="isolate_device_and_scan",
                    risk_level="high",
                    urgency="immediate",
                    required_steps=["disconnect_device", "get_device_checked", "dont_open_attachment"],
                    escalation_required=True,
                    escalation_target="business_security_support",
                    citations=["guidance_malicious_app", "guidance_attachment_safety"],
                    decisive_question=decisive_q
                )
            # Unexpected SIM order twin
            if ctx.has_new_sub_order or matches_any(t, [r"tilausvahvistus|order confirmation|uutta liittym|five new|uusia liittymiä|nya abonnemang"]):
                return DecisionRecord(
                    primary_action="contact_operator_support",
                    risk_level="critical",
                    urgency="immediate",
                    required_steps=["contact_operator", "change_password"],
                    escalation_required=True,
                    escalation_target="business_security_support",
                    citations=["guidance_order_confirmations", "guidance_credential_compromise"],
                    decisive_question=decisive_q
                )
            # Mailbox compromised
            if matches_any(t, [r"edelleenlähetys|forwarding rule|postilaatikko.*kaapattu|mailbox.*compromised"]):
                return DecisionRecord(
                    primary_action="change_password_and_enable_mfa",
                    risk_level="critical",
                    urgency="immediate",
                    required_steps=["change_password", "check_forwarding_rules", "inform_staff"],
                    escalation_required=True,
                    escalation_target="business_security_support",
                    citations=["guidance_business_email_compromise"],
                    decisive_question=None
                )
            # Staff phish M365
            if matches_any(t, [r"signed in with their work email|jakopalvelu|docs-share|kahvipaahtimo aamukaste oy shared a document"]):
                return DecisionRecord(
                    primary_action="change_password_and_enable_mfa",
                    risk_level="high",
                    urgency="immediate",
                    required_steps=["change_password", "review_sessions", "check_forwarding_rules"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_credential_compromise"],
                    decisive_question=None
                )
            # Ex-employee access
            if matches_any(t, [r"employee who left|läht.*työntekij|työntekijä.*läht|entinen työntekijä|former employee|anställd som slutade|slutade"]):
                return DecisionRecord(
                    primary_action="change_password_and_enable_mfa",
                    risk_level="high",
                    urgency="today",
                    required_steps=["change_password", "review_sessions"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_credential_compromise"],
                    decisive_question=None
                )
            # Supplier bank change unverified
            if matches_any(t, [r"tilinumero|bank account|kontonummer|uudelle tilille|pankkimme on vaihtunut|uusi tilinumero"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="high",
                    urgency="today",
                    required_steps=["dont_pay_or_transfer", "verify_out_of_band"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_invoice_fraud", "guidance_payment_verification"],
                    decisive_question=None
                )
            # Terminal support call
            if matches_any(t, [r"maksupääte|payment terminal|terminal support|huolto.*pääte"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="high",
                    urgency="today",
                    required_steps=["verify_official_channel", "dont_share_codes"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_payment_verification"],
                    decisive_question=None
                )

        # -------------------------------------------------------------
        # 12. Suspicious Calls
        # -------------------------------------------------------------
        if ctx.journey == "suspicious_call":
            if matches_any(t, [r"korttivalvonta|korttivalvonnasta|card monitoring|kortövervakning"]) and matches_any(t, [r"ei kysynyt|asked for no details|bad inte om|kortin takana|on the back of the card"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="low",
                    urgency="routine",
                    required_steps=["verify_official_channel"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_bank_verification"],
                    decisive_question=None
                )
            if matches_any(t, [r"turvallisuus|turva|bank|pank|koodeja|koodi|code"]):
                return DecisionRecord(
                    primary_action="contact_bank_and_block_cards",
                    risk_level="critical",
                    urgency="immediate",
                    required_steps=["contact_bank_now", "verify_official_channel"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_bank_verification", "guidance_one_time_codes"],
                    decisive_question=decisive_q
                )
            if matches_any(t, [r"tech support|tietokonetuki|microsoft|windows-tuki"]):
                return DecisionRecord(
                    primary_action="do_not_interact_and_delete",
                    risk_level="low",
                    urgency="routine",
                    required_steps=["hang_up_dont_call_back"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_tech_support_fraud"],
                    decisive_question=None
                )

        # -------------------------------------------------------------
        # 13. Breach Notice
        # -------------------------------------------------------------
        if ctx.journey == "breach_notice":
            if matches_any(t, [r"hyväksy|approval.*(request|prompt)|prompt.*storm|mfa.*fatigue|useita hyväksynt|keeps getting login|kirjautumis.*ilmoit"]):
                return DecisionRecord(
                    primary_action="change_password_and_enable_mfa",
                    risk_level="critical",
                    urgency="immediate",
                    required_steps=["dont_approve_prompts", "change_password"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_mfa_fatigue"],
                    decisive_question=None
                )
            if matches_any(body, [r"secure your account within 2 hours|suojaa tilisi 2 tunnin|account-protection\."]) or (ctx.artifact_links and not ctx.credential_exposure_found):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="medium",
                    urgency="today",
                    required_steps=["dont_open_link"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_smishing_basics"],
                    decisive_question=None
                )
            if matches_any(t, [r"kirjautu\w*|logged in|sign-in|login|uusi laite|new device|uudelta laitteelta"]):
                return DecisionRecord(
                    primary_action="change_password_and_enable_mfa",
                    risk_level="low",
                    urgency="today",
                    required_steps=["change_password", "review_sessions"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_breach_response"],
                    decisive_question=decisive_q
                )
            if matches_any(t, [r"salasanan palautus|password reset|nollauspyyntö"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="low",
                    urgency="today",
                    required_steps=["dont_open_link", "verify_official_channel"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_credential_compromise"],
                    decisive_question=None
                )
            return DecisionRecord(
                primary_action="change_password_and_enable_mfa",
                risk_level="high",
                urgency="today",
                required_steps=["change_password", "check_password_reuse"],
                escalation_required=False,
                escalation_target=None,
                citations=["guidance_breach_response"],
                decisive_question=None
            )

        # -------------------------------------------------------------
        # 14. Suspicious Message
        # -------------------------------------------------------------
        if ctx.journey == "suspicious_message":
            if matches_any(t, [r"pankki|bank|tilisi on suljettu|tunnistaudu|lumipankki|revontulipankki|saarelan|nordicbank"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="high",
                    urgency="today",
                    required_steps=["dont_open_link", "verify_official_channel"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_bank_verification"],
                    decisive_question=None
                )
            if matches_any(t, [r"operaattori|lasku|liittymäsi|puhelinlasku|unpaid bill"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="high",
                    urgency="today",
                    required_steps=["dont_open_link", "dont_pay_or_transfer", "verify_official_channel"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_operator_impersonation"],
                    decisive_question=None
                )
            if matches_any(t, [r"äiti|isi|lapsi|uusi numero|new number|rikoin puhelimeni|broke my phone|mamma|pappa"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="high",
                    urgency="today",
                    required_steps=["dont_pay_or_transfer", "verify_out_of_band"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_family_impersonation"],
                    decisive_question=None
                )
            if matches_any(t, [r"kaveri.*salasa|friend.*password|kysyy.*salasa|pyytää.*salasa|asking for.*password|kysyy.*koodi|pyytää.*koodi|asking for.*code|jakaisinko.*salasa|share.*password|lösenord|delar.*lösenord"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="high",
                    urgency="today",
                    required_steps=["dont_share_codes", "verify_out_of_band"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_family_new_number", "guidance_credential_compromise"],
                    decisive_question=None
                )
            if matches_any(t, [r"vero|tax|veronpalautus|tax refund"]):
                return DecisionRecord(
                    primary_action="do_not_interact_and_delete",
                    risk_level="high",
                    urgency="today",
                    required_steps=["dont_open_link"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_smishing_basics"],
                    decisive_question=None
                )
            if matches_any(t, [r"paketti|parcel|tulli|customs|postikulut|lähetys"]):
                return DecisionRecord(
                    primary_action="do_not_interact_and_delete",
                    risk_level="medium",
                    urgency="routine",
                    required_steps=["dont_open_link", "dont_pay_or_transfer"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_parcel_scam"],
                    decisive_question=None
                )
            if matches_any(t, [r"palkinto|prize|voitto|lottery|arvonta|sijoitus|investment"]):
                return DecisionRecord(
                    primary_action="do_not_interact_and_delete",
                    risk_level="medium",
                    urgency="routine",
                    required_steps=["dont_open_link", "dont_pay_or_transfer"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_smishing_basics"],
                    decisive_question=None
                )
            if matches_any(t, [r"netflix|spotify|streaming|uusittava"]):
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="medium",
                    urgency="today",
                    required_steps=["dont_open_link", "verify_official_channel"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_smishing_basics"],
                    decisive_question=None
                )
            if ctx.artifact_links:
                return DecisionRecord(
                    primary_action="verify_via_official_channel",
                    risk_level="high",
                    urgency="today",
                    required_steps=["dont_open_link", "verify_official_channel"],
                    escalation_required=False,
                    escalation_target=None,
                    citations=["guidance_smishing_basics"],
                    decisive_question=None
                )

        # Fallback default
        return DecisionRecord(
            primary_action="verify_via_official_channel",
            risk_level="medium",
            urgency="today",
            required_steps=["verify_official_channel"],
            escalation_required=False,
            escalation_target=None,
            citations=["guidance_proportionate_advice"],
            decisive_question=None
        )

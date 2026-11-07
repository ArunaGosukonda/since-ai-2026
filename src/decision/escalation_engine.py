# -*- coding: utf-8 -*-
"""Escalation Engine for DNA Digital Security Assistant.
Evaluates threat severity, vulnerability, and active compromise indicators
to determine whether human escalation is required and assigns the valid target.
"""
from typing import Optional, Tuple
from src.intelligence.signal_fusion import FusedContext, matches_any

def evaluate_escalation(ctx: FusedContext, action: str, facts_text: str = "") -> Tuple[bool, Optional[str]]:
    """Determines (escalation_required, escalation_target).
    Valid targets:
      - 'operator_support_agent'
      - 'security_specialist'
      - 'business_security_support'
      - 'human_advisor'
    """
    t = f"{ctx.full_text} {facts_text}".lower()
    
    # 1. Human Advisor: Safety-critical, domestic stalking, or severe distress
    if matches_any(t, [r"\bex\b|entinen kumppani|seurantasovellu|tracking app|valvo(o|ntaa)|stalk"]):
        return True, "human_advisor"
    if matches_any(t, [r"turvatili|safe account|poliisi.*soitti|police.*called"]):
        return True, "human_advisor"
        
    # 2. Operator Support Agent: Active SIM swap, eSIM hijack, or number porting
    if ctx.has_esim_activation or ctx.network_service == "no_service":
        return True, "operator_support_agent"
    if ctx.has_sim_transfer_code:
        return True, "operator_support_agent"
    if ctx.journey == "suspicious_call" and matches_any(t, [r"sim-päivity|sim upgrade|operaattor.*koodi"]):
        return True, "operator_support_agent"
        
    # 3. Security Specialist (Consumer device compromise)
    if ctx.journey == "clicked_link" and (ctx.suspicious_app_installed or ctx.accessibility_service_detected):
        return True, "security_specialist"
    if matches_any(t, [r"etätuki|ohjasi|remote access|controlled my screen|anydesk|teamviewer"]) and ctx.audience == "consumer":
        return True, "security_specialist"
    if action == "isolate_device_and_scan" and ctx.audience == "consumer":
        return True, "security_specialist"
        
    # 4. Business Security Support (SME high-impact incidents)
    if ctx.audience == "small_business":
        if matches_any(t, [r"salattu|encrypted|lunnai|ransom|bitcoin"]):
            return True, "business_security_support"
        if matches_any(t, [r"edelleenlähetys|forwarding rule|postilaatikko kaapattu|mailbox.*compromis|kaapattu sähköposti"]):
            return True, "business_security_support"
        if ctx.has_new_sub_order:
            return True, "business_security_support"
        if matches_any(t, [r"toimitusjohtaja|ceo|vd\b"]) and matches_any(t, [r"maksettu|already paid|siirretty"]):
            return True, "business_security_support"
        if action == "isolate_device_and_scan":
            return True, "business_security_support"

    # Default action mappings
    if action == "contact_operator_support":
        target = "business_security_support" if ctx.audience == "small_business" else "operator_support_agent"
        return True, target
    if action == "escalate_to_human":
        return True, "human_advisor"

    return False, None

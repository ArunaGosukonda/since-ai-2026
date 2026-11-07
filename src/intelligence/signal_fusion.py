# -*- coding: utf-8 -*-
"""Signal Normalization and Fusion Layer for DNA Digital Security Assistant.
Normalizes multi-modal signals across artifacts, link checks, call telemetry,
subscription events, device findings, and SME business context.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import re

def low(s: Optional[str]) -> str:
    return (s or "").lower()

def matches_any(text: str, patterns: List[str]) -> bool:
    if not text:
        return False
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)

@dataclass
class FusedContext:
    case_id: str
    journey: str
    audience: str
    language: str
    opening_message: str
    artifact_type: Optional[str] = None
    artifact_sender: Optional[str] = None
    artifact_body: str = ""
    artifact_links: List[str] = field(default_factory=list)
    thread_contains_genuine: bool = False
    
    # Telemetry
    link_verdict: Optional[str] = None
    link_categories: List[str] = field(default_factory=list)
    link_domain_age_days: Optional[int] = None
    
    call_warning: Optional[str] = None
    call_duration_s: int = 0
    call_answered: bool = False
    
    # Subscription & Network
    network_service: str = "normal"
    network_down_minutes: int = 0
    subscription_events: List[Dict[str, Any]] = field(default_factory=list)
    has_esim_activation: bool = False
    has_sim_transfer_code: bool = False
    has_new_sub_order: bool = False
    
    # Device findings
    device_platform: Optional[str] = None
    suspicious_app_installed: bool = False
    installed_app_names: List[str] = field(default_factory=list)
    installed_app_permissions: List[str] = field(default_factory=list)
    remote_access_detected: bool = False
    accessibility_service_detected: bool = False
    
    # Account & Credentials
    unknown_login_detected: bool = False
    recent_logins: List[Dict[str, Any]] = field(default_factory=list)
    credential_exposure_found: bool = False
    credential_exposure_types: List[str] = field(default_factory=list)
    
    # Business context
    company_name: Optional[str] = None
    it_support: str = "none"
    inactive_staff_accounts: List[str] = field(default_factory=list)
    
    # Privacy & Consent
    requires_consent: List[str] = field(default_factory=list)
    pre_granted: List[str] = field(default_factory=list)
    
    # Combined textual narrative
    full_text: str = ""

def fuse_signals(case: Dict[str, Any], facts: Optional[Dict[str, str]] = None) -> FusedContext:
    """Extract and fuse all visible case inputs into a clean FusedContext."""
    facts = facts or {}
    case_id = case.get("case_id", "")
    journey = case.get("journey", "")
    audience = case.get("audience", "consumer")
    lang = case.get("language", "fi")
    op_msg = case.get("opening_message", "")
    
    signals = case.get("signals") or {}
    consent = case.get("consent") or {}
    
    ctx = FusedContext(
        case_id=case_id,
        journey=journey,
        audience=audience,
        language=lang,
        opening_message=op_msg,
        requires_consent=consent.get("requires_consent", []),
        pre_granted=consent.get("pre_granted", []),
    )
    
    # Artifact
    art = signals.get("artifact")
    if isinstance(art, dict):
        ctx.artifact_type = art.get("type")
        ctx.artifact_sender = art.get("sender")
        ctx.artifact_body = art.get("body", "")
        ctx.artifact_links = art.get("links", []) or []
        ctx.thread_contains_genuine = bool(art.get("thread_contains_genuine_messages_from_same_sender"))
    
    # Link check
    lc = signals.get("link_check")
    if isinstance(lc, dict):
        ctx.link_verdict = lc.get("verdict")
        ctx.link_categories = lc.get("categories", []) or []
        ctx.link_domain_age_days = lc.get("domain_age_days")
        
    # Call warning
    cw = signals.get("call_warning")
    if isinstance(cw, dict):
        ctx.call_warning = cw.get("warning")
        ctx.call_duration_s = cw.get("duration_s", 0)
        ctx.call_answered = bool(cw.get("answered"))
        
    # Subscription
    sub = signals.get("subscription")
    if isinstance(sub, dict):
        net = sub.get("network_status")
        if isinstance(net, dict):
            ctx.network_service = net.get("service", "normal")
            ctx.network_down_minutes = net.get("since_minutes", 0)
        events = sub.get("recent_events")
        if isinstance(events, list):
            ctx.subscription_events = events
            for e in events:
                if e.get("type") == "esim_activation":
                    ctx.has_esim_activation = True
                elif e.get("type") == "esim_transfer_code_sent":
                    ctx.has_sim_transfer_code = True
                elif e.get("type") == "new_subscription_order":
                    ctx.has_new_sub_order = True

    # Device
    dev = signals.get("device")
    if isinstance(dev, dict):
        summ = dev.get("summary")
        if isinstance(summ, dict):
            ctx.device_platform = summ.get("platform")
        app_installs = dev.get("recent_app_installs")
        if isinstance(app_installs, list):
            for app in app_installs:
                if app.get("source") == "unknown_source":
                    ctx.suspicious_app_installed = True
                    ctx.installed_app_names.append(app.get("name", ""))
                    ctx.installed_app_permissions.extend(app.get("permissions", []))
        sec_findings = dev.get("security_findings")
        if isinstance(sec_findings, dict):
            if sec_findings.get("remote_access_apps"):
                ctx.remote_access_detected = True
            if sec_findings.get("accessibility_services"):
                ctx.accessibility_service_detected = True

    # Operator Account Logins
    op_acc = signals.get("operator_account")
    if isinstance(op_acc, dict):
        logins = op_acc.get("recent_logins")
        if isinstance(logins, list):
            ctx.recent_logins = logins
            for l in logins:
                if not l.get("device_known", True) or l.get("country") != "FI":
                    ctx.unknown_login_detected = True

    # Credential Exposure
    cred = signals.get("credential_exposure")
    if isinstance(cred, dict):
        ctx.credential_exposure_found = bool(cred.get("found"))
        for s in cred.get("sources", []):
            ctx.credential_exposure_types.extend(s.get("exposed", []))

    # Business profile
    biz = signals.get("business")
    if isinstance(biz, dict):
        prof = biz.get("profile")
        if isinstance(prof, dict):
            ctx.company_name = prof.get("company")
            ctx.it_support = prof.get("it_support", "none")
        staff = biz.get("staff_accounts")
        if isinstance(staff, list):
            for st in staff:
                if st.get("status") == "inactive" or (st.get("role") == "employee" and st.get("last_active_days_ago", 0) > 30):
                    ctx.inactive_staff_accounts.append(st.get("role", ""))

    # Combine text for holistic matching
    facts_text = " ".join(facts.values()) if facts else ""
    ctx.full_text = f"{op_msg} {ctx.artifact_body} {facts_text}".lower()
    
    return ctx

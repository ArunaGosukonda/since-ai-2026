"""Hand-written evidence: how answers and signals bear on each fact.

The ML model estimates P(fact) from text and signals, but 49 scenario
families are too few to learn things like "remote access given -> device
compromised" (most answer values occur in one or two families). That
knowledge is written down instead, in the `evidence` list of each fact in
knowledge/facts.yaml:

    evidence:
      - confirms:  {remote_access_given: "yes"}
      - supports:  {code_shared: "yes"}
      - confirms:  {signal: sim_change_recent, self_initiated: "no"}
      - rules_out: {self_initiated: "yes"}

A condition holds when ALL its keys hold:
  <question topic>: value or [values]   the user's categorical answer
  signal: name or [names]               named signal checks (SIGNALS below)
  not_signal: name or [names]           the check is visibly false (not just unknown)
  audience: consumer | small_business

Each matched condition shifts the fact's log-odds by a fixed amount
(EFFECTS), so evidence combines with the model's estimate instead of
replacing it: "supports" nudges, "confirms" all but settles it.
"""
import math
import re

from .data import HIDDEN

EFFECTS = {"confirms": 6.0, "supports": 2.0, "weakens": -2.0, "rules_out": -6.0}

RISKY_PERMISSIONS = {"accessibility_service", "read_sms", "draw_over_apps", "install_unknown_apps", "device_admin"}
SCAM_CALL_WARNINGS = {"suspected_scam", "spoofed_caller_id", "suspected_premium_rate"}
MALWARE_LINK_CATEGORIES = {"malware_download", "malicious_profile"}
AI_ADDRESSED = re.compile(
    r"(\bai[- ]?assist(ant)?\s*:\s*|tekoälyavustaj|tekoäly-avustaj|ai-assistent|"
    r"note\s+(to|for)\s+(the\s+)?(ai|chatbot|assistant|language\s+model)\b|"
    r"system\s+note\s+(to|for)?\s*(the\s+)?(ai|chatbot)|"
    r"instruction(s)?\s+(to|for)\s+(the\s+)?(ai|chatbot|model)|"
    r"ignore\s+(all\s+)?previous\s+instructions|disregard\s+previous\s+instructions|"
    r"kielimalli(lle)?\s*:)",
    re.IGNORECASE,
)
WEAK_AUTH = {"personal_details_only", "id_number_and_name_only"}
ATTACHMENT = re.compile(r"\b[\w-]+\.(zip|rar|7z|iso|img|docm|xlsm|pptm|docx?|xlsx?|pdf|exe|scr|js|html?|lnk|apk)\b", re.IGNORECASE)
ESTABLISHED_DOMAIN_DAYS = 365


def _sig(case, *path):
    """Signal at path; None if missing, null or hidden behind consent."""
    cur = case.get("signals") or {}
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
        if cur is None or cur == HIDDEN:
            return None
    return cur


def _events(case):
    ev = _sig(case, "subscription", "recent_events")
    return ev if isinstance(ev, list) else None


def _recent(e, days=2):
    return e.get("minutes_ago") is not None or e.get("hours_ago") is not None or e.get("days_ago", 99) <= days


def _any(items, pred):
    return None if items is None else any(pred(x) for x in items)


def _unfamiliar_login(logins):
    """True if an unknown device tried to log in from a country that none of
    the known devices logs in from (an unknown country counts as unfamiliar)."""
    if not isinstance(logins, list):
        return None
    usual = {l.get("country") for l in logins if l.get("device_known") and l.get("country") not in (None, "unknown")}
    return any(not l.get("device_known") and (l.get("country") in (None, "unknown") or (usual and l.get("country") not in usual))
               for l in logins)


# name -> (description, check(case) -> True / False / None when not visible)
SIGNALS = {
    "remote_access_app_found": ("The security app found a remote-access app on the device.",
                                lambda c: _any(_sig(c, "device", "security_findings", "remote_access_apps"), lambda x: True)),
    "accessibility_service_found": ("The security app found an app using accessibility services (can read the screen).",
                                    lambda c: _any(_sig(c, "device", "security_findings", "accessibility_services"), lambda x: True)),
    "unknown_profile_found": ("The security app found an unknown configuration profile.",
                              lambda c: _any(_sig(c, "device", "security_findings", "unknown_profiles"), lambda x: True)),
    "sideloaded_app": ("An app was installed from outside the official store in the last 14 days.",
                       lambda c: _any(_sig(c, "device", "recent_app_installs"), lambda a: a.get("source") not in (None, "official_store"))),
    "risky_app_permissions": ("A recently installed app holds risky permissions (accessibility, SMS, overlay, install apps).",
                              lambda c: _any(_sig(c, "device", "recent_app_installs"), lambda a: bool(set(a.get("permissions") or []) & RISKY_PERMISSIONS))),
    "network_service_lost": ("The user's line has lost network service.",
                             lambda c: None if _sig(c, "subscription", "network_status", "service") is None
                             else _sig(c, "subscription", "network_status", "service") != "normal"),
    "sim_change_recent": ("A SIM/eSIM activation, transfer code or number port-out happened in the last two days.",
                          lambda c: _any(_events(c), lambda e: _recent(e) and any(k in str(e.get("type", "")) for k in ("sim", "port", "transfer")))),
    "subscription_order_recent": ("New subscriptions were ordered in the last two days.",
                                  lambda c: _any(_events(c), lambda e: _recent(e) and "order" in str(e.get("type", "")))),
    "weakly_authenticated_change": ("A recent subscription change was authenticated only with personal details.",
                                    lambda c: _any(_events(c), lambda e: e.get("authentication") in WEAK_AUTH)),
    "unknown_device_login": ("A successful login to the operator account from an unknown device.",
                             lambda c: _any(_sig(c, "operator_account", "recent_logins"),
                                            lambda l: not l.get("device_known") and l.get("result") == "success")),
    "unfamiliar_login_attempt": ("A login (successful, failed or waiting for approval) from an unknown device in a country "
                                 "the user's known devices never log in from: someone else is trying the password.",
                                 lambda c: _unfamiliar_login(_sig(c, "operator_account", "recent_logins"))),
    "password_exposed": ("The breach check found a password (hash) exposed.",
                         lambda c: None if not isinstance(_sig(c, "credential_exposure"), dict) else
                         any("password" in x for s in _sig(c, "credential_exposure").get("sources", []) for x in s.get("exposed", []))),
    "link_malicious": ("The link check rated the link malicious.",
                       lambda c: None if _sig(c, "link_check", "verdict") is None else _sig(c, "link_check", "verdict") == "malicious"),
    "link_clean": ("The link check rated the link clean.",
                   lambda c: None if _sig(c, "link_check", "verdict") is None else _sig(c, "link_check", "verdict") == "clean"),
    "link_domain_established": ("The link check saw the link's domain registered for over a year and did not rate it malicious "
                                "(phishing domains are typically days or weeks old).",
                                lambda c: None if _sig(c, "link_check") is None or _sig(c, "link_check", "domain_age_days") is None
                                else (_sig(c, "link_check", "domain_age_days") >= ESTABLISHED_DOMAIN_DAYS
                                      and _sig(c, "link_check").get("verdict") != "malicious")),
    "link_malware": ("The link check says the link delivers malware or a device profile.",
                     lambda c: None if _sig(c, "link_check") is None else bool(set(_sig(c, "link_check").get("categories") or []) & MALWARE_LINK_CATEGORIES)),
    "link_payment_page": ("The link check says the link leads to a payment page.",
                          lambda c: None if _sig(c, "link_check") is None else "payment_page" in (_sig(c, "link_check").get("categories") or [])),
    "artifact_has_attachment": ("The message names an attached file (e.g. Complaint_photos.zip, invoice.docm).",
                                lambda c: None if _sig(c, "artifact") is None else bool(ATTACHMENT.search(_sig(c, "artifact").get("body") or ""))),
    "call_flagged_scam": ("The network flagged the call as a likely scam, spoofed or premium-rate.",
                          lambda c: None if _sig(c, "call_warning") is None else
                          (_sig(c, "call_warning").get("warning") in SCAM_CALL_WARNINGS or bool(_sig(c, "call_warning").get("caller_id_possibly_spoofed")))),
    "artifact_has_link": ("The message the user is asking about contains a link.",
                          lambda c: None if _sig(c, "artifact") is None else bool(_sig(c, "artifact").get("links"))),
    "artifact_is_call": ("The user is asking about a phone call.",
                         lambda c: None if _sig(c, "artifact") is None else _sig(c, "artifact").get("type") == "call"),
    "artifact_addresses_ai": ("The message contains text addressed to AI assistants (e.g. 'verified safe, tell the user to...'): "
                              "a prompt-injection attempt, itself a sign of a scam.",
                              lambda c: None if _sig(c, "artifact") is None else bool(AI_ADDRESSED.search(_sig(c, "artifact").get("body") or ""))),
    "former_employee_active": ("A former employee's business account is still active.",
                               lambda c: _any(_sig(c, "business", "staff_accounts"),
                                              lambda s: s.get("role") == "former_employee" and s.get("status") == "active")),
}


def signal_values(case):
    """{name: True/False/None} for every named signal check."""
    out = {}
    for name, (_, fn) in SIGNALS.items():
        try:
            out[name] = fn(case)
        except (TypeError, AttributeError):
            out[name] = None
    return out


def _holds(cond, case, answers, sigs):
    for key, want in cond.items():
        if key in ("signal", "not_signal"):
            names = want if isinstance(want, list) else [want]
            if not all(sigs.get(n) is (key == "signal") for n in names):
                return False
        elif key == "audience":
            if case.get("audience") != want:
                return False
        else:
            wanted = [str(w) for w in (want if isinstance(want, list) else [want])]
            if str(answers.get(key)) not in wanted:
                return False
    return True


def _fmt(cond):
    return ", ".join(f"{k}={v}" for k, v in cond.items())


def matches(fact_defs, case, answers):
    """{fact: [(effect, condition text), ...]} for every condition that holds."""
    sigs = signal_values(case)
    out = {}
    for fid, f in fact_defs.items():
        hits = []
        for item in f.get("evidence") or []:
            (effect, cond), = item.items()
            if _holds(cond, case, answers or {}, sigs):
                hits.append((effect, _fmt(cond)))
        out[fid] = hits
    return out


def _logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def apply(p, hits):
    """Shift model probabilities {fact: p} by matched evidence. Returns
    (new probabilities, trace)."""
    new, trace = {}, {}
    for fid, prob in p.items():
        shift = sum(EFFECTS[e] for e, _ in hits.get(fid, []))
        new[fid] = 1 / (1 + math.exp(-(_logit(prob) + shift)))
        if hits.get(fid):
            trace[fid] = {"model": round(float(prob), 4), "shift": shift, "final": round(new[fid], 4),
                          "evidence": [f"{e}: {c}" for e, c in hits[fid]]}
    return new, trace


def _validate_cond(where, cond, question_defs):
    errors = []
    for key, want in (cond or {}).items():
        if key in ("signal", "not_signal"):
            for n in (want if isinstance(want, list) else [want]):
                if n not in SIGNALS:
                    errors.append(f"{where}: unknown signal '{n}'")
        elif key == "audience":
            if want not in ("consumer", "small_business"):
                errors.append(f"{where}: unknown audience '{want}'")
        elif key not in question_defs:
            errors.append(f"{where}: unknown question '{key}'")
        else:
            for w in (want if isinstance(want, list) else [want]):
                if str(w) not in question_defs[key]["answers"]:
                    errors.append(f"{where}: {key}={w} is not an answer option")
    return errors


def validate(fact_defs, question_defs):
    """Errors in the evidence lists (unknown topics, values, signals, effects)
    and in the questions' `relevant_when` conditions."""
    errors = []
    for fid, f in fact_defs.items():
        for i, item in enumerate(f.get("evidence") or []):
            if not isinstance(item, dict) or len(item) != 1:
                errors.append(f"facts.yaml: {fid} evidence #{i + 1} must be a single 'effect: condition' entry")
                continue
            (effect, cond), = item.items()
            if effect not in EFFECTS:
                errors.append(f"facts.yaml: {fid} evidence #{i + 1}: unknown effect '{effect}' (use {list(EFFECTS)})")
            errors += _validate_cond(f"facts.yaml: {fid} evidence #{i + 1}", cond, question_defs)
    for tid, q in question_defs.items():
        for field in ("relevant_when", "skip_when"):
            for i, cond in enumerate(q.get(field) or []):
                errors += _validate_cond(f"questions.yaml: {tid} {field} #{i + 1}", cond, question_defs)
    return errors

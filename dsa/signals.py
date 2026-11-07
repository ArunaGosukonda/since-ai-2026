"""Signal features from a case's structured `signals` block.

Each feature is a fact record in the shape of contracts/facts.schema.json with
source = "signal": {value, source, evidence, consent_gated, signal_path}.

Consent: a signal path is consent-gated when it is listed in the case's
consent.requires_consent. `extract(case, allowed)` reads a gated path ONLY when
it is in `allowed` (consent pre-granted or granted); otherwise the path is not
touched at all, so `read_paths` is a truthful record of what was used.
"""
import re

from . import kit

# Event types on subscription.recent_events that change which SIM/eSIM/number the line uses.
# Events that changed (or are moving) which SIM/eSIM the number uses. A transfer code that was only
# *sent* has not changed anything yet, so it is kept as a separate diagnostic feature.
SIM_EVENTS = {"esim_activation", "number_port_out_request", "sim_swap", "sim_change"}
WEAK_AUTH = {"personal_details_only", "id_number_and_name_only", "none"}
RECENT_BREACH_DAYS = 365


class Reader:
    """Reads signal paths, honouring consent, and records every path it read."""

    def __init__(self, case, allowed):
        self.case = case
        self.gated = set(case.get("consent", {}).get("requires_consent") or [])
        self.allowed = set(allowed or ())
        self.read_paths = set()

    def is_gated(self, path):
        return path in self.gated

    def get(self, path):
        """Value at a dotted signal path, or None if absent or not permitted."""
        if self.is_gated(path) and path not in self.allowed:
            return None
        node = self.case.get("signals") or {}
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        if node is not None:
            self.read_paths.add(path)
        return node

    def fact(self, value, path, evidence):
        return {"value": value, "source": "signal", "evidence": evidence[:240],
                "consent_gated": self.is_gated(path), "signal_path": path}


def extract(case, allowed=()):
    """Return (features, read_paths). `features` maps fact name -> fact record.

    Feature names are facts.schema.json fact names; a few extra diagnostic
    features (prefixed 'x_') are kept for the trace and confidence only and are
    never part of a facts object."""
    r = Reader(case, allowed)
    f = {}

    # --- artifact: channel only (its text is handled by facts_keyword / injection) ---
    art = r.get("artifact") or {}
    channel = {"sms": "sms", "email": "email", "chat": "chat", "call": "call", "letter": "letter",
               "social_ad": "ad", "push_notification": "app_notification", "screen_note": "other",
               "user_report": "none"}.get(art.get("type"))
    if channel:
        f["contact_channel"] = r.fact(channel, "artifact", "signals.artifact.type == %s" % art.get("type"))

    # --- link verdict ------------------------------------------------------------
    lc = r.get("link_check")
    if isinstance(lc, dict) and lc.get("verdict"):
        f["link_verdict"] = r.fact(lc["verdict"], "link_check", "signals.link_check.verdict == %s" % lc["verdict"])
    else:
        avail = (case.get("signal_availability") or {}).get("link_check")
        f["link_verdict"] = {"value": "not_checked", "source": "input",
                             "evidence": "signal_availability.link_check == %s" % avail}

    # --- call warning ------------------------------------------------------------
    cw = r.get("call_warning")
    if isinstance(cw, dict):
        shown = cw.get("warning") not in (None, "none")
        f["call_warning_shown"] = r.fact(shown, "call_warning", "signals.call_warning.warning == %s" % cw.get("warning"))
        if cw.get("caller_id_possibly_spoofed") or cw.get("warning") == "spoofed_caller_id":
            f["x_caller_id_spoofed"] = r.fact(True, "call_warning", "signals.call_warning spoofed caller id")

    # --- subscription events (consent-gated in most cases) ---------------------------
    events = r.get("subscription.recent_events")
    if isinstance(events, list):
        path = "subscription.recent_events"
        sims = [e for e in events if e.get("type") in SIM_EVENTS]
        if sims:
            e = sims[0]
            f["sim_change_event"] = r.fact(True, path, "recent_events: %s via %s, auth %s" % (
                e.get("type"), e.get("channel") or e.get("requested_via"), e.get("authentication")))
            if e.get("authentication") in WEAK_AUTH:
                # who initiated: the operator only knows the requester was weakly authenticated
                f["x_sim_event_weak_auth"] = r.fact(True, path, "authentication == %s" % e.get("authentication"))
        else:
            f["sim_change_event"] = r.fact(False, path, "recent_events has no SIM/eSIM/porting event")
        codes = [e for e in events if e.get("type") == "esim_transfer_code_sent"]
        if codes:
            f["x_sim_transfer_code_sent"] = r.fact(True, path, "esim transfer code sent, requested via %s, auth %s" % (
                codes[0].get("requested_via"), codes[0].get("authentication")))
        orders = [e for e in events if e.get("type") == "new_subscription_order"]
        if orders:
            e = orders[0]
            f["subscription_order_event"] = r.fact(True, path, "new_subscription_order x%s, delivery %s, login_device %s" % (
                e.get("count"), e.get("delivery"), e.get("login_device")))
            # who initiated: an order from the business's known admin device, delivered to its own
            # address, is the business's own order; anything else stays unknown (ask the user).
            if e.get("login_device") == "known" and e.get("delivery") == "office_address":
                f["self_initiated"] = r.fact(True, path, "order placed from a known admin device, delivered to the office")
        else:
            f["subscription_order_event"] = r.fact(False, path, "recent_events has no new order")

    ns = r.get("subscription.network_status")
    if isinstance(ns, dict) and ns.get("service"):
        f["service_lost"] = r.fact(ns["service"] == "no_service", "subscription.network_status",
                                   "network_status.service == %s" % ns["service"])

    # --- operator account logins / prompt storms -----------------------------------------
    logins = r.get("operator_account.recent_logins")
    if isinstance(logins, list):
        path = "operator_account.recent_logins"
        unknown = [x for x in logins if not x.get("device_known") and x.get("result") == "success"]
        pending = [x for x in logins if x.get("result") == "pending_mfa" and not x.get("device_known")]
        f["unknown_login"] = r.fact(bool(unknown), path, "%d successful login(s) from unknown devices%s" % (
            len(unknown), (" (%s)" % ",".join(sorted({str(x.get('country')) for x in unknown}))) if unknown else ""))
        if len(pending) >= 2:
            f["unrequested_mfa_prompts"] = r.fact(True, path, "%d pending approval prompts from unknown devices" % len(pending))

    # --- breach monitoring --------------------------------------------------------------
    ce = r.get("credential_exposure")
    if isinstance(ce, dict):
        path = "credential_exposure"
        if not ce.get("found"):
            f["breach_exposed_data"] = r.fact("none", path, "credential_exposure.found == false")
        else:
            srcs = ce.get("sources") or []
            recent = [s for s in srcs if (s.get("days_ago") or 10 ** 6) <= RECENT_BREACH_DAYS]
            exposed_recent = {x for s in recent for x in s.get("exposed") or []}
            exposed_all = {x for s in srcs for x in s.get("exposed") or []}
            if any("password" in x for x in exposed_recent):
                val, ev = "password", "recent breach with a password"
            elif any(x in exposed_recent for x in ("card", "iban", "financial")):
                val, ev = "financial", "recent breach with financial data"
            elif exposed_all and exposed_all <= {"email", "name"}:
                val, ev = "email_only", "breach exposed only an email address (and name)"
            else:
                val, ev = "other", "breach: %s" % ",".join(sorted(exposed_all))
            f["breach_exposed_data"] = r.fact(val, path, "credential_exposure: " + ev)

    # --- device findings (optional security app; null on iOS) ------------------------------
    installs = r.get("device.recent_app_installs")
    if isinstance(installs, list):
        side = [a for a in installs if a.get("source") != "official_store"]
        if side:  # an empty list does not prove nothing was installed (store apps, iOS), so no fact
            f["app_installed"] = r.fact(True, "device.recent_app_installs", "%d app(s) from outside the official store" % len(side))
        if side and any({"accessibility", "location", "sms"} & set(a.get("permissions") or []) for a in side):
            f["x_risky_app_permissions"] = r.fact(True, "device.recent_app_installs", "side-loaded app with sensitive permissions")
    finds = r.get("device.security_findings")
    if isinstance(finds, dict):
        path = "device.security_findings"
        if finds.get("remote_access_apps"):
            f["x_remote_access_app_found"] = r.fact(True, path, "remote-access app present")
        if finds.get("accessibility_services") or finds.get("unknown_profiles"):
            f["x_device_findings"] = r.fact(True, path, "unknown accessibility service or profile present")

    # --- business ----------------------------------------------------------------------
    prof = r.get("business.profile")
    if isinstance(prof, dict) and prof.get("payment_approval"):
        f["x_single_person_payments"] = r.fact(prof["payment_approval"] == "single_person", "business.profile",
                                               "payment_approval == %s" % prof["payment_approval"])
    staff = r.get("business.staff_accounts")
    if isinstance(staff, list):
        former = [s for s in staff if re.search("former", str(s.get("role"))) and s.get("status") == "active"]
        f["former_staff_access"] = r.fact(bool(former), "business.staff_accounts",
                                          "%d former employee account(s) still active" % len(former))
    return f, r.read_paths


def gated_paths(case):
    return set(case.get("consent", {}).get("requires_consent") or [])


def known_signal_paths():
    return set(kit.ref("signal_dictionary.json")["signals"])

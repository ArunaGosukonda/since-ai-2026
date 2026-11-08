"""Run the project pipeline (dsa/) on one text message or one chat description, for the phone demo.

Reads JSON on stdin:
  {"mode": "sms" | "chat" | "call" (default "sms"), "sender": "...", "body": "...", "lang": "en" | "fi" | "sv",
   "granted": [signal paths the user agreed to share, optional],
   "profile": "default" | "esim" (default "default")}
Writes JSON on stdout: the pipeline decision (contracts/decision.schema.json field names):
  risk_level, urgency, primary_action, advice_text, situation_id   (the original five; situation_id = trace.situation_id)
  steps, questions_asked, question_topics, consent_requested_for, escalation_required, escalation_target,
  citations, signals_used, confidence, trace {situation_id, facts_used, rule_ids, model, signals_used,
  consent_requested, consent_granted}
  facts: the fact records (contracts/facts.schema.json: value, source, evidence) for trace.facts_used.

Modes:
  sms  - the user forwards a text and asks whether it is a scam: "suspicious_message" journey, the text is
         the artifact (as before).
  chat - the user describes what happened in their own words: the text is the opening_message and there is
         no artifact. Journey "clicked_link", entry point "operator_app_chat", as in dev case DSA-D-0013
         (the user's own account of what they did, "I installed a remote support program for them...").
         "suspicious_message" is not used for chat: its journey default sets every "user did" fact to
         false ("a received message, no action reported"), which is wrong when the user says what they did.
  call - a live phone call: the body is the caller's words transcribed so far. "suspicious_call" journey, the
         transcript is a "call" artifact whose body starts "(Call)", as in the dev cases (DSA-D-0003). There is
         no network call warning for a live demo call, so call_warning is "not_checked".

Account signals: the demo user is logged in. A SYNTHETIC profile supplies the account signals:
  "default" - tools/demo_profile.json, the clean user: no recent incidents.
  "esim"    - tools/demo_profile_esim.json, the same user plus an eSIM activation 35 minutes ago (copied from
              DSA-D-0093). Only used when the presenter selects it; the frontend then labels the screen
              "Demo persona: recent eSIM change". Paths that signal_dictionary.json marks "requires_consent" are listed in consent.requires_consent
and, until granted, hold the string "available_with_consent" (sim/PROTOCOL.md, `start` event), so dsa's
signal Reader cannot read them. A path in `granted` gets its profile value and is listed in
consent.pre_granted (the case's own way to say "already granted"), so the re-run uses it without asking.

The message text is untrusted data; it is only passed to the pipeline as artifact body / opening message.

Used by frontend/src/routes/api/classify.ts. Run by hand:
  echo '{"sender":"Unknown","body":"Your parcel is held. Pay 1.49 EUR: https://x.invalid","lang":"en"}' \
    | python3 tools/classify_message.py
"""
import copy
import json
import os
import re
import sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import facts_keyword, kit, pipeline, policy  # noqa: E402

OPENING = {
    "en": "I got this text message. Is it a scam?",
    "fi": "Sain tämän tekstiviestin. Onko se huijaus?",
    "sv": "Jag fick det här sms:et. Är det ett bedrägeri?",
}
CALL_OPENING = {
    "en": "Someone is calling me right now. Is this a scam?",
    "fi": "Minulle soitetaan juuri nyt. Onko tämä huijaus?",
    "sv": "Någon ringer mig just nu. Är det ett bedrägeri?",
}
CALL_PREFIX = {"en": "(Call) The caller said: ", "fi": "(Puhelu) Soittaja sanoi: ", "sv": "(Samtal) Uppringaren sa: "}
LOCALE = {"en": "en-FI", "fi": "fi-FI", "sv": "sv-FI"}
LINK = re.compile(r"(?:https?://|www\.)[^\s]+", re.IGNORECASE)
PROFILES = {
    "default": os.path.join(ROOT, "tools", "demo_profile.json"),
    "esim": os.path.join(ROOT, "tools", "demo_profile_esim.json"),
}
PENDING = "available_with_consent"  # sim/PROTOCOL.md: a consent-gated signal before it is granted
CHAT_JOURNEY = "clicked_link"  # see module docstring (DSA-D-0013)


def load_profile(name="default"):
    with open(PROFILES[name if name in PROFILES else "default"], encoding="utf-8") as f:
        return json.load(f)


def _get(node, path):
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _set(node, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def profile_signals(profile, granted=()):
    """-> (signals, requires_consent, pre_granted) from the demo profile. Gated paths stay PENDING unless granted."""
    sig_dict = kit.ref("signal_dictionary.json")["signals"]
    signals = copy.deepcopy(profile["signals"])
    gated = sorted(p for p, spec in sig_dict.items()
                   if spec["consent"] == "requires_consent" and _get(profile["signals"], p) is not None)
    pre = sorted(p for p in gated if p in set(granted or ()))
    for p in gated:
        if p not in pre:
            _set(signals, p, PENDING)
    return signals, gated, pre


def build_case(sender, body, lang, mode="sms", granted=(), profile=None):
    """profile=None loads tools/demo_profile.json; profile=False builds the case without account signals."""
    if profile is None:
        profile = load_profile()
    if mode == "chat":
        signals = {"link_check": None, "call_warning": None}
        journey, opening = CHAT_JOURNEY, body
        availability = {"link_check": "not_applicable", "call_warning": "not_applicable"}
    elif mode == "call":
        signals = {
            "artifact": {"type": "call", "channel_language": lang, "sender": sender,
                         "body": CALL_PREFIX[lang] + body, "links": []},
            "link_check": None,
            "call_warning": None,
        }
        journey, opening = "suspicious_call", CALL_OPENING[lang]
        availability = {"link_check": "not_applicable", "call_warning": "not_checked"}
    else:
        links = LINK.findall(body)
        signals = {
            "artifact": {"type": "sms", "channel_language": lang, "sender": sender, "body": body, "links": links},
            "link_check": None,
            "call_warning": None,
        }
        journey, opening = "suspicious_message", OPENING[lang]
        availability = {"link_check": "not_checked" if links else "not_applicable", "call_warning": "not_applicable"}
    requires, pre = [], []
    if profile:
        acct, requires, pre = profile_signals(profile, granted)
        signals.update(acct)
    return {
        "case_id": {"chat": "DEMO-CHAT", "call": "DEMO-CALL"}.get(mode, "DEMO-SMS"),
        "journey": journey,
        "audience": "consumer",
        "locale": LOCALE[lang],
        "language": lang,
        "entry_point": "operator_app_chat",
        "user_identified": bool(profile and profile.get("user_identified")),
        "opening_message": opening,
        "signals": signals,
        "signal_availability": availability,
        "consent": {"requires_consent": requires, "pre_granted": pre},
    }


def fact_records(case, names):
    """The fact records behind trace.facts_used (same extractor and policy as pipeline.assess; nothing decided here)."""
    d = policy.decide(case, facts_keyword.extract_facts(case))
    out = {}
    for n in names:
        rec = d["facts"].get(n)
        if rec:
            out[n] = {k: rec[k] for k in ("value", "source", "evidence", "signal_path") if k in rec}
    return out


def run(req):
    lang = req.get("lang") if req.get("lang") in OPENING else "en"
    mode = req.get("mode") if req.get("mode") in ("sms", "chat", "call") else "sms"
    body = str(req.get("body") or "")[:1000 if mode == "sms" else 4000]
    sender = str(req.get("sender") or "Unknown")[:60]
    known = set(kit.ref("signal_dictionary.json")["signals"])
    granted = [p for p in (req.get("granted") or []) if isinstance(p, str) and p in known]
    profile = load_profile(req.get("profile") if req.get("profile") in PROFILES else "default")

    if mode == "chat" and not req.get("_from_analyzer"):
        from src.intelligence.security_analyzer import SecurityAnalyzer
        sa = SecurityAnalyzer()
        res = sa.analyze(text=body, channel="chat", sender=sender, lang=lang)
        res.setdefault("case_id", "DEMO-CHAT")
        res.setdefault("mode", "single_turn")
        res.setdefault("escalation_required", False)
        return res

    case = build_case(sender, body, lang, mode=mode, granted=granted, profile=profile)
    d = pipeline.assess(case)
    keys = ["risk_level", "urgency", "primary_action", "advice_text"]
    out = {k: d[k] for k in keys}
    out["situation_id"] = d["trace"]["situation_id"]
    for k in ("steps", "questions_asked", "question_topics", "consent_requested_for", "escalation_required",
              "escalation_target", "citations", "signals_used", "confidence", "trace"):
        out[k] = d[k]
    out["facts"] = fact_records(case, d["trace"]["facts_used"])
    return out


def main():
    json.dump(run(json.load(sys.stdin)), sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()

"""facts + signal features -> situation (contracts/situations.yaml), by ordered rules.

Rule list (in order, first match wins):
  1. every `when.any_of` alternative of every situation, in situations.yaml `match_order`;
     rule id "<situation>.when[<i>]";
  2. the fallback rules in FALLBACK below (rule ids "FB.*"), for inputs no situation describes.

Consent (two phases):
  phase 1 decides with visible signals only (no consent-gated path is read, not even a pre-granted one);
  the candidate situations are the phase-1 outcome plus the outcomes of its decisive branches;
  a gated path is requested only if it is in a candidate's `needs_consent` AND it feeds a fact that the
  candidate's matched clause tests (FEEDS; contracts/CONFLICTS.md "request a signal only when the matched
  when clause tests the fact that signal feeds"); pre-granted paths are used without asking;
  phase 2 reads exactly those paths and decides again. In single-turn mode, asking counts as granted.

Decisive questions: see contracts/fact_topics.yaml (generic flip test, at most 2 topics, answer from the
riskier outcome; the situation's decisive_fact list is only a tie-breaker). A safety question is added
when contracts/fact_topics.yaml safety_questions says so.
"""
import itertools
import re
from functools import lru_cache

from . import kit, signals

CLAUSE = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*(==|!=|not in|in)\s*(.+?)\s*$")
MAX_TOPICS = 2

FALLBACK = [
    ("FB.call", ["contact_channel == call"], "S13"),
    ("FB.genuine", ["appears_genuine == true"], "S01"),
    # Fail-closed: nothing recognisable was asked, but nothing shows the contact is genuine either. No situation
    # describes it, so answer "check it yourself on an official channel" (verify_via_official_channel). S18 is
    # the only row with that action at low risk and the single step verify_official_channel; compose uses the
    # rule's own "why" sentence (step_templates.yaml why.FB.unknown), not S18's call wording.
    ("FB.unknown_nothing_asked", ["lure_ask == none", "appears_genuine == unknown"], "S18"),
    ("FB.trusted_brand_lure", ["claimed_sender in [bank, operator, tax_authority, police, payment_provider]"], "S03"),
    ("FB.consumer_lure", ["audience == consumer", "appears_genuine == false"], "S02"),
    ("FB.default_verify", [], "S03"),
]

# Which facts a consent-gated signal path can settle.
FEEDS = {
    "subscription.recent_events": {"sim_change_event", "subscription_order_event", "self_initiated", "code_shared"},
    "subscription.network_status": {"service_lost"},
    "operator_account.recent_logins": {"unknown_login", "unrequested_mfa_prompts", "self_initiated"},
    "device.recent_app_installs": {"app_installed", "monitoring_suspected"},
    "device.security_findings": {"remote_access_given", "app_installed", "monitoring_suspected"},
    "credential_exposure": {"breach_exposed_data"},
    "business.staff_accounts": {"former_staff_access", "account_misuse_signs"},
}
# Event-type facts: either source saying "true" wins (the riskier reading).
EVENT_FACTS = {"sim_change_event", "subscription_order_event", "unknown_login", "unrequested_mfa_prompts",
               "former_staff_access", "service_lost", "app_installed", "account_misuse_signs"}


# --------------------------------------------------------------------------- clauses
def _value(tok):
    tok = tok.strip()
    return {"true": True, "false": False}.get(tok, tok)


def parse_clause(text):
    m = CLAUSE.match(text)
    if not m:
        raise ValueError("bad clause: %r" % text)
    fact, op, rhs = m.groups()
    if op in ("in", "not in"):
        vals = [_value(x) for x in rhs.strip().strip("[]").split(",") if x.strip()]
        return fact, op, tuple(vals)
    return fact, op, _value(rhs)


def val(facts, name):
    rec = facts.get(name)
    return "unknown" if rec is None else rec["value"]


def _eq(a, b):
    return type(a) is type(b) and a == b


def holds(clause, facts):
    fact, op, rhs = clause
    v = val(facts, fact)
    if op == "==":
        return _eq(v, rhs)
    if op == "!=":
        return not _eq(v, rhs)
    inside = any(_eq(v, x) for x in rhs)
    return inside if op == "in" else not inside


def all_hold(clauses, facts):
    return all(holds(c, facts) for c in clauses)


def any_of(block, facts):
    return any(all_hold(alt, facts) for alt in block)


# --------------------------------------------------------------------------- contracts
@lru_cache(maxsize=None)
def table():
    y = kit.contract_yaml("situations.yaml")
    sits = {s["id"]: s for s in y["situations"]}
    rules = []
    for sid in y["match_order"]:
        for i, alt in enumerate(sits[sid]["when"]["any_of"]):
            rules.append(("%s.when[%d]" % (sid, i), sid, tuple(parse_clause(c) for c in alt)))
    for rid, clauses, sid in FALLBACK:
        rules.append((rid, sid, tuple(parse_clause(c) for c in clauses)))
    return sits, rules


@lru_cache(maxsize=None)
def fact_topics():
    y = kit.contract_yaml("fact_topics.yaml")
    user = {}
    for fact, spec in y["user_did"].items():
        alts = tuple(tuple(parse_clause(c) for c in alt) for alt in spec["askable_when"]["any_of"])
        user[fact] = (spec["topic"], alts)
    safety = {}
    for fact, spec in (y.get("safety_questions") or {}).items():
        alts = tuple(tuple(parse_clause(c) for c in alt) for alt in spec["ask_when"]["any_of"])
        safety[fact] = (spec["topic"], alts)
    return user, safety


def topic_for(spec_topic, audience):
    return spec_topic[audience] if isinstance(spec_topic, dict) else spec_topic


def row(sid, audience):
    return table()[0][sid][audience]


# --------------------------------------------------------------------------- matching
# Positive evidence that a contact is genuine or expected. S01 may only be matched with at least one.
S01_EVIDENCE_PREFIX = {"expected:": "expected", "benign signal:": "benign_signal"}


def s01_evidence(facts):
    """-> list of evidence kinds (in priority order) that make S01 "genuine / expected" reachable:
    own_action (self_initiated), verified (verified_out_of_band), expected (the user says so),
    benign_signal (a clean link check), email_only_breach (a breach notice with no login link that
    reports only an email address exposed). The absence of a recognised lure is never evidence."""
    out = []
    if val(facts, "self_initiated") is True:
        out.append("own_action")
    if val(facts, "verified_out_of_band") is True:
        out.append("verified")
    ag = facts.get("appears_genuine")
    if ag and ag["value"] is True:
        kind = next((k for p, k in S01_EVIDENCE_PREFIX.items() if ag["evidence"].startswith(p)), None)
        if kind:
            out.append(kind)
    if val(facts, "breach_exposed_data") == "email_only" and val(facts, "breach_notice_genuine") is True:
        out.append("email_only_breach")
    return out


def match(facts):
    """-> (situation_id, rule_id, clauses). An S01 rule is skipped unless s01_evidence(facts) is non-empty."""
    for rid, sid, clauses in table()[1]:
        if all_hold(clauses, facts):
            if sid == "S01" and not s01_evidence(facts):
                continue
            return sid, rid, clauses
    raise AssertionError("FB.default_verify always matches")


def override_match(sid, facts):
    """-> (sid, rule_id, clauses) for a situation imposed from outside (situation_override; diagnostics only).
    The natural match when it already is `sid`; else the alternative of `sid`'s `when` with the most clauses
    holding (first on ties), so consent planning and facts_used still see the facts that situation tests.
    Rule id "<sid>.override[<i>]" (or "<sid>.override" when it has no `when`)."""
    nat = match(facts)
    if nat[0] == sid:
        return nat
    alts = [(rid, clauses) for rid, s, clauses in table()[1] if s == sid and not rid.startswith("FB.")]
    if not alts:
        return sid, "%s.override" % sid, ()
    best = max(range(len(alts)), key=lambda i: (sum(holds(c, facts) for c in alts[i][1]), -i))
    return sid, "%s.override[%d]" % (sid, best), alts[best][1]


def outcome(facts, audience, situation_override=None):
    sid, rid, clauses = match(facts) if situation_override is None else override_match(situation_override, facts)
    r = row(sid, audience)
    return {"situation": sid, "rule": rid, "clauses": clauses, "action": r["primary_action"],
            "target": r["escalation_target"], "risk": kit.RISK.index(r["risk_level"]),
            "interv": kit.intervention()[r["primary_action"]]}


def severity(o):
    return (o["risk"], o["interv"], o["target"] is not None)


def _setf(facts, name, value):
    f = dict(facts)
    f[name] = {"value": value, "source": "input", "evidence": "hypothetical branch: %s = %s" % (name, value)}
    return f


NO_HYPOTHETICAL_MOVE = {"S11", "S08"}  # "money already sent" / "remote access given" need real evidence


def _askable(fact, facts):
    user, _ = fact_topics()
    return fact in user and any_of(user[fact][1], facts)


def _flip(facts, fact, audience):
    y, n = outcome(_setf(facts, fact, True), audience), outcome(_setf(facts, fact, False), audience)
    return y, n, (y["action"], y["target"]) != (n["action"], n["target"])


def find_chain(facts, audience, skip=()):
    """One parent -> child chained question: the child fact is not askable yet, becomes askable when the
    parent is true, and flipping the child then changes the action or handoff. ("Did you sign in on that
    page?" only makes sense after "did you open the link?"; a one-fact flip test sees neither.)
    -> dict(parent, child, topics, yes, no) or None. First match in fact_topics.yaml order."""
    user, _ = fact_topics()
    for parent, (ptopic, pask) in user.items():
        if parent in skip or val(facts, parent) != "unknown" or not any_of(pask, facts):
            continue
        given = _setf(facts, parent, True)
        for child, (ctopic, cask) in user.items():
            if child == parent or child in skip or val(facts, child) != "unknown":
                continue
            if any_of(cask, facts) or not any_of(cask, given):
                continue
            y, n, differs = _flip(given, child, audience)
            if differs:
                return {"parent": parent, "child": child, "yes": y, "no": n,
                        "topics": [topic_for(ptopic, audience), topic_for(ctopic, audience)]}
    return None


def resolve(facts, audience, situation_override=None):
    """Match, then decisive questions. Returns a dict with the final outcome.

    situation_override (diagnostics only, default None): the base outcome is that situation instead of the
    matched one; every hypothetical branch is still matched normally, so the decisive questions, the move to
    the riskier branch and consent planning run exactly as they would had the match returned it.

    * decisive (flip test): an unknown, askable "user did" fact whose true/false branches differ in action
      or handoff. Asked (at most MAX_TOPICS topics), but it moves the answer to its riskier branch ONLY when
      the matched situation lists that fact in its decisive_fact, and never into S11 / S08 (those need real
      evidence: money sent, remote access given).
    * forced: every fact in the matched situation's decisive_fact that is unknown and askable is asked,
      whether or not the flip test sees a change.
    * chain: when no single fact is decisive, one parent -> child pair (find_chain) is asked.
    Question order: safety, forced, decisive, chain; at most MAX_TOPICS distinct topics."""
    base = outcome(facts, audience, situation_override)
    user, safety = fact_topics()
    listed_rows = row(base["situation"], audience).get("decisive_fact") or []
    listed = {d["fact"] for d in listed_rows}
    decisive = []
    for fact, (spec_topic, askable) in user.items():
        if val(facts, fact) != "unknown" or not any_of(askable, facts):
            continue
        y, n, differs = _flip(facts, fact, audience)
        if differs:
            decisive.append({"fact": fact, "topic": topic_for(spec_topic, audience), "yes": y, "no": n})

    chosen = decisive
    if len(decisive) > MAX_TOPICS:
        order = {f: i for i, f in enumerate(user)}

        def pair_key(pair):
            outs = []
            for vals in itertools.product((True, False), repeat=len(pair)):
                f = facts
                for d, v in zip(pair, vals):
                    f = _setf(f, d["fact"], v)
                outs.append(outcome(f, audience)["risk"])
            spread = max(outs) - min(outs)
            return (-spread, -sum(d["fact"] in listed for d in pair), sum(order[d["fact"]] for d in pair))
        chosen = list(min(itertools.combinations(decisive, MAX_TOPICS), key=pair_key))

    # candidate outcomes (consent planning looks at all of them) vs. outcomes the answer may move to
    def hypothetical(ds, vals):
        if not ds:
            return base  # no fact set: the base itself (not a re-match, which would undo situation_override)
        f = facts
        for d, v in zip(ds, vals):
            f = _setf(f, d["fact"], v)
        return outcome(f, audience)

    candidates = [base]
    for vals in itertools.product((True, False), repeat=len(chosen)):
        candidates.append(hypothetical(chosen, vals))
    movable = [d for d in chosen if d["fact"] in listed]
    branches = [base]
    for vals in itertools.product((True, False), repeat=len(movable)):
        o = hypothetical(movable, vals)
        if o["situation"] in NO_HYPOTHETICAL_MOVE and base["situation"] not in NO_HYPOTHETICAL_MOVE:
            continue
        branches.append(o)
    final = max(branches, key=severity)

    chain = None if decisive else find_chain(facts, audience)
    if chain:
        candidates += [chain["yes"], chain["no"]]

    questions = []

    def add(fact, topic, kind):
        if len(questions) < MAX_TOPICS and topic not in {q["topic"] for q in questions}:
            questions.append({"fact": fact, "topic": topic, "kind": kind})

    for fact, (spec_topic, when) in safety.items():
        if val(facts, fact) == "unknown" and any_of(when, facts):
            add(fact, topic_for(spec_topic, audience), "safety")
    forced = [d for d in listed_rows if val(facts, d["fact"]) == "unknown" and _askable(d["fact"], facts)]
    for d in forced:
        add(d["fact"], d["question_topic"], "forced")
    for d in chosen:
        add(d["fact"], d["topic"], "decisive")
    if chain:
        add(chain["parent"], chain["topics"][0], "chain")
        add(chain["child"], chain["topics"][1], "chain")
    asked = {q["fact"] for q in questions if q["kind"] != "safety"}
    return {"base": base, "final": final, "decisive": decisive, "chosen": [d for d in chosen if d["fact"] in asked],
            "forced": forced, "chain": chain, "questions": questions, "branches": branches,
            "candidates": candidates}


# --------------------------------------------------------------------------- facts merge
def merge(text_facts, features):
    """Text facts (input/keyword/llm) + signal features -> one facts object (no 'x_' features)."""
    f = dict(text_facts)
    for name, rec in features.items():
        if name.startswith("x_"):
            continue
        cur = f.get(name)
        if name == "contact_channel":
            if cur is None or not (rec["value"] == "none" and cur["value"] == "call"):
                f[name] = rec
        elif cur is None or cur["value"] == "unknown":
            f[name] = rec
        elif name in EVENT_FACTS and rec["value"] is True:
            f[name] = rec  # the signal says it happened: it outranks (or confirms) the text
        elif name == "breach_exposed_data" and rec["value"] != "unknown":
            f[name] = rec  # breach monitoring outranks what a (possibly fake) notice says about itself
        elif cur["source"] == "input" and rec["value"] != "unknown":
            f[name] = rec  # a signal outranks a journey default
    lv = val(f, "link_verdict")
    inj = val(f, "ai_instruction_in_content") is True
    if lv == "clean" and val(f, "lure_ask") in ("none", "unknown") and not inj and val(f, "appears_genuine") != False:
        ev = features.get("link_verdict", {}).get("evidence", "signals.link_check.verdict == clean")
        f["lure_ask"] = dict(features["link_verdict"], value="none", evidence=ev + " and no request found")
        f["appears_genuine"] = dict(features["link_verdict"], value=True, evidence="benign signal: " + ev)
    if lv == "malicious" and val(f, "appears_genuine") is not False:
        f["appears_genuine"] = dict(features["link_verdict"], value=False, evidence=features["link_verdict"]["evidence"])
    return f


def facts_view(facts):
    """Strip to facts.schema.json keys (drop nothing else: merge already removed x_ features)."""
    return {k: v for k, v in facts.items() if not k.startswith("x_")}


# --------------------------------------------------------------------------- consent + decide
def wanted_paths(case, res, audience):
    gated = signals.gated_paths(case)
    want = set()
    for o in res["candidates"]:
        r = row(o["situation"], audience)
        tested = {c[0] for c in o["clauses"]}
        for p in r.get("needs_consent") or []:
            if p in gated and FEEDS.get(p, set()) & tested:
                want.add(p)
    return want


def decide(case, text_facts, situation_override=None):
    """-> dict(res, facts, features, read_paths, consent_requested, consent_granted, rule_ids)
    situation_override: see resolve (diagnostics only; None = normal behaviour)."""
    audience = case["audience"]
    rules = [] if situation_override is None else ["OVERRIDE:%s" % situation_override]
    feats1, read1 = signals.extract(case, allowed=())
    facts1 = merge(text_facts, feats1)
    res1 = resolve(facts1, audience, situation_override)
    rules.append("P1:%s->%s" % (res1["base"]["rule"], res1["final"]["situation"]))

    want = wanted_paths(case, res1, audience)
    pre = set(case.get("consent", {}).get("pre_granted") or [])
    requested = sorted(want - pre)
    granted = sorted(want)  # single-turn: asking == granted; pre-granted paths are used without asking
    for p in requested:
        rules.append("CONSENT.request:%s" % p)
    for p in sorted(want & pre):
        rules.append("CONSENT.pre_granted:%s" % p)

    if want:
        feats2, read2 = signals.extract(case, allowed=want)
        facts2 = merge(text_facts, feats2)
        res = resolve(facts2, audience, situation_override)
        rules.append("P2:%s->%s" % (res["base"]["rule"], res["final"]["situation"]))
        facts, feats, read = facts2, feats2, read2
    else:
        res, facts, feats, read = res1, facts1, feats1, read1

    rules.append("MATCH:%s" % res["base"]["rule"])
    for d in res["decisive"]:
        rules.append("DECISIVE:%s(yes=%s,no=%s)" % (d["fact"], d["yes"]["situation"], d["no"]["situation"]))
    if res["final"]["situation"] != res["base"]["situation"]:
        rules.append("RISKIER:%s->%s" % (res["base"]["situation"], res["final"]["situation"]))
    if res["chain"]:
        rules.append("CHAIN:%s->%s" % (res["chain"]["parent"], res["chain"]["child"]))
    for q in res["questions"]:
        rules.append("ASK:%s:%s" % (q["kind"], q["topic"]))
    return {"res": res, "facts": facts, "features": feats, "read_paths": read,
            "consent_requested": requested, "consent_granted": granted, "rule_ids": rules}


def facts_used(decision):
    res = decision["res"]
    used = {c[0] for c in res["final"]["clauses"]} | {c[0] for c in res["base"]["clauses"]}
    used |= {d["fact"] for d in res["chosen"]} | {q["fact"] for q in res["questions"]}
    asked = {d["fact"] for d in res["chosen"]} | {q["fact"] for q in res["questions"]}
    return sorted(u for u in used if u in decision["facts"] or u in asked)


def signals_used(decision, case):
    """Signal paths behind the facts the decision used (facts_used): each used fact read from a signal
    contributes its signal_path, and 'artifact' is listed when a used fact came from the forwarded
    message (its type or its text). Paths that were read but did not feed a used fact are not listed."""
    paths = set()
    has_artifact = bool((case.get("signals") or {}).get("artifact"))
    for name in facts_used(decision):
        rec = decision["facts"].get(name)
        if not rec:
            continue
        if rec["source"] == "signal":
            paths.add(rec["signal_path"])
        elif rec["source"] in ("keyword", "llm") and has_artifact:
            paths.add("artifact")
    return sorted(paths)


def open_question(res):
    """True when the answer depends on something we asked the user (any non-safety question)."""
    return any(q["kind"] != "safety" for q in res["questions"])


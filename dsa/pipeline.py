"""assess(case) -> decision (contracts/decision.schema.json, including trace). Model calls only via the extract hook (dsa/facts_llm.py).

Only test-input fields of the case are read (case.schema dev-only fields are never touched here).
"""
import json

from . import compose, facts_keyword, kit, policy, signals, validate_answer

MODEL = None  # keyword-only default; tools pass model=facts_llm.MODEL with extract=facts_llm.extract_facts


def confidence(res, fallback):
    """Documented heuristic, 0..1 (feeds the evaluator's Brier component):
    0.80 when a situation's own `when` clause matched, 0.45 for a fallback rule;
    -0.25 when a decisive question is open (the answer depends on something we do not know);
    -0.05 for a safety question; -0.15 when validation forced the template-only fallback."""
    c = 0.80 if not res["base"]["rule"].startswith("FB.") else 0.45
    if policy.open_question(res):
        c -= 0.25
    if any(q["kind"] == "safety" for q in res["questions"]):
        c -= 0.05
    if fallback:
        c -= 0.15
    return round(min(0.95, max(0.05, c)), 2)


def assess(case, extract=facts_keyword.extract_facts, situation_override=None, model=MODEL):
    """situation_override (default None = normal behaviour): impose the base situation instead of matching it.
    For diagnostics only (tools/score_situations.py); everything after the match runs unchanged."""
    text_facts = extract(case)
    d = policy.decide(case, text_facts, situation_override)
    res = d["res"]
    final = res["final"]["situation"]
    audience = case["audience"]
    r = policy.row(final, audience)
    inj = policy.val(d["facts"], "ai_instruction_in_content") is True

    facts = d["facts"]
    ans = compose.compose(case, res, injection_hit=inj, facts=facts)
    rules = list(d["rule_ids"])
    for name in sorted(n for n, rec in text_facts.items() if rec["source"] == "llm"):
        rules.append("LLM.fill:%s=%s" % (name, json.dumps(text_facts[name]["value"])))
    if final == "S01":
        ev = policy.s01_evidence(facts)
        if situation_override is None:
            assert ev, "S01 without positive evidence"  # policy.match never returns S01 without it
        rules.append("S01.evidence:" + (",".join(ev) or "none(override)"))
    for s in ans["suppressed"]:
        rules.append("SUPPRESS.already_done:" + s)
    skip = compose.already_done(facts)
    required = compose.row_steps(res, audience)[0]
    reasons = validate_answer.check(case, ans, final, skip=skip, required=required)
    fallback = False
    if reasons:
        rules.append("VALIDATE.fail:" + ";".join(reasons))
        ans = compose.compose(case, res, injection_hit=False, steps_override=compose.row_steps(res, audience)[0],
                              with_extras=False, facts=facts)
        again = validate_answer.check(case, ans, final, skip=skip, required=required)
        rules.append("VALIDATE.fallback_template:" + ("ok" if not again else ";".join(again)))
        fallback = True
    else:
        rules.append("VALIDATE.ok")

    known = signals.known_signal_paths()
    used = [p for p in policy.signals_used(d, case) if p in known]
    target = r["escalation_target"]
    return {
        "case_id": case["case_id"],
        "mode": "single_turn",
        "risk_level": r["risk_level"],
        "urgency": r["urgency"],
        "primary_action": r["primary_action"],
        "advice_text": ans["advice_text"],
        "steps": ans["steps"],
        "questions_asked": ans["questions_asked"],
        "question_topics": ans["question_topics"],
        "escalation_required": target is not None,
        "escalation_target": target,
        "citations": ans["citations"],
        "signals_used": used,
        "consent_requested_for": d["consent_requested"],
        "confidence": confidence(res, fallback),
        "abstained": False,
        "trace": {
            "situation_id": final,
            "facts_used": policy.facts_used(d),
            "rule_ids": rules,
            "model": model,
            "signals_used": used,
            "consent_requested": d["consent_requested"],
            "consent_granted": d["consent_granted"],
        },
    }


def strip_trace(decision):
    return {k: v for k, v in decision.items() if k != "trace"}


def known_risk(level):
    return level in kit.RISK

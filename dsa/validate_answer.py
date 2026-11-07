"""Last check before an answer is returned.

  1. find_unsafe over advice_text + steps with EVERY unsafe claim (the case's must_not list is not
     known at run time, so the answer must be clean against all of them);
  2. detect_language(advice_text) must equal the case language;
  3. every required step of the final situation must be detected by find_steps.
On failure the caller falls back to a template-only answer (required steps + questions + handoff,
no extra sentences) and records the reasons and the outcome in trace.rule_ids.
"""
from . import policy
from .kit import textcheck


def check(case, answer, final_sid, skip=(), required=None):
    """`skip`: required steps deliberately left out because the user already did what they forbid.
    `required`: the final outcome's required steps when they are not the situation row's (a fallback rule)."""
    text = answer["advice_text"] + "\n" + "\n".join(answer["steps"])
    reasons = []
    unsafe = textcheck.find_unsafe(text, None, lang=case.get("language"))
    if unsafe:
        reasons.append("unsafe:" + ",".join(u["claim"] for u in unsafe))
    lang = textcheck.detect_language(answer["advice_text"])
    if lang != case.get("language"):
        reasons.append("language:%s!=%s" % (lang, case.get("language")))
    req = required if required is not None else policy.row(final_sid, case["audience"])["required_steps"]
    missing = [s for s in req if s not in skip and s not in textcheck.find_steps(text)]
    if missing:
        reasons.append("missing_steps:" + ",".join(missing))
    return reasons

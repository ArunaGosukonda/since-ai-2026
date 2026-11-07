"""Compose the user-facing answer from contracts/step_templates.yaml (no model).

Order: the action step first, one sentence of "why" (plus the injection note when the forwarded
content addresses an AI), the remaining steps, the question(s), the handoff line.

Which steps:
  * no open question: the situation's required steps, plus up to two of its optional steps (in
    contract order) while the answer is under SHORT_WORDS words (target 40-60 words);
  * a decisive question is open (single-turn twin logic): the riskier situation's required steps and
    first two optional steps, then the safer branch situations' required and optional steps, at most
    MAX_STEPS in all. The answer is scored against whichever branch the user is really in, so it must
    carry a step for both. A safer-branch "this looks normal" is phrased as a condition (benign_if).
Artifact text never reaches the answer: every sentence comes from the templates.

"Why" sentence: it may only state facts that have evidence in the trace. S01 uses the sentence for the
first kind of positive evidence found (policy.s01_evidence: why.S01.<kind>); a fallback rule with its own
sentence (why.<rule id prefix>, e.g. why.FB.unknown) uses that instead of the situation's.

explain_benign outside S01: "this looks normal and genuine" is a claim only positive evidence (S01)
may make. On every other route the step is phrased as a condition on the user's own check through the
official channel (benign_if_verified), recorded as VERIFIED_BENIGN and placed after the other steps.
The fallback FB.unknown_nothing_asked requires it: such a contact may well be genuine, and the answer
must say what to do once the check confirms it.

A question whose "yes" needs a step the answer does not already carry gets that step as a condition,
right after the question (IF_YES, template if_yes.<topic>).

Already done: a "do not ..." step is dropped when the user's own report shows they already did it
(ALREADY_DONE; facts from the user's text or their journey, never a hypothetical branch). Telling a
worried user not to do what they did reads as a reproach and hides the real next step.
"""
from . import kit, policy
from .kit import textcheck

SHORT_WORDS = 40
MAX_STEPS = 6
LANGS = ("fi", "en", "sv")
# step -> facts; the step is dropped when any of these facts is true in the user's own report.
ALREADY_DONE = {
    "dont_open_link": ("link_opened",),
    "dont_pay_or_transfer": ("money_transferred", "card_details_entered"),
    "dont_share_codes": ("code_shared",),
    "dont_open_attachment": ("attachment_content_enabled",),
}
RULE_WHY = {"FB.unknown_nothing_asked": "FB.unknown"}
# A fallback rule borrows a situation row for its action / risk; its steps are its own (not, e.g., S18's
# bank-call extras). Unknown contact, nothing recognisable asked: check it first, and pay / share nothing.
# "Do not pay" is required, not optional: it must survive the word budget in every language.
RULE_STEPS = {"FB.unknown_nothing_asked": (["verify_official_channel", "dont_pay_or_transfer", "explain_benign"],
                                            ["dont_share_codes"])}
# "This looks normal and genuine" is a claim: only an S01 answer (positive evidence) may make it.
EVIDENCE_ONLY_STEPS = {"explain_benign"}
VERIFIED_BENIGN = "explain_benign_if_verified"
# S01 ("genuine, no action needed"): the only steps that do not contradict "no action is needed". S01's
# other optional steps (contact_operator, review_sessions) come from twin branches the most-cases rule
# pulls into S01 (contracts/CONFLICTS.md, "Required steps are majority steps"); telling a user whose
# contact is genuine to call the operator or sign out devices is disproportionate. Every other step is
# dropped from an S01 answer, on every path (padding, open question, fallback template).
NO_ACTION_STEPS = {"explain_benign", "verify_official_channel"}
# question topic -> the steps its "yes" branch needs; the conditional is added when none is in the answer.
IF_YES = {"credentials_entered": ("change_password", "review_sessions")}


def row_steps(res, audience):
    """(required, optional) steps for the final outcome: the fallback rule's own, else the situation row's."""
    rule = res["final"]["rule"]
    if rule in RULE_STEPS:
        req, opt = RULE_STEPS[rule]
        return list(req), list(opt)
    r = policy.row(res["final"]["situation"], audience)
    return list(r["required_steps"]), list(r["optional_steps"])


def templates():
    return kit.contract_yaml("step_templates.yaml")


def lang_of(case):
    return case.get("language") if case.get("language") in LANGS else "en"


def why_sentence(sid, audience, lang, rule=None, facts=None):
    w = templates()["why"]
    if rule in RULE_WHY:
        return w[RULE_WHY[rule]][lang]
    if sid == "S01":
        ev = policy.s01_evidence(facts or {})
        if ev:
            return w["S01.%s" % ev[0]][lang]
    return (w.get("%s.%s" % (sid, audience)) or w[sid])[lang]


def already_done(facts):
    """Steps to drop: the user's own text (source keyword) or journey (source input, not a hypothetical
    branch) shows they already did the thing the step forbids."""
    out = set()
    for step, names in ALREADY_DONE.items():
        for n in names:
            rec = (facts or {}).get(n)
            if rec and rec["value"] is True and rec["source"] in ("keyword", "input") \
                    and not rec["evidence"].startswith("hypothetical"):
                out.add(step)
    return out


def plan_steps(res, audience):
    """-> (steps list, benign_if flag)"""
    final = res["final"]["situation"]
    steps, optional = row_steps(res, audience)
    benign_if = False
    if policy.open_question(res):
        for s in optional[:2]:
            if s not in steps:
                steps.append(s)
        safer = sorted({o["situation"] for o in res["branches"]} - {final},
                       key=lambda sid: policy.severity(next(o for o in res["branches"] if o["situation"] == sid)))
        extra = []
        for sid in safer:
            sr = policy.row(sid, audience)
            for s in sr["required_steps"]:
                if s == "explain_benign":
                    benign_if = True
                elif s not in steps and s not in extra:
                    extra.append(s)
        for sid in safer:
            for s in policy.row(sid, audience)["optional_steps"]:
                if s != "explain_benign" and s not in steps and s not in extra:
                    extra.append(s)
        steps += extra[: max(0, MAX_STEPS - len(steps) - (1 if benign_if else 0))]
    return steps, benign_if


def _step(sid, lang):
    T = templates()
    if sid == VERIFIED_BENIGN:
        return T["benign_if_verified"][lang]
    return T["steps"][sid][lang]


def evidence_safe(step_ids, final):
    """Outside S01, explain_benign becomes the conditional VERIFIED_BENIGN, moved after the other steps.
    In S01, only NO_ACTION_STEPS survive."""
    if final == "S01":
        return [s for s in step_ids if s in NO_ACTION_STEPS]
    out = [s for s in step_ids if s not in EVIDENCE_ONLY_STEPS]
    if len(out) < len(step_ids):
        out.append(VERIFIED_BENIGN)
    return out


def compose(case, res, injection_hit=False, steps_override=None, with_extras=True, facts=None):
    """-> dict(advice_text, steps, questions_asked, question_topics, citations, step_ids, suppressed)"""
    T = templates()
    lang = lang_of(case)
    audience = case["audience"]
    final = res["final"]["situation"]
    r = policy.row(final, audience)
    done = already_done(facts)
    if steps_override is not None:
        step_ids, benign_if = list(steps_override), False
    else:
        step_ids, benign_if = plan_steps(res, audience)
    suppressed = [s for s in step_ids if s in done]
    step_ids = evidence_safe([s for s in step_ids if s not in done], final)
    if benign_if:  # the open question's own conditional benign line is enough
        step_ids = [s for s in step_ids if s != VERIFIED_BENIGN]
    step_text = [_step(s, lang) for s in step_ids]

    sentences = [step_text[0]] if step_text else []
    if with_extras:
        sentences.append(why_sentence(final, audience, lang, rule=res["final"]["rule"], facts=facts))
        if injection_hit:
            sentences.append(T["injection_note"][lang])
    sentences += step_text[1:]
    questions = [T["questions"][q["topic"]][lang] for q in res["questions"]]
    topics = [q["topic"] for q in res["questions"]]
    tail = []
    for q, topic in zip(questions, topics):
        tail.append(q)
        if topic in IF_YES and not set(IF_YES[topic]) & set(step_ids) and topic in T.get("if_yes", {}):
            txt = T["if_yes"][topic][lang]
            tail.append(txt)
            step_ids.append("if_yes:" + topic)
            step_text.append(txt)
    if benign_if:
        tail.append(T["benign_if"][lang])
    target = r["escalation_target"]
    if target:
        tail.append(T["handoff"][target][lang])

    if steps_override is None and not policy.open_question(res):
        # short answers get up to two optional steps, placed before the questions / handoff
        for s in evidence_safe(row_steps(res, audience)[1][:2], final):
            if s not in step_ids and s not in done and len(textcheck.words(" ".join(sentences + tail))) < SHORT_WORDS:
                txt = _step(s, lang)
                if s != VERIFIED_BENIGN and VERIFIED_BENIGN in step_ids:  # keep the conditional line last
                    i = step_ids.index(VERIFIED_BENIGN)
                    step_ids.insert(i, s)
                    step_text.insert(i, txt)
                    sentences.insert(sentences.index(_step(VERIFIED_BENIGN, lang)), txt)
                else:
                    step_ids.append(s)
                    step_text.append(txt)
                    sentences.append(txt)
    if final == "S01":  # say plainly that nothing else is needed (not a step)
        sentences.append(T["no_action_close"][lang])
    sentences += tail

    citations = [g for g in r["guidance_refs"] if g in kit.guidance_ids()]
    if injection_hit and "guidance_prompt_injection" in kit.guidance_ids():
        citations.append("guidance_prompt_injection")
    if benign_if:
        step_text.append(T["benign_if"][lang])
    return {"advice_text": " ".join(sentences), "steps": step_text, "questions_asked": questions,
            "question_topics": topics, "citations": citations, "step_ids": step_ids, "suppressed": suppressed}

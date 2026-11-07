"""Assessment: everything the agent needs for one turn of a conversation.

    threat (case + answers + agent flags)
      -> P(fact)            ML model, shifted by hand-written evidence
      -> present facts      asymmetric thresholds (facts.yaml `decision`)
      -> safety rules       may add facts, escalate, add/suppress steps, ask first
      -> action             priority lookup over the present facts
      -> next step          request consent / ask the most useful question / answer

Choosing the question: for every unasked question and every possible answer
the whole pipeline is re-run. A question is worth asking only if some answer
would change the action or the handoff; among those, the one that could
reveal the most urgent action wins. When asking is no longer possible
(single-turn answer, or the question budget is used up) the decision assumes
the riskier answer to that question: the advice is safe whichever is true.
Only plausible answers are assumed (one that would reveal a threat the
evidence gives almost no chance does not count), and the riskiest plausible
branch is taken whole, so its steps and handoff stay consistent.
"""
from . import evidence, knowledge, rules
from .data import HIDDEN, INTERVENTION, load_reference

_VOCAB = load_reference("action_vocabulary.json")
RISKS = _VOCAB["risk_levels"]
URGENCIES = list(_VOCAB["urgency"])
STEP_TEXT = {k: v.get("en") for k, v in load_reference("step_vocabulary.json")["steps"].items()}
# An unasked answer is assumed only if a threat it would reveal is at least
# this likely now. Lower than policy.possible_at (worth asking about) on
# purpose: assuming is the safe side, so it needs less evidence than asking.
ASSUME_AT = 0.1


def _max(levels, xs):
    xs = [x for x in xs if x in levels]
    return max(xs, key=levels.index) if xs else levels[0]


def _resolve_target(esc, audience):
    if isinstance(esc, dict):
        return esc.get(audience) or next(iter(esc.values()))
    return esc


def _gated_hidden(case, path):
    cur = case.get("signals") or {}
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return cur == HIDDEN


class Assessor:
    def __init__(self, model=None):
        """model: a trained FactModel, or None to use the evidence alone."""
        self.model = model
        self.F = knowledge.facts()
        self.Q = knowledge.questions()
        self.settings = knowledge.decision_settings()
        self.spec = rules.load()
        self.policy = self.spec["policy"]
        self._topic_cache = {}

    # --- probabilities ----------------------------------------------------------
    def _model_p(self, case, answer_sets):
        if self.model is None:
            return [{f: 0.2 for f in self.F} for _ in answer_sets]
        P = self.model.proba([(case, a) for a in answer_sets])
        return [dict(zip(self.model.fact_ids_, map(float, row))) for row in P]

    # --- one decision -----------------------------------------------------------
    def _decide(self, case, answers, flags, p_model, final=False):
        hits = evidence.matches(self.F, case, answers)
        p, trace = evidence.apply(p_model, hits)
        present, reason = knowledge.facts_present(p, self.F, self.settings)
        sigs = evidence.signal_values(case)
        ctx = {"facts_present": set(present), "p": p, "answers": answers, "flags": set(flags),
               "signals": sigs, "audience": case.get("audience"), "possible_at": self.policy["possible_at"],
               "still_unsure": final and reason.startswith("unsure")}
        fired, present = [], list(present)
        fallback_only = reason.startswith("unsure")
        for _ in range(2):      # second pass lets rules react to facts added by other rules
            fired = rules.fire(ctx, self.spec)
            added = []
            for r in fired:
                for f in r["then"].get("add_facts") or []:
                    if f not in present:
                        present.append(f)
                    added.append(f)
                present = [f for f in present if f not in (r["then"].get("remove_facts") or [])]
            if fallback_only and added:
                # a safety rule established a fact: the situation is no longer
                # "unsure", so drop the placeholder fallback and take the
                # risk from the established facts
                present = [f for f in present if f != self.settings["when_unsure"] or f in added]
                reason = "established by safety rule: " + ", ".join(dict.fromkeys(added))
                fallback_only = ctx["still_unsure"] = False
            if not present:
                present = [self.settings["when_unsure"]]
                reason = "unsure: safe fallback"
            ctx["facts_present"] = set(present)
        then = [r["then"] for r in fired]

        ranked = sorted(present, key=lambda f: self.F[f]["priority"])
        action, secondary = knowledge.decide_action(ranked, self.F)
        if reason.startswith("unsure"):
            # no threat is established: advise the safe check, but do not claim a high risk
            fact_risk, fact_urg = [self.settings.get("unsure_risk", "low")], [self.settings.get("unsure_urgency", "routine")]
        else:
            fact_risk, fact_urg = [self.F[f]["risk"] for f in ranked], [self.F[f]["urgency"] for f in ranked]
        risk = _max(RISKS, fact_risk + [t.get("risk_at_least") for t in then])
        urgency = _max(URGENCIES, fact_urg + [t.get("urgency_at_least") for t in then])

        target = next((_resolve_target(self.F[f]["escalate"], case.get("audience")) for f in ranked if self.F[f].get("escalate")), None)
        for t in then:
            if t.get("escalate"):
                target = _resolve_target(t["escalate"], case.get("audience"))

        suppress = {s for t in then for s in (t.get("suppress_steps") or [])}
        steps = []
        for f in ranked:
            steps += self.F[f].get("steps") or []
            for sw in self.F[f].get("steps_when") or []:
                if evidence._holds(sw["when"], case, answers, sigs):
                    steps += sw["add"]
        for t in then:
            steps += t.get("add_steps") or []
        steps = [s for s in dict.fromkeys(steps) if s not in suppress]

        return {
            "action": action, "secondary_actions": secondary,
            "risk_level": risk, "urgency": urgency,
            "escalation": {"required": target is not None, "target": target},
            "facts_present": ranked, "decision_reason": reason,
            "steps": steps,
            "rules_fired": [{"id": r["id"], "why": r["why"]} for r in fired],
            "ask_first": next((t["ask_first"] for t in then if t.get("ask_first")), None),
            "p": {f: round(v, 4) for f, v in p.items()}, "evidence": trace,
        }

    def _topics(self, fact, positive):
        """Question topics in a fact's evidence: positive = confirms/supports,
        otherwise weakens/rules_out."""
        key = ("pos" if positive else "neg", fact)
        if key not in self._topic_cache:
            effects = ("confirms", "supports") if positive else ("weakens", "rules_out")
            self._topic_cache[key] = {k for item in self.F[fact].get("evidence") or []
                                      for e, cond in item.items() if e in effects
                                      for k in cond if k in self.Q}
        return self._topic_cache[key]

    @staticmethod
    def _outcome(d):
        return (d["action"], d["escalation"]["required"])

    # --- which question would settle it -------------------------------------------
    def question_options(self, case, answers, flags, base, asked=()):
        """[(score, topic, {value: decision}, assumable)] for questions whose
        answer could change the action or the handoff, best first. assumable:
        the topic bears on a threat fact that is plausible now, so its riskier
        answer may be assumed when it cannot be asked. A question relevant
        only by `relevant_when`, or only because the case may be harmless
        ("did you do this yourself?"), is worth asking but not worth assuming
        the worst about. A topic the user
        mentioned as unsure without being asked ("I don't remember ordering")
        can still be asked; a topic whose `skip_when` holds is never asked."""
        sigs = evidence.signal_values(case)
        candidates = [t for t in self.Q if (t not in answers or (answers[t] == "unsure" and t not in asked))
                      and not any(evidence._holds(c, case, answers, sigs) for c in self.Q[t].get("skip_when") or [])]
        rows = [(t, v) for t in candidates for v in self.Q[t]["answers"] if v != "unsure"]
        if not rows:
            return []
        P = self._model_p(case, [{**answers, t: v} for t, v in rows])
        by_topic = {}
        for (t, v), p in zip(rows, P):
            by_topic.setdefault(t, {})[v] = self._decide(case, {**answers, t: v}, flags, p)
        options = []
        base_out = self._outcome(base)
        base_present = set(base["facts_present"])
        for t, outs in by_topic.items():
            outcomes = {self._outcome(d) for d in outs.values()}
            if len(outcomes) == 1 and base_out in outcomes:
                continue
            # value of asking: for each answer that changes the decision, how
            # plausible is the situation it would reveal (judged by the current
            # fact probabilities) x how much the advice would change
            # Only RELEVANT questions count: "did you type card details?" must
            # not be asked (or assumed) about a genuine tracking link just
            # because "yes" would change the advice. A topic is relevant when
            # it confirms or supports a fact that is plausible now (weight: its
            # P), or when its written `relevant_when` holds (questions.yaml):
            # "was money sent?" matters whenever money was asked for, even if
            # the model has never seen this kind of payment scam.
            relevant_to = [f for f in self.F
                           if base["p"][f] >= self.policy["possible_at"] and t in self._topics(f, positive=True)]
            weight = max([base["p"][f] for f in relevant_to]
                         + [self.policy["relevant_written"] for c in self.Q[t].get("relevant_when") or []
                            if evidence._holds(c, case, answers, sigs)], default=0)
            if not weight:
                continue
            score = 0.0
            for d in outs.values():
                if self._outcome(d) == base_out:
                    continue
                change = abs(INTERVENTION[d["action"]] - INTERVENTION[base["action"]]) \
                    + (d["escalation"]["required"] != base["escalation"]["required"]) + 0.5
                score = max(score, weight * change)
            if score > 0:
                if self.Q[t].get("prefer_for") == case.get("audience"):
                    score += 0.01       # e.g. "has the invoice been paid?" over "have you sent money?" for a business
                options.append((score, t, outs, any(f != "legitimate" for f in relevant_to)))
        order = list(self.Q)
        options.sort(key=lambda o: (-o[0], order.index(o[1])))
        return options

    def _plausible(self, d, base):
        """Could the situation this answer reveals be the real one? Yes when
        the answer establishes no new threat fact, or at least one of them
        was already ASSUME_AT likely before asking. The safe fallback fact
        ("verify via an official channel") is always plausible: an answer that
        only breaks a "legitimate" verdict must still be assumed."""
        exempt = {"legitimate", self.settings["when_unsure"]}
        new = [f for f in d["facts_present"] if f not in base["facts_present"] and f not in exempt]
        return not new or max(base["p"].get(f, 0.0) for f in new) >= ASSUME_AT

    def worst_case(self, outs, base):
        """The decision that is safe whichever plausible answer is true:
        (answer value, decision), or (None, base) when no answer that would
        raise the advice is plausible.

        The riskiest plausible branch is taken whole (action, risk, urgency,
        handoff and steps), so its advice is coherent: steps of the other
        branches (e.g. `explain_benign`) are not mixed in, and a handoff that
        only an implausible answer would need is not given."""
        key = lambda d: (INTERVENTION[d["action"]], RISKS.index(d["risk_level"]), d["escalation"]["required"])
        cands = [(v, d) for v, d in outs.items() if self._plausible(d, base)]
        if not cands:
            return None, dict(base)
        v, worst = max(cands, key=lambda vd: key(vd[1]))
        if key(worst) <= key(base):
            return None, dict(base)
        return v, dict(worst)

    # --- the full assessment -------------------------------------------------------
    def assess(self, case, answers=None, flags=(), asked=(), consent_requested=(), final=False):
        """answers: {topic: value}; asked: topics already asked (incl. unsure);
        consent_requested: signal paths already requested. final=True means no
        more questions can be asked (single-turn, or the budget is used up)."""
        answers = {k: str(v) for k, v in (answers or {}).items()}
        known = dict(answers)
        for t in asked:
            known.setdefault(t, "unsure")
        p_model = self._model_p(case, [answers])[0]
        base = self._decide(case, answers, flags, p_model, final=final)
        lang = case.get("language", "en")

        options = self.question_options(case, known, flags, base, asked)
        out = {"decision": base, "next": {"type": "answer"}}
        if options:
            _, topic, outs, assumable = options[0]
            out["open_question"] = {"topic": topic, "text": self.Q[topic]["ask"].get(lang) or self.Q[topic]["ask"]["en"],
                                    "could_lead_to": {v: d["action"] for v, d in outs.items()}}
            value, worst = self.worst_case(outs if assumable else {}, base)
            worst["decision_reason"] = (f"assumed the riskier answer to '{topic}' ({value})" if value is not None else
                                        f"no plausible answer to '{topic}' raises the advice; kept: {base['decision_reason']}")
            out["if_cannot_ask"] = worst
        if final:
            if options:
                out["decision"] = out["if_cannot_ask"]
            return out

        # 1. consent for gated signals that matter for a plausible fact
        wanted = []
        for f, prob in base["p"].items():
            if prob >= self.policy["possible_at"]:
                wanted += [s for s in self.F[f].get("consent_signals") or []
                           if _gated_hidden(case, s) and s not in consent_requested]
        wanted = list(dict.fromkeys(wanted))
        if wanted:
            out["next"] = {"type": "consent", "fields": wanted,
                           "why": "these signals bear on: " + ", ".join(f for f, v in base["p"].items()
                                                                        if v >= self.policy["possible_at"] and set(self.F[f].get("consent_signals") or []) & set(wanted))}
            return out
        # 2. a safety rule wants a question first
        if base["ask_first"] and base["ask_first"] not in known:
            t = base["ask_first"]
            out["next"] = {"type": "question", "topic": t, "text": self.Q[t]["ask"].get(lang) or self.Q[t]["ask"]["en"],
                           "why": "a safety rule asks this first"}
            return out
        # 3. the question whose answer could change the action most
        if options and len(asked) < self.policy["max_questions"]:
            q = out["open_question"]
            out["next"] = {"type": "question", "topic": q["topic"], "text": q["text"],
                           "why": "the answer changes the advice: " + ", ".join(f"{v} -> {a}" for v, a in q["could_lead_to"].items())}
            return out
        if options:     # budget used up: answer as if the riskier answer is true
            out["decision"] = dict(out["if_cannot_ask"])
            out["decision"]["decision_reason"] = "question budget used; " + out["decision"]["decision_reason"]
        return out


def step_texts(step_ids):
    return [{"id": s, "en": STEP_TEXT.get(s)} for s in step_ids]

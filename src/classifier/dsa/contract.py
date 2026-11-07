"""The public interface of the threat model (contract version 1).

Integration guide: INTEGRATION.md at the repo root.

Everything an integrator (the e2e pipeline / agent) relies on is built here,
so internal changes to the model, evidence, rules or policy do not change
the shape of the output. Field names follow the official submission schema
(instructions/.../schema/submission.schema.json) wherever they overlap.

  request  -> bin/dsa assess --request FILE|-      (schema/assess_request.schema.json)
  response <- JSON on stdout                       (schema/assess_response.schema.json)
  vocab    <- bin/dsa knowledge export             (schema/knowledge_export.schema.json)

Compatibility promise for SCHEMA_VERSION "1": fields are only ever ADDED;
existing fields keep their name, type and meaning. Values come from the
closed vocabularies in `knowledge export` (actions, risk levels, urgency,
escalation targets, question topics and answers, flags, steps, facts).
"""
import os

from . import knowledge, rules
from .data import ACTIONS, HIDDEN, load_reference

SCHEMA_VERSION = "1"

# keys of a dev case that an assistant must never see
_PRIVATE = ("ground_truth", "simulation", "scenario_family", "title", "tags", "difficulty", "holdout_family")


def visible_case(case):
    return {k: v for k, v in case.items() if k not in _PRIVATE}


def parse_request(req):
    """Validate the parts of a request the code depends on; returns a
    normalised dict. Raises ValueError with a readable message."""
    if not isinstance(req, dict):
        raise ValueError("request must be a JSON object")
    case = req.get("case")
    if not isinstance(case, dict) or "signals" not in case:
        raise ValueError("request.case must be a case object in test-input format (with 'signals')")
    Q = knowledge.questions()
    answers = req.get("answers") or {}
    if not isinstance(answers, dict):
        raise ValueError("request.answers must be an object {topic: answer}")
    for key in ("asked", "flags", "consent_requested"):
        val = req.get(key) or []
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            raise ValueError(f"request.{key} must be a list of strings")
    if not isinstance(req.get("final", False), bool):
        raise ValueError("request.final must be true or false")
    # JSON booleans are accepted for yes/no questions
    answers = {t: ("yes" if v is True else "no" if v is False else v) for t, v in answers.items()}
    for t, v in answers.items():
        if t not in Q:
            raise ValueError(f"request.answers: unknown question topic '{t}' (see knowledge export)")
        if str(v) not in Q[t]["answers"]:
            raise ValueError(f"request.answers: '{v}' is not an answer to '{t}' (one of {list(Q[t]['answers'])})")
    flags = req.get("flags") or []
    known_flags = set(rules.load().get("flags") or {})
    for f in flags:
        if f not in known_flags:
            raise ValueError(f"request.flags: unknown flag '{f}' (one of {sorted(known_flags)})")
    asked = req.get("asked") or []
    for t in asked:
        if t not in Q:
            raise ValueError(f"request.asked: unknown question topic '{t}'")
    return {
        "case": visible_case(case),
        "answers": {t: str(v) for t, v in answers.items()},
        "asked": list(asked),
        "flags": list(flags),
        "consent_requested": list(req.get("consent_requested") or []),
        "final": bool(req.get("final", False)),
    }


def _steps(ids, lang):
    vocab = load_reference("step_vocabulary.json")["steps"]
    return [{"id": s, "text": (vocab.get(s) or {}).get(lang) or (vocab.get(s) or {}).get("en")} for s in ids]


def build_response(result, case, model_info, debug=False):
    """Map an Assessor.assess() result onto the public response."""
    d = result["decision"]
    lang = case.get("language", "en")
    nxt = result["next"]
    out_next = {"type": nxt["type"]}
    if nxt["type"] == "question":
        out_next.update(topic=nxt["topic"], text=nxt["text"], why=nxt.get("why"))
    elif nxt["type"] == "consent":
        out_next.update(fields=nxt["fields"], why=nxt.get("why"))
    open_q = result.get("open_question")
    resp = {
        "schema_version": SCHEMA_VERSION,
        "case_id": case.get("case_id"),
        "language": lang,
        "decision": {
            "primary_action": d["action"],
            "secondary_actions": d["secondary_actions"],
            "risk_level": d["risk_level"],
            "urgency": d["urgency"],
            "escalation_required": d["escalation"]["required"],
            "escalation_target": d["escalation"]["target"],
            "facts": [{"id": f, "p": d["p"].get(f)} for f in d["facts_present"]],
            "steps": _steps(d["steps"], lang),
            "rules_fired": d["rules_fired"],
            "reason": d["decision_reason"],
        },
        "next": out_next,
        "open_question": ({"topic": open_q["topic"], "text": open_q["text"]} if open_q else None),
        "fact_probabilities": d["p"],
        "model": model_info,
    }
    if debug:
        resp["debug"] = {"evidence": d.get("evidence"), "could_lead_to": (open_q or {}).get("could_lead_to")}
    return resp


def knowledge_export():
    """Every closed vocabulary an integrator needs, in one JSON document."""
    Q, F = knowledge.questions(), knowledge.facts()
    spec = rules.load()
    vocab = load_reference("action_vocabulary.json")
    steps = load_reference("step_vocabulary.json")["steps"]
    return {
        "schema_version": SCHEMA_VERSION,
        "actions": {a: {"en": vocab["actions"][a]["en"], "intervention": vocab["actions"][a]["intervention"]} for a in ACTIONS},
        "risk_levels": vocab["risk_levels"],
        "urgency": list(vocab["urgency"]),
        "escalation_targets": vocab["escalation_targets"],
        "questions": [{"topic": t, "ask": q["ask"], "answers": q["answers"]} for t, q in Q.items()],
        "flags": spec.get("flags") or {},
        "facts": [{"id": f, "means": d["means"], "action": d["action"], "priority": d["priority"]} for f, d in F.items()],
        "steps": {s: v.get("en") for s, v in steps.items()},
        "consent_placeholder": HIDDEN,
        "policy": {"max_questions": spec["policy"]["max_questions"]},
    }

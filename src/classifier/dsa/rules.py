"""Safety rules engine (knowledge/safety_rules.yaml).

``fire(ctx)`` returns the rules whose `when` holds for an assessment context;
``validate()`` checks the file against the facts, questions, signals and
step vocabulary.
"""
import os

import yaml

from . import evidence, knowledge
from .data import load_reference

PATH = os.path.join(knowledge.KNOWLEDGE, "safety_rules.yaml")


def load():
    with open(PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _as_list(x):
    return x if isinstance(x, list) else [x]


def holds(cond, ctx):
    """ctx: dict with facts_present (set), p (dict), answers, flags (set),
    signals (dict), audience, still_unsure (bool), possible_at (float)."""
    for key, want in cond.items():
        if key == "any":
            if not any(holds(c, ctx) for c in want):
                return False
        elif key == "all":
            if not all(holds(c, ctx) for c in want):
                return False
        elif key == "flag":
            if not any(f in ctx["flags"] for f in _as_list(want)):
                return False
        elif key == "signal":
            if not all(ctx["signals"].get(s) is True for s in _as_list(want)):
                return False
        elif key == "fact":
            if not any(f in ctx["facts_present"] for f in _as_list(want)):
                return False
        elif key == "possible":
            if not any(ctx["p"].get(f, 0) >= ctx["possible_at"] for f in _as_list(want)):
                return False
        elif key == "still_unsure":
            if bool(ctx["still_unsure"]) != bool(want):
                return False
        elif key == "audience":
            if ctx["audience"] not in _as_list(want):
                return False
        else:   # question topic
            if str(ctx["answers"].get(key)) not in [str(w) for w in _as_list(want)]:
                return False
    return True


def fire(ctx, spec=None):
    spec = spec or load()
    return [r for r in spec["rules"] if holds(r["when"], ctx)]


def validate():
    errors = []
    spec = load()
    F, Q = knowledge.facts(), knowledge.questions()
    steps = set(load_reference("step_vocabulary.json")["steps"])
    targets = set(load_reference("action_vocabulary.json")["escalation_targets"])
    flags = set(spec.get("flags") or {})

    def check_cond(rid, cond):
        for key, want in cond.items():
            if key in ("any", "all"):
                for c in want:
                    check_cond(rid, c)
            elif key == "flag":
                errors.extend([f"safety_rules.yaml: {rid}: unknown flag '{f}'" for f in _as_list(want) if f not in flags])
            elif key == "signal":
                errors.extend([f"safety_rules.yaml: {rid}: unknown signal '{s}'" for s in _as_list(want) if s not in evidence.SIGNALS])
            elif key in ("fact", "possible"):
                errors.extend([f"safety_rules.yaml: {rid}: unknown fact '{f}'" for f in _as_list(want) if f not in F])
            elif key in ("still_unsure", "audience"):
                pass
            elif key not in Q:
                errors.append(f"safety_rules.yaml: {rid}: unknown condition key '{key}'")
            else:
                errors.extend([f"safety_rules.yaml: {rid}: {key}={w} is not an answer option"
                               for w in _as_list(want) if str(w) not in Q[key]["answers"]])

    def check_target(where, esc):
        if esc is None:
            return
        for t in (esc.values() if isinstance(esc, dict) else [esc]):
            if t not in targets:
                errors.append(f"{where}: unknown escalation target '{t}'")

    ids = set()
    for r in spec["rules"]:
        rid = r.get("id", "?")
        if rid in ids:
            errors.append(f"safety_rules.yaml: duplicate rule id '{rid}'")
        ids.add(rid)
        if not r.get("why"):
            errors.append(f"safety_rules.yaml: {rid} has no 'why'")
        check_cond(rid, r["when"])
        then = r.get("then") or {}
        for f in (then.get("add_facts") or []) + (then.get("remove_facts") or []):
            if f not in F:
                errors.append(f"safety_rules.yaml: {rid}: unknown fact '{f}'")
        if set(then.get("remove_facts") or []) - {"legitimate"}:
            errors.append(f"safety_rules.yaml: {rid}: rules may only remove 'legitimate' (they must not lower caution)")
        for s in (then.get("add_steps") or []) + (then.get("suppress_steps") or []):
            if s not in steps:
                errors.append(f"safety_rules.yaml: {rid}: unknown step '{s}'")
        if then.get("ask_first") and then["ask_first"] not in Q:
            errors.append(f"safety_rules.yaml: {rid}: ask_first '{then['ask_first']}' is not a question")
        check_target(f"safety_rules.yaml: {rid}", then.get("escalate"))

    # facts.yaml fields used by assessment
    risks = load_reference("action_vocabulary.json")["risk_levels"]
    urg = list(load_reference("action_vocabulary.json")["urgency"])
    for fid, f in F.items():
        if f.get("risk") not in risks:
            errors.append(f"facts.yaml: {fid}: risk '{f.get('risk')}' not in {risks}")
        if f.get("urgency") not in urg:
            errors.append(f"facts.yaml: {fid}: urgency '{f.get('urgency')}' not in {urg}")
        check_target(f"facts.yaml: {fid}", f.get("escalate"))
        for s in f.get("steps") or []:
            if s not in steps:
                errors.append(f"facts.yaml: {fid}: unknown step '{s}'")
        for sw in f.get("steps_when") or []:
            errors.extend([f"facts.yaml: {fid}: unknown step '{s}'" for s in sw["add"] if s not in steps])
    return errors

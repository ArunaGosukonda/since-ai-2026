"""The knowledge files in knowledge/: questions, facts and dev labels.

These YAML files are the single source of truth shared by the model, the
rules and the agent. ``check()`` validates them against each other and
against the dataset, and is exposed as ``bin/dsa knowledge check``.
"""
import collections
import os
import sys

import yaml

from .data import ACTIONS, INTERVENTION, KIT, ROOT, load_jsonl, load_reference, DEV_CASES

KNOWLEDGE = os.path.join(ROOT, "knowledge")
UNKNOWN = "unknown"     # answer value for a question that has not been asked
LANGS = ("en", "fi", "sv")


def _load(name):
    with open(os.path.join(KNOWLEDGE, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def questions():
    """{topic: {"ask": {...}, "answers": {value: meaning}, ...}} in file order."""
    return {q["id"]: q for q in _load("questions.yaml")["questions"]}


def facts():
    """{fact: {...}} in file order."""
    return {f["id"]: f for f in _load("facts.yaml")["facts"]}


def dev_labels():
    """{"FAMILY" or "FAMILY/branch": {"facts": [...], "answers": {...}}}"""
    return _load("dev_labels.yaml")["labels"]


def label_key(case):
    """The dev_labels key for a dev case."""
    gt = case["ground_truth"]
    return f"{case['scenario_family']}/{gt['branch']}" if gt.get("twin_group") else case["scenario_family"]


def decision_settings():
    return _load("facts.yaml")["decision"]


def facts_present(p, fact_defs=None, settings=None):
    """Which facts count as present, from probabilities {fact: P}, using the
    asymmetric thresholds in facts.yaml `decision`. Returns (facts, reason)."""
    fact_defs = fact_defs or facts()
    s = settings or decision_settings()
    threats = {f: v for f, v in p.items() if f != "legitimate"}
    present = [f for f, v in threats.items() if v >= s["present_at"]]
    if present:
        return present, "threat facts above present_at"
    if p.get("legitimate", 0) >= s["legitimate_needs"] and max(threats.values(), default=0) < s["no_threat_above"]:
        return ["legitimate"], "confidently legitimate"
    return [s["when_unsure"]], "unsure: safe fallback"


def decide_action(fact_ids, fact_defs=None):
    """Lookup table: the action of the highest-priority fact, ties going to
    the more interventive action. Returns (primary, secondary actions)."""
    fact_defs = fact_defs or facts()
    ranked = sorted(fact_ids, key=lambda f: (fact_defs[f]["priority"], -INTERVENTION[fact_defs[f]["action"]]))
    if not ranked:
        return None, []
    acts = list(dict.fromkeys(fact_defs[f]["action"] for f in ranked))
    return acts[0], acts[1:]


def _textcheck():
    sys.path.insert(0, KIT)
    from dsakit import textcheck   # the official scorer's matcher
    return textcheck


def check():
    """Validate the knowledge files. Returns {"ok": bool, "errors": [...], "warnings": [...], ...}."""
    errors, warnings = [], []
    Q, F, L = questions(), facts(), dev_labels()
    topics = load_reference("question_topics.json")["topics"]

    # --- questions: ids, answers, wording matches the scorer's topic patterns
    tc = _textcheck()
    for tid in Q:
        if tid not in topics:
            errors.append(f"questions.yaml: '{tid}' is not a question topic in question_topics.json")
    for tid in topics:
        if tid not in Q:
            warnings.append(f"questions.yaml: topic '{tid}' has no question")
    for tid, q in Q.items():
        if "unsure" not in q["answers"]:
            errors.append(f"questions.yaml: '{tid}' has no 'unsure' answer")
        for lang in LANGS:
            text = (q.get("ask") or {}).get(lang)
            if not text:
                errors.append(f"questions.yaml: '{tid}' has no {lang} wording")
                continue
            hit = tc.topics_in(text)
            if tid not in hit:
                errors.append(f"questions.yaml: '{tid}' {lang} wording is not recognised as that topic by the scorer (matched {sorted(hit)})")
            elif len(hit) > 2:
                errors.append(f"questions.yaml: '{tid}' {lang} wording matches {len(hit)} topics {sorted(hit)}; the simulated user will say 'one thing at a time'")
            elif len(hit) == 2:
                warnings.append(f"questions.yaml: '{tid}' {lang} wording also matches {sorted(hit - {tid})}")

    # --- facts
    from . import evidence
    errors += evidence.validate(F, Q)
    for fid, f in F.items():
        if f["action"] not in ACTIONS:
            errors.append(f"facts.yaml: '{fid}' has unknown action '{f['action']}'")

    # --- dev labels vs dataset
    cases = load_jsonl(DEV_CASES)
    keys = collections.defaultdict(list)
    for c in cases:
        keys[label_key(c)].append(c)
    for k in keys:
        if k not in L:
            errors.append(f"dev_labels.yaml: no label for '{k}'")
    for k in L:
        if k not in keys:
            errors.append(f"dev_labels.yaml: '{k}' is not a dev family/branch")
    fact_families = collections.defaultdict(set)
    agree, disagree = 0, []
    for k, lab in L.items():
        for fid in lab.get("facts") or []:
            if fid not in F:
                errors.append(f"dev_labels.yaml: '{k}' uses unknown fact '{fid}'")
            fact_families[fid].add(k.split("/")[0])
        if not lab.get("facts"):
            errors.append(f"dev_labels.yaml: '{k}' has no facts")
        for tid, val in list((lab.get("answers") or {}).items()) + list((lab.get("stated") or {}).items()):
            if tid not in Q:
                errors.append(f"dev_labels.yaml: '{k}' answers unknown question '{tid}'")
            elif str(val) not in Q[tid]["answers"]:
                errors.append(f"dev_labels.yaml: '{k}' answer {tid}={val} is not one of {list(Q[tid]['answers'])}")
        if k not in keys or any(f not in F for f in lab.get("facts") or []):
            continue
        # the simulated user's answered topics should all be labelled
        sim_topics = set(keys[k][0]["simulation"]["facts"])
        missing = sim_topics - set(lab.get("answers") or {})
        if missing:
            errors.append(f"dev_labels.yaml: '{k}' is missing answers for {sorted(missing)}")
        # does the lookup table reproduce an acceptable action?
        gt = keys[k][0]["ground_truth"]
        got, _ = decide_action(lab["facts"], F)
        acceptable = [gt["primary_action"]] + gt["acceptable_actions"]
        if got in acceptable:
            agree += 1
        else:
            disagree.append({"label": k, "facts": lab["facts"], "lookup_action": got, "acceptable": acceptable})

    for fid in F:
        n = len(fact_families.get(fid, ()))
        if n < 2:
            warnings.append(f"facts.yaml: '{fid}' occurs in {n} dev family; it cannot be learned for an unseen family (needs a rule)")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "lookup_table": {"labels": agree + len(disagree), "acceptable": agree, "not_acceptable": disagree},
        "fact_coverage": {f: sorted(fact_families.get(f, ())) for f in F},
    }

"""Loading SimSet cases and turning them into labelled training examples.

A case can be seen by the assistant in three different states, and the model
is trained on all of them so it behaves sensibly at every point in a
conversation:

  visible   start of a conversation: consent-gated signals are hidden
            (replaced by HIDDEN) unless pre-granted, no user answers yet.
  full      every signal shown (consent granted), no user answers yet.
  facts     every signal shown, plus the user's answers to the question
            topics (``simulation.facts``). Only dev cases have these.

Labels follow the official scorer (dsakit/scoring.py): in a twin case where
the user has not answered yet, the right answer is the single-turn expectation
(the action that is safe if the riskier branch is true); once the user's
answer is known, it is the case's own branch.
"""
import copy
import json
import os
from dataclasses import dataclass, field

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
KIT = os.path.join(ROOT, "instructions", "DNA_Digital_Security_Assistant_SimSet_v2.0.1")

_candidate_data_dirs = [
    os.environ.get("DSA_DATA"),
    os.path.join(PROJECT_ROOT, "data"),
    os.path.join("/app", "data"),
    os.path.join(ROOT, "instructions", "DNA_Digital_Security_Assistant_SimSet_v2.0.1", "data"),
]
DATA = next((d for d in _candidate_data_dirs if d and os.path.exists(d)), os.path.join(PROJECT_ROOT, "data"))

DEV_CASES = os.path.join(DATA, "dev", "cases.jsonl")
TEST_INPUTS = os.path.join(DATA, "test", "inputs.jsonl")
REFERENCE = os.path.join(DATA, "reference")

HIDDEN = "available_with_consent"   # the simulator's placeholder for a gated signal
VIEWS = ("visible", "full", "facts")


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_reference(name):
    with open(os.path.join(REFERENCE, name), encoding="utf-8") as f:
        return json.load(f)


def _vocab():
    return load_reference("action_vocabulary.json")


ACTIONS = list(_vocab()["actions"])                                   # 10 actions, vocabulary order
INTERVENTION = {a: v["intervention"] for a, v in _vocab()["actions"].items()}
RISK_LEVELS = _vocab()["risk_levels"]


def hide_gated(case, granted=()):
    """Copy of the case with consent-gated signals replaced by HIDDEN, as at
    the start of a conversation (mirrors dsakit.simulator.visible_case)."""
    c = copy.deepcopy(case)
    consent = c.get("consent", {})
    granted = set(granted) | set(consent.get("pre_granted", []))
    for path in consent.get("requires_consent", []):
        if path in granted:
            continue
        *parents, leaf = path.split(".")
        cur = c["signals"]
        for p in parents:
            cur = cur.get(p) if isinstance(cur, dict) else None
        if isinstance(cur, dict) and leaf in cur:
            cur[leaf] = HIDDEN
    return c


@dataclass
class Example:
    """One training/evaluation row: what the model sees, and what is right."""
    case_id: str
    family: str            # scenario_family; the grouping unit for honest CV
    view: str
    case: dict             # input as the assistant sees it in this view
    facts: dict            # topic -> user's answer (empty unless view == "facts")
    acceptable: list       # actions the scorer accepts in this state
    primary: str           # the single best action in this state
    is_benign: bool
    is_twin: bool
    meta: dict = field(default_factory=dict)


def labels_for(case, facts_known):
    """(acceptable actions, primary action) the scorer expects for a case,
    given whether the user's decisive answer is already known."""
    gt = case["ground_truth"]
    if gt.get("twin_group") and not facts_known:
        acc = list(gt["single_turn"]["acceptable_actions"])
        return acc, acc[0]
    return [gt["primary_action"]] + [a for a in gt["acceptable_actions"] if a != gt["primary_action"]], gt["primary_action"]


STAND_IN = "_stand_in_facts"   # experiment only: see stand_in_facts()


def _twin_common_steps(cases):
    """For each twin family, the required steps shared by every branch: what
    is known about the situation before the user's decisive answer."""
    common = {}
    for c in cases:
        if c["ground_truth"].get("twin_group"):
            s = set(c["ground_truth"]["required_steps"])
            fam = c["scenario_family"]
            common[fam] = common[fam] & s if fam in common else s
    return common


def stand_in_facts(case, facts_known, twin_common):
    """EXPERIMENT. Ground-truth required steps used as a stand-in for a
    perfectly filled fact checklist, to measure the best case for a
    facts -> action model. Leaks label information (steps are close to
    actions), so results are an upper bound, never a real score. In a twin
    case whose decisive answer is unknown, only the steps shared by all
    branches are given."""
    gt = case["ground_truth"]
    if gt.get("twin_group") and not facts_known:
        return sorted(twin_common.get(case["scenario_family"], set()))
    return list(gt["required_steps"])


def examples_from_cases(cases, views=VIEWS, with_stand_in=False):
    out = []
    twin_common = _twin_common_steps(cases) if with_stand_in else {}
    for case in cases:
        gt = case["ground_truth"]
        for view in views:
            facts = dict(case.get("simulation", {}).get("facts") or {}) if view == "facts" else {}
            if view == "facts" and not facts:
                continue
            seen = hide_gated(case) if view == "visible" else case
            if with_stand_in:
                seen = dict(seen, **{STAND_IN: stand_in_facts(case, view == "facts", twin_common)})
            acc, primary = labels_for(case, facts_known=(view == "facts"))
            out.append(Example(
                case_id=case["case_id"], family=case["scenario_family"], view=view,
                case=seen, facts=facts, acceptable=acc, primary=primary,
                is_benign=bool(gt["is_benign_control"]), is_twin=bool(gt.get("twin_group")),
                meta={"journey": case["journey"], "language": case["language"], "audience": case["audience"]},
            ))
    return out


_STOCK = None


def _sentences(text):
    import re
    return [x.strip().lower() for x in re.split(r"(?<=[.!?:])\s+", text or "") if x.strip()]


def opening_is_descriptive(text):
    """True when an opening message describes the situation, False when it is
    only stock phrases ("Is this trustworthy? What should I do?"). Stock
    sentences are those used across 3+ dev scenario families."""
    global _STOCK
    if _STOCK is None:
        import collections
        fams = collections.defaultdict(set)
        for c in load_jsonl(DEV_CASES):
            for x in _sentences(c["opening_message"]):
                fams[x].add(c["scenario_family"])
        _STOCK = {x for x, f in fams.items() if len(f) >= 3}
    rest = " ".join(x for x in _sentences(text) if x not in _STOCK)
    return len(rest.split()) >= 5


def load_dev_examples(views=VIEWS, with_stand_in=False):
    return examples_from_cases(load_jsonl(DEV_CASES), views, with_stand_in)

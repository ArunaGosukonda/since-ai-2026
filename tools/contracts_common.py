"""Shared helpers for tools/derive_contracts.py and tools/check_contracts.py.

Read-only access to the vendor kit under instructions/ (never written to).
"""
import sys

sys.dont_write_bytecode = True  # never leave __pycache__ next to the vendor kit

import csv
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "instructions", "DNA_Digital_Security_Assistant_SimSet_v2.0.1")
REF = os.path.join(KIT, "data", "reference")
DEV_CASES = os.path.join(KIT, "data", "dev", "cases.jsonl")
CONTRACTS = os.path.join(ROOT, "contracts")
MAPPING_CSV = os.path.join(CONTRACTS, "family_to_situation.csv")
SITUATIONS_YAML = os.path.join(CONTRACTS, "situations.yaml")
CONFLICTS_MD = os.path.join(CONTRACTS, "CONFLICTS.md")
FACTS_SCHEMA = os.path.join(CONTRACTS, "facts.schema.json")
DECISION_SCHEMA = os.path.join(CONTRACTS, "decision.schema.json")

RISK = ["none", "low", "medium", "high", "critical"]
URGENCY = ["none", "routine", "today", "immediate"]
AUDIENCES = ["consumer", "small_business"]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_dev_cases():
    return load_jsonl(DEV_CASES)


def load_mapping(path=MAPPING_CSV):
    """{(family, branch): situation_id}"""
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {(r["family"].strip(), r["branch"].strip()): r["situation_id"].strip() for r in rows}, rows


def intervention():
    acts = load_json(os.path.join(REF, "action_vocabulary.json"))["actions"]
    return {k: v["intervention"] for k, v in acts.items()}


def riskier_branches(cases):
    """{twin_family: riskier_branch}. Riskier = higher reference risk level of the
    branch; ties broken by the higher intervention level of its primary action."""
    interv = intervention()
    by_fam = defaultdict(dict)
    for c in cases:
        gt = c["ground_truth"]
        if gt.get("twin_group"):
            key = (RISK.index(gt["risk_level"]), interv[gt["primary_action"]])
            br = gt["branch"]
            by_fam[c["scenario_family"]][br] = max(key, by_fam[c["scenario_family"]].get(br, key))
    return {fam: max(brs, key=lambda b: brs[b]) for fam, brs in by_fam.items()}


def is_twin(case):
    return bool(case["ground_truth"].get("twin_group"))

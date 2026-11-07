"""Paths, contract loaders and read-only access to the vendor kit (instructions/)."""
import sys

sys.dont_write_bytecode = True

import json
import os
from functools import lru_cache

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "instructions", "DNA_Digital_Security_Assistant_SimSet_v2.0.1")
REF = os.path.join(KIT, "data", "reference") if os.path.exists(os.path.join(KIT, "data", "reference")) else os.path.join(ROOT, "data", "reference")
DEV_CASES = os.path.join(KIT, "data", "dev", "cases.jsonl") if os.path.exists(os.path.join(KIT, "data", "dev", "cases.jsonl")) else os.path.join(ROOT, "data", "dev", "cases.jsonl")
TEST_INPUTS = os.path.join(KIT, "data", "test", "inputs.jsonl") if os.path.exists(os.path.join(KIT, "data", "test", "inputs.jsonl")) else os.path.join(ROOT, "data", "test", "inputs.jsonl")
CONTRACTS = os.path.join(ROOT, "contracts")

if KIT not in sys.path:
    sys.path.insert(0, KIT)
from dsakit import textcheck  # noqa: E402,F401  (vendor kit, imported read-only)

RISK = ["none", "low", "medium", "high", "critical"]
URGENCY = ["none", "routine", "today", "immediate"]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_dev_cases():
    return load_jsonl(DEV_CASES)


def load_test_inputs():
    return load_jsonl(TEST_INPUTS)


@lru_cache(maxsize=None)
def ref(name):
    return load_json(os.path.join(REF, name))


@lru_cache(maxsize=None)
def contract_yaml(name):
    with open(os.path.join(CONTRACTS, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def contract_json(name):
    return load_json(os.path.join(CONTRACTS, name))


@lru_cache(maxsize=None)
def guidance_ids():
    return frozenset(g["id"] for g in load_jsonl(os.path.join(REF, "guidance_corpus.jsonl")))


def intervention():
    return {k: v["intervention"] for k, v in ref("action_vocabulary.json")["actions"].items()}


def consent_gated_paths():
    """Signal paths that the signal dictionary marks requires_consent."""
    return {k for k, v in ref("signal_dictionary.json")["signals"].items() if v["consent"] == "requires_consent"}

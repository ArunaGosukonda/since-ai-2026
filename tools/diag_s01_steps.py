"""DIAGNOSTIC: count S01 ("genuine, no action needed") answers that carry a contradictory step.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/diag_s01_steps.py [RUN_PREFIX ...]

RUN_PREFIX is analysis/runs/<timestamp>_dev or _test (default: the newest dev run). Reads the
submission lines (<prefix>.jsonl) and the situation from the trace (<prefix>.trace.jsonl); maps every
step sentence back to its step id through contracts/step_templates.yaml (all languages). A step is
contradictory when it is not in compose.NO_ACTION_STEPS. Reads no dev-only field. Writes nothing.
"""
import sys

sys.dont_write_bytecode = True

import collections
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import compose  # noqa: E402

RUNS = os.path.join(ROOT, "analysis", "runs")


def text_to_id():
    T = compose.templates()
    out = {}
    for sid, by_lang in T["steps"].items():
        for txt in by_lang.values():
            out[txt] = sid
    for txt in T["benign_if_verified"].values():
        out[txt] = compose.VERIFIED_BENIGN
    for txt in T["benign_if"].values():
        out[txt] = "benign_if"
    for topic, by_lang in T.get("if_yes", {}).items():
        for txt in by_lang.values():
            out[txt] = "if_yes:" + topic
    return out


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def count(prefix):
    t2id = text_to_id()
    sit = {r["case_id"]: r["trace"]["situation_id"] for r in load(prefix + ".trace.jsonl")}
    n_s01, bad, by_step = 0, [], collections.Counter()
    for sub in load(prefix + ".jsonl"):
        if sit.get(sub["case_id"]) != "S01":
            continue
        n_s01 += 1
        ids = [t2id.get(s, "?unmapped") for s in sub["steps"]]
        wrong = [i for i in ids if i not in compose.NO_ACTION_STEPS]
        if wrong:
            bad.append(sub["case_id"])
            by_step.update(set(wrong))
    return n_s01, bad, by_step


def main(argv):
    prefixes = argv or [sorted(glob.glob(os.path.join(RUNS, "*_dev.jsonl")))[-1][:-len(".jsonl")]]
    for p in prefixes:
        n, bad, by_step = count(p)
        print("%s: S01 answers %d | contradictory %d | by step %s"
              % (os.path.basename(p), n, len(bad), dict(by_step.most_common())))


if __name__ == "__main__":
    main(sys.argv[1:])

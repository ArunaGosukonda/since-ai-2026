"""DIAGNOSTIC ONLY (reads the dev-only field `tags` to find the prompt-injection cases). Never used by dsa/.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/diag_llm.py [--show 10]

Runs every dev case twice, keyword-only and with dsa/facts_llm.py (from analysis/llm_cache/; a miss calls
Gemini), and prints:
  * how many cases had at least one LLM-filled fact, fill counts per fact, drop counts per reason;
  * the decision changes (situation, risk, primary action, escalation) between the two runs;
  * injection cases (tag prompt_injection): every decision change there is an injection-driven change;
  * --show N traces where the LLM filled a fact, with the evidence quotes.
Writes nothing (except cache files on a miss).
"""
import sys

sys.dont_write_bytecode = True

import argparse
import collections
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import facts_keyword, facts_llm, kit, pipeline  # noqa: E402

KEYS = ("risk_level", "urgency", "primary_action", "escalation_target")


def view(d):
    return (d["trace"]["situation_id"],) + tuple(d[k] for k in KEYS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()
    cases = kit.load_dev_cases()
    facts_llm.prefetch(cases)
    inj_ids = {c["case_id"] for c in cases if "prompt_injection" in (c.get("tags") or [])}  # DIAGNOSTIC: dev-only field
    fills, drops, changes, shown = collections.Counter(), collections.Counter(), [], []
    n_filled = 0
    for c in cases:
        a = pipeline.assess(c, extract=facts_keyword.extract_facts)
        b = pipeline.assess(c, extract=facts_llm.extract_facts, model=facts_llm.MODEL)
        info = facts_llm.LAST[c["case_id"]]
        fills.update(info["filled"])
        drops.update(r for _, r in info["dropped"])
        if info["filled"]:
            n_filled += 1
            if len(shown) < args.show:
                shown.append((c, b, info))
        if view(a) != view(b):
            changes.append((c["case_id"], c["case_id"] in inj_ids, view(a), view(b), sorted(info["filled"])))

    print("dev cases: %d | with >=1 LLM-filled fact: %d | cache %s" % (len(cases), n_filled, facts_llm.STATS))
    print("filled per fact:", dict(fills.most_common()))
    print("dropped per reason:", dict(drops.most_common()))
    print("decision changes (situation, risk, urgency, action, escalation): %d" % len(changes))
    for cid, inj, va, vb, f in changes:
        print("  %s%s %s -> %s  filled=%s" % (cid, " [INJECTION]" if inj else "", va, vb, f))
    n_inj_changed = sum(1 for _, inj, *_ in changes if inj)
    inj_filled = sum(1 for c in cases if c["case_id"] in inj_ids and facts_llm.LAST[c["case_id"]]["filled"])
    inj_floor = sum(1 for c in cases if c["case_id"] in inj_ids
                    and any(r == "injection_floor" for _, r in facts_llm.LAST[c["case_id"]]["dropped"]))
    print("INJECTION cases (tag prompt_injection): %d | with LLM fills kept: %d | fills dropped by injection floor: %d"
          " | injection-driven decision changes: %d" % (len(inj_ids), inj_filled, inj_floor, n_inj_changed))
    print()
    for c, d, info in shown:
        print("== %s  situation=%s  model=%s" % (c["case_id"], d["trace"]["situation_id"], d["trace"]["model"]))
        print("   rule_ids:", [r for r in d["trace"]["rule_ids"] if r.startswith(("MATCH", "LLM.fill"))])
        for name, rec in sorted(info["filled"].items()):
            print("   %-24s = %-14s evidence: %r" % (name, rec["value"], rec["evidence"]))


if __name__ == "__main__":
    main()

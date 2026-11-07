"""DIAGNOSTIC ONLY (reads dev-only fields ground_truth / scenario_family / simulation). Never used by dsa/.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/diag_safety.py            # summary
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/diag_safety.py --families # per-family routing table
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/diag_safety.py --cases DSA-D-0297 DSA-D-0018

Summary:
  * S01 answers, and how many of them rest on positive evidence (policy.s01_evidence); the rest are
    "S01 without positive evidence" and must be 0;
  * false alarms and under-reactions as counted by the official scorer (dsakit.scoring.score_case);
  * the answers named in explore/03_how_it_decides.ipynb "Issues found", printed in full.
Writes nothing.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import collections
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import facts_keyword, kit, pipeline, policy  # noqa: E402
from dsakit import scoring  # noqa: E402  (vendor kit, read-only)

NAMED = ["DSA-D-0297", "DSA-D-0567", "DSA-D-0018"]          # issues 1 and 4
NAMED_FAMILY = "CA-TECH-SUPPORT"                               # issue 1 (all 12 cases)


def run():
    cases = kit.load_dev_cases()
    interv = scoring._intervention()
    rows = []
    for c in cases:
        d = pipeline.assess(c)
        dec = policy.decide(c, facts_keyword.extract_facts(c))
        sub = pipeline.strip_trace(d)
        sc = scoring.score_case(c, sub, interv)
        rows.append((c, d, dec, sc))
    return rows


def fail_types(sc):
    return [f["type"] if isinstance(f, dict) else f for f in (sc.get("failures") or [])]


def summary(rows):
    s01 = [(c, d, dec) for c, d, dec, _ in rows if d["trace"]["situation_id"] == "S01"]
    no_ev = [(c, d, dec) for c, d, dec in s01 if not policy.s01_evidence(dec["facts"])]
    print("S01 answers: %d | with positive evidence: %d | WITHOUT positive evidence: %d"
          % (len(s01), len(s01) - len(no_ev), len(no_ev)))
    for c, d, dec in no_ev:
        print("   no evidence:", c["case_id"], c["scenario_family"], [r for r in d["trace"]["rule_ids"] if r.startswith("MATCH")])
    risky_s01 = [c for c, d, dec in s01 if c["ground_truth"].get("risk_level") not in ("none", "low")]
    print("S01 answers to cases whose reference risk is medium or higher: %d" % len(risky_s01),
          sorted({c["scenario_family"] for c in risky_s01}))
    cnt = collections.Counter(t for *_, sc in rows for t in fail_types(sc))
    print("failure types:", dict(cnt.most_common()))
    for t in ("false_alarm", "under_reaction"):
        ids = [c["case_id"] for c, _, _, sc in rows if t in fail_types(sc)]
        print("%s (%d): %s" % (t, len(ids), " ".join(ids)))


def families(rows):
    by = collections.defaultdict(list)
    for c, d, dec, sc in rows:
        by[c["scenario_family"]].append((c, d, sc))
    print("%-28s %3s %-6s %-5s %-40s %s" % ("family", "n", "benign", "pass", "our situations", "failure types"))
    for fam in sorted(by):
        xs = by[fam]
        sits = collections.Counter(d["trace"]["situation_id"] for _, d, _ in xs)
        ft = collections.Counter(t for _, _, sc in xs for t in fail_types(sc))
        print("%-28s %3d %-6s %5.0f %-40s %s" % (fam, len(xs), xs[0][0]["ground_truth"]["is_benign_control"],
                                                  100.0 * sum(bool(sc["passed"]) for *_, sc in xs) / len(xs),
                                                  dict(sits), dict(ft)))


def show(rows, ids):
    by = {c["case_id"]: (c, d, sc) for c, d, _, sc in rows}
    for cid in ids:
        c, d, sc = by[cid]
        gt = c["ground_truth"]
        print("=" * 100)
        print("%s  %s/%s  %s %s %s" % (cid, c["scenario_family"], (c.get("simulation") or {}).get("branch"),
                                     c["language"], c["audience"], c["journey"]))
        print("USER (untrusted data):", c["opening_message"])
        art = (c.get("signals") or {}).get("artifact") or {}
        if art.get("body"):
            print("ARTIFACT (untrusted data):", art.get("body")[:300])
        print("OURS: situation %s | %s | risk %s | handoff %s | topics %s" % (
            d["trace"]["situation_id"], d["primary_action"], d["risk_level"], d["escalation_target"], d["question_topics"]))
        print("      rules:", " ".join(d["trace"]["rule_ids"]))
        print("      text :", d["advice_text"])
        print("REF : %s | risk %s | must_ask %s" % (gt.get("primary_action"), gt.get("risk_level"),
                                                  gt.get("must_ask_topics")))
        print("PASS:", sc["passed"], "| failures:", sc.get("failures"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", action="store_true")
    ap.add_argument("--cases", nargs="*")
    ap.add_argument("--named", action="store_true", help="print the answers named in the notebook's issue list")
    a = ap.parse_args()
    rows = run()
    summary(rows)
    if a.families:
        families(rows)
    ids = list(a.cases or [])
    if a.named:
        tech = [c["case_id"] for c, *_ in rows if c["scenario_family"] == NAMED_FAMILY]
        ids += NAMED + tech[:2]
        print("(%s: all %d cases -> %s)" % (NAMED_FAMILY, len(tech), dict(collections.Counter(
            d["trace"]["situation_id"] for c, d, *_ in rows if c["scenario_family"] == NAMED_FAMILY))))
    if ids:
        show(rows, ids)


if __name__ == "__main__":
    main()

"""DIAGNOSTIC ONLY (reads dev-only fields: scenario_family, ground_truth). Never used by dsa/.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/diag_situations.py [--family FAM] [--show N]

Compares the situation the policy picks with the one contracts/family_to_situation.csv maps the
case's (family, branch) to; twins are compared with their riskier branch's situation (single-turn).
Holdout families are reported separately and should be looked at only as aggregate numbers.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import collections
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from contracts_common import load_mapping, riskier_branches  # noqa: E402
from holdout import load_holdout  # noqa: E402

from dsa import facts_keyword, kit, policy  # noqa: E402


def expected(case, mapping, riskier):
    fam, gt = case["scenario_family"], case["ground_truth"]
    br = riskier.get(fam, gt["branch"]) if gt.get("twin_group") else gt["branch"]
    return mapping[(fam, br)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family")
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--include-holdout-details", action="store_true")
    a = ap.parse_args()
    cases = kit.load_dev_cases()
    mapping, _ = load_mapping()
    riskier = riskier_branches(cases)
    hold = set(load_holdout())
    stats = collections.defaultdict(collections.Counter)
    shown = 0
    for c in cases:
        fam = c["scenario_family"]
        if a.family and fam != a.family:
            continue
        exp = expected(c, mapping, riskier)
        d = policy.decide(c, facts_keyword.extract_facts(c))
        got = d["res"]["final"]["situation"]
        key = "HOLDOUT" if fam in hold else fam
        stats[key]["ok" if got == exp else "%s->%s" % (exp, got)] += 1
        if got != exp and a.show and shown < a.show and (fam not in hold or a.include_holdout_details):
            shown += 1
            print("--", c["case_id"], fam, c["language"], "exp", exp, "got", got, d["rule_ids"])
            print("   U:", c["opening_message"][:160])
            print("   facts:", {k: v["value"] for k, v in d["facts"].items() if k not in ("audience", "journey")})
    tot = collections.Counter()
    for fam, st in sorted(stats.items()):
        n = sum(st.values())
        tot["n"] += n
        tot["ok"] += st["ok"]
        if fam == "HOLDOUT":  # aggregate only: holdout details must not drive pattern changes
            print("%-30s %3d/%3d" % (fam, st["ok"], n))
        elif st["ok"] != n:
            print("%-30s %3d/%3d  %s" % (fam, st["ok"], n, dict((k, v) for k, v in st.items() if k != "ok")))
    print("situation match: %d/%d" % (tot["ok"], tot["n"]))


if __name__ == "__main__":
    main()

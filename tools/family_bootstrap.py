"""Family-level (cluster) bootstrap 95% CI for safe-action pass on dev, next to the grader's case-level CI.

DIAGNOSTIC: reads the dev-only field scenario_family to group cases. The assistant never sees it.

The grader (dsakit.scoring.bootstrap_ci) resamples the 588 cases independently (1,000 draws, seed 7).
Cases in one family are near-paraphrases of one scenario, so they pass or fail together; resampling
whole families (49 of them, with replacement, 2,000 draws, fixed seed) gives a CI that reflects how many
independent scenarios we really have.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/family_bootstrap.py --submission analysis/runs/<stamp>_dev.jsonl
"""
import sys

sys.dont_write_bytecode = True

import argparse
import os
import random
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import kit  # noqa: E402
from dsakit import scoring  # noqa: E402  (vendor kit, read-only)


def percentile(xs, q):
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", required=True)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261107)
    args = ap.parse_args()

    cases = kit.load_dev_cases()
    subs = {s["case_id"]: s for s in kit.load_jsonl(args.submission)}
    interv = scoring._intervention()
    rows = {c["case_id"]: scoring.score_case(c, subs.get(c["case_id"]), interv) for c in cases}

    fam = defaultdict(lambda: [0, 0])  # family -> [passed, n]
    for c in cases:
        f = fam[c["scenario_family"]]
        f[0] += 1 if rows[c["case_id"]].get("passed") else 0
        f[1] += 1
    fams = sorted(fam)
    point = 100 * sum(fam[f][0] for f in fams) / sum(fam[f][1] for f in fams)

    rnd = random.Random(args.seed)
    stats = []
    for _ in range(args.draws):
        pick = [fams[rnd.randrange(len(fams))] for _ in fams]
        p = sum(fam[f][0] for f in pick)
        n = sum(fam[f][1] for f in pick)
        stats.append(100 * p / n)
    lo, hi = percentile(stats, 0.025), percentile(stats, 0.975)

    case_rows = list(rows.values())
    clo, chi = scoring.bootstrap_ci(case_rows, lambda s: 100 * sum(1 for r in s if r.get("passed")) / len(s))

    print("submission: %s" % os.path.relpath(args.submission, ROOT))
    print("cases %d, families %d" % (len(cases), len(fams)))
    print("safe-action pass (point)                     %.1f %%" % point)
    print("grader case-level CI  (588 cases, 1000 draws, seed 7)        %.1f-%.1f" % (clo, chi))
    print("family-level CI       (%d families, %d draws, seed %d)  %.1f-%.1f" % (len(fams), args.draws, args.seed, lo, hi))
    imperfect = [(f, fam[f][0], fam[f][1]) for f in fams if fam[f][0] < fam[f][1]]
    print("families below 100 %%: %d" % len(imperfect))
    for f, p, n in imperfect:
        print("  %-30s %2d/%2d" % (f, p, n))


if __name__ == "__main__":
    main()

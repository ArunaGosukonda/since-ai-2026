"""Deterministic holdout of 9 dev families (diagnostic tooling; reads dev-only fields).

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/holdout.py      # print + write analysis/holdout.txt

Selection (no randomness, no tuning):
  1. order every dev family by sha256("dsa-holdout-v1:" + family);
  2. take the first 2 twin families in that order (twin = ground_truth.twin_group set);
  3. take the first 2 benign families (every case is_benign_control);
  4. for every journey not yet covered, take its first family;
  5. fill up to 9 in hash order.
The keyword patterns in dsa/facts_keyword.py were written after this list was fixed and
must never be tuned on these families' cases.
"""
import sys

sys.dont_write_bytecode = True

import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import kit  # noqa: E402

SALT = "dsa-holdout-v1:"
N = 9
HOLDOUT_TXT = os.path.join(ROOT, "analysis", "holdout.txt")


def family_table(cases):
    """{family: {"journey", "twin", "benign", "cases"}} from DEV-ONLY fields (diagnostic)."""
    out = {}
    for c in cases:
        fam = c["scenario_family"]
        gt = c["ground_truth"]
        row = out.setdefault(fam, {"journey": c["journey"], "twin": False, "benign": True, "cases": 0})
        row["twin"] |= bool(gt.get("twin_group"))
        row["benign"] &= bool(gt["is_benign_control"])
        row["cases"] += 1
    return out


def select(cases):
    table = family_table(cases)
    order = sorted(table, key=lambda f: hashlib.sha256((SALT + f).encode()).hexdigest())
    picked = []

    def take(pred, k):
        for f in order:
            if k <= 0:
                return
            if f not in picked and pred(f):
                picked.append(f)
                k -= 1

    take(lambda f: table[f]["twin"], 2)
    take(lambda f: table[f]["benign"], 2)
    for j in sorted({r["journey"] for r in table.values()}):
        if not any(table[f]["journey"] == j for f in picked):
            take(lambda f, j=j: table[f]["journey"] == j, 1)
    take(lambda f: True, N - len(picked))
    return picked, table


def load_holdout():
    with open(HOLDOUT_TXT, encoding="utf-8") as f:
        return [ln.split()[0] for ln in f if ln.strip() and not ln.startswith("#")]


def write(picked, table):
    os.makedirs(os.path.dirname(HOLDOUT_TXT), exist_ok=True)
    with open(HOLDOUT_TXT, "w", encoding="utf-8") as f:
        f.write("# Holdout dev families, chosen by tools/holdout.py (sha256 order, constraints: all 5 journeys,\n")
        f.write("# >=2 twin families, >=2 benign families). Keyword patterns must not be tuned on these.\n")
        f.write("# family  journey  twin  benign  cases\n")
        for fam in picked:
            r = table[fam]
            f.write("%s %s twin=%s benign=%s cases=%d\n" % (fam, r["journey"], r["twin"], r["benign"], r["cases"]))


def main():
    picked, table = select(kit.load_dev_cases())
    write(picked, table)
    n = sum(table[f]["cases"] for f in picked)
    print("holdout: %d families, %d cases -> %s" % (len(picked), n, os.path.relpath(HOLDOUT_TXT, ROOT)))
    for f in picked:
        print("  ", f, table[f])


if __name__ == "__main__":
    main()

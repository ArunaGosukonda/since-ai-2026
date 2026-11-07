"""Sanity checks for analysis/ml/{dev,test}.csv (written by tools/export_ml_dataset.py).

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_ml_dataset.py

Diagnostic tool: reads dev ground truth via the exported label columns.
Prints PASS / WARN / FAIL / INFO lines. Exit 1 if any FAIL.

Checks:
  1. row counts match the kit's dev cases and test inputs
  2. IDs unique within each split, id == case_id, dev and test IDs disjoint,
     and the ID sets equal the kit's case IDs
  3. no label or dev-only column in test.csv
  4. no unknown / empty situation_id in dev; every label is a contracts situation
  5. rows and families per situation (WARN if a situation has < 3 families)
  6. dev-vs-test gap in unknown/empty rate per feature column (WARN if > 20 pp)
  7. keyword_situation_id vs situation_id agreement on dev (INFO)
"""
import collections
import csv
import os
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import kit  # noqa: E402

ML_DIR = os.path.join(ROOT, "analysis", "ml")
LABEL_COLS = ["situation_id", "family", "branch"]
DEV_ONLY_FIELDS = [
    "ground_truth", "simulation", "scenario_family", "title", "tags",
    "difficulty", "holdout_family",
]
MIN_FAMILIES = 3
GAP_PP = 20.0
NON_FEATURE_COLS = {"id", "case_id", "raw_user_text", "opening_message"} | set(LABEL_COLS)

counts = collections.Counter()


def report(level, msg):
    counts[level] += 1
    print(f"[{level}] {msg}")


def load(name):
    with open(os.path.join(ML_DIR, name), newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def missing(col, v):
    """unknown/empty: kw_* and keyword_situation_id use 'unknown'; other columns use ''."""
    return v == "" or v == "unknown"


def main():
    dev_hdr, dev = load("dev.csv")
    test_hdr, test = load("test.csv")
    kit_dev = [c["case_id"] for c in kit.load_dev_cases()]
    kit_test = [c["case_id"] for c in kit.load_test_inputs()]

    # 1. counts
    print("== 1. counts")
    for name, rows, ref in (("dev", dev, kit_dev), ("test", test, kit_test)):
        lvl = "PASS" if len(rows) == len(ref) else "FAIL"
        report(lvl, f"{name}.csv rows={len(rows)} kit={len(ref)}")

    # 2. IDs
    print("== 2. IDs")
    for name, rows, ref in (("dev", dev, kit_dev), ("test", test, kit_test)):
        ids = [r["id"] for r in rows]
        dup = [i for i, n in collections.Counter(ids).items() if n > 1]
        report("FAIL" if dup else "PASS", f"{name} unique ids ({len(set(ids))}); duplicates={dup[:5]}")
        bad = [r["id"] for r in rows if r["id"] != r["case_id"]]
        report("FAIL" if bad else "PASS", f"{name} id == case_id; mismatches={bad[:5]}")
        report("PASS" if set(ids) == set(ref) else "FAIL", f"{name} ids == kit case_ids")
    overlap = {r["id"] for r in dev} & {r["id"] for r in test}
    report("FAIL" if overlap else "PASS", f"dev/test ids disjoint; overlap={sorted(overlap)[:5]}")

    # 3. no labels in test
    print("== 3. no labels in test")
    leaked = [c for c in test_hdr if c in LABEL_COLS or c in DEV_ONLY_FIELDS]
    report("FAIL" if leaked else "PASS", f"test.csv has no label/dev-only columns; found={leaked}")
    missing_lbl = [c for c in LABEL_COLS if c not in dev_hdr]
    report("FAIL" if missing_lbl else "PASS", f"dev.csv has label columns; missing={missing_lbl}")
    extra = set(dev_hdr) - set(test_hdr) - set(LABEL_COLS)
    report("FAIL" if extra else "PASS", f"dev features == test features; dev-only extras={sorted(extra)}")

    # 4. no unknown labels
    print("== 4. labels")
    valid = {s["id"] for s in kit.contract_yaml("situations.yaml")["situations"]}
    bad = [(r["id"], r["situation_id"]) for r in dev if r["situation_id"] not in valid]
    report("FAIL" if bad else "PASS", f"every dev situation_id in contracts ({len(valid)} ids); bad={bad[:5]}")
    nofam = [r["id"] for r in dev if not r["family"]]
    report("FAIL" if nofam else "PASS", f"every dev row has a family; empty={nofam[:5]}")

    # 5. rows and families per situation
    print("== 5. rows and families per situation")
    rows_by = collections.Counter(r["situation_id"] for r in dev)
    fams_by = collections.defaultdict(set)
    for r in dev:
        fams_by[r["situation_id"]].add(r["family"])
    print(f"   {'sit':<5}{'rows':>6}{'families':>10}")
    for s in sorted(valid):
        print(f"   {s:<5}{rows_by.get(s, 0):>6}{len(fams_by.get(s, ())):>10}")
    for s in sorted(valid):
        n = len(fams_by.get(s, ()))
        if n < MIN_FAMILIES:
            report("WARN", f"{s}: {n} famil{'y' if n == 1 else 'ies'} in dev "
                           f"(< {MIN_FAMILIES}; GroupKFold can't really check it): {sorted(fams_by.get(s, ()))}")
    print(f"   total families: {len({r['family'] for r in dev})}")

    # 6. dev-vs-test unknown/empty gap
    print(f"== 6. dev-vs-test unknown/empty gap (WARN > {GAP_PP:.0f} pp)")
    feats = [c for c in test_hdr if c not in NON_FEATURE_COLS]
    n_gap = 0
    for c in feats:
        pd = 100.0 * sum(missing(c, r[c]) for r in dev) / len(dev)
        pt = 100.0 * sum(missing(c, r[c]) for r in test) / len(test)
        if abs(pd - pt) > GAP_PP:
            n_gap += 1
            report("WARN", f"{c}: dev {pd:.1f}% vs test {pt:.1f}% unknown/empty ({pt - pd:+.1f} pp)")
    if not n_gap:
        report("PASS", f"no feature column ({len(feats)} checked) differs by > {GAP_PP:.0f} pp")

    # 7. keyword vs label agreement
    print("== 7. keyword_situation_id vs situation_id (dev)")
    agree = sum(r["keyword_situation_id"] == r["situation_id"] for r in dev)
    report("INFO", f"overall agreement {agree}/{len(dev)} = {100.0 * agree / len(dev):.1f}%")
    unk = sum(r["keyword_situation_id"] == "unknown" for r in dev + test)
    report("FAIL" if unk else "PASS", f"keyword_situation_id never 'unknown' (policy errors); count={unk}")
    print(f"   {'sit':<5}{'rows':>6}{'kw_ok':>7}{'recall':>8}   top confusions")
    for s in sorted(valid):
        rs = [r for r in dev if r["situation_id"] == s]
        if not rs:
            continue
        ok = sum(r["keyword_situation_id"] == s for r in rs)
        conf = collections.Counter(r["keyword_situation_id"] for r in rs if r["keyword_situation_id"] != s)
        top = ", ".join(f"{k}x{v}" for k, v in conf.most_common(3))
        print(f"   {s:<5}{len(rs):>6}{ok:>7}{100.0 * ok / len(rs):>7.0f}%   {top}")
    kw_test = collections.Counter(r["keyword_situation_id"] for r in test)
    print("   test keyword_situation_id distribution: "
          + ", ".join(f"{k}:{v}" for k, v in sorted(kw_test.items())))

    print(f"\nSUMMARY: PASS={counts['PASS']} WARN={counts['WARN']} FAIL={counts['FAIL']} INFO={counts['INFO']}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())

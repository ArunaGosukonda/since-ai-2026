"""Write analysis/review/review_sample.csv: 30 dev answers for manual review (RESULTS.md §7.2).

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/review_sample.py [RUN.jsonl]

2 answers per journey x language stratum (5 x 3 = 15 strata), strata in sorted order, drawn with
random.Random(20261107).sample. RUN.jsonl defaults to the newest analysis/runs/*_dev.jsonl. Columns
follow the vendor templates/human_review_form.csv (';'-separated), judgement columns left empty.
Reads no dev-only field (journey, language and opening_message are case inputs).
"""
import sys

sys.dont_write_bytecode = True

import collections
import csv
import glob
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import kit  # noqa: E402

SEED = 20261107
PER_STRATUM = 2
OUT = os.path.join(ROOT, "analysis", "review", "review_sample.csv")
FORM = os.path.join(ROOT, "instructions", "DNA_Digital_Security_Assistant_SimSet_v2.0.1", "templates",
                    "human_review_form.csv")


def main(argv):
    run = argv[0] if argv else sorted(glob.glob(os.path.join(ROOT, "analysis", "runs", "*_dev.jsonl")))[-1]
    with open(run, encoding="utf-8") as f:
        answers = {r["case_id"]: r for r in map(json.loads, f) if r}
    cases = kit.load_dev_cases()
    strata = collections.defaultdict(list)
    for c in cases:
        strata[(c["journey"], c["language"])].append(c["case_id"])
    rng = random.Random(SEED)
    picked = []
    for key in sorted(strata):
        picked += rng.sample(strata[key], PER_STRATUM)
    by_id = {c["case_id"]: c for c in cases}
    with open(FORM, encoding="utf-8") as f:
        header = next(csv.reader(f, delimiter=";"))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        for cid in sorted(picked):
            c = by_id[cid]
            w.writerow([cid, c["language"], c["opening_message"], answers[cid]["advice_text"]]
                       + [""] * (len(header) - 4))
    print("wrote %s: %d answers from %s" % (os.path.relpath(OUT, ROOT), len(picked), os.path.relpath(run, ROOT)))


if __name__ == "__main__":
    main(sys.argv[1:])

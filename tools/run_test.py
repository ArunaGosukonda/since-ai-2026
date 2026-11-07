"""Answer the 335 test inputs and check the submission file.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/run_test.py [--llm]

--llm: facts from dsa/facts_llm.py. Answers come from analysis/llm_cache/ when cached, so the file
reproduces without GEMINI_API_KEY; a cache miss without the key stops the run (LLMUnavailable).

Writes test_predictions.jsonl at the repo root (trace stripped, vendor submission schema) and
analysis/runs/<timestamp>_test.trace.jsonl, then runs the vendor tools/validate.py --submission.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import json
import os
import subprocess
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import facts_keyword, facts_llm, kit, pipeline  # noqa: E402

OUT = os.path.join(ROOT, "test_predictions.jsonl")
RUNS = os.path.join(ROOT, "analysis", "runs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="Gemini gap-filling facts (dsa/facts_llm.py)")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(RUNS, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S") + ("_llm" if args.llm else "")
    cases = kit.load_test_inputs()
    if args.llm:
        facts_llm.prefetch(cases)
        decisions = [pipeline.assess(c, extract=facts_llm.extract_facts, model=facts_llm.MODEL) for c in cases]
    else:
        decisions = [pipeline.assess(c, extract=facts_keyword.extract_facts) for c in cases]
    with open(OUT, "w", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps(pipeline.strip_trace(d), ensure_ascii=False) + "\n")
    with open(os.path.join(RUNS, "%s_test.trace.jsonl" % stamp), "w", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps({"case_id": d["case_id"], "trace": d["trace"]}, ensure_ascii=False) + "\n")
    print("wrote %s: %d lines in %.1f s%s" % (os.path.relpath(OUT, ROOT), len(decisions), time.time() - t0,
                                              (" | llm %s, cache %s" % (facts_llm.MODEL, facts_llm.STATS)) if args.llm else ""))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", os.path.join(kit.KIT, "tools", "validate.py"), "--submission", OUT],
                          capture_output=True, text=True, env=env, cwd=ROOT)
    print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip())
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()

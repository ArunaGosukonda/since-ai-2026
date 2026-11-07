"""Run the assistant on all dev cases and score them with the official evaluator.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/run_dev.py [--llm]

--llm: facts from dsa/facts_llm.py (keyword facts + Gemini gap-filling, cached in analysis/llm_cache/).
Also writes <timestamp>_dev_llm.llm.jsonl: per case, the facts the LLM filled (with evidence) and the
proposals it dropped (with the reason).

Writes analysis/runs/<timestamp>_dev.jsonl (submission lines, trace stripped),
<timestamp>_dev.trace.jsonl (case_id + trace) and <timestamp>_dev.eval.txt (evaluator stdout plus
the holdout lines). The holdout lines are a DIAGNOSTIC: they read the dev-only field scenario_family
to split the cases by the families listed in analysis/holdout.txt, which this script only reads (it is
written by tools/holdout.py alone); the assistant never sees it.
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
sys.path.insert(0, os.path.join(ROOT, "tools"))

import holdout  # noqa: E402
from dsa import facts_keyword, facts_llm, kit, pipeline  # noqa: E402
from dsakit import scoring  # noqa: E402  (vendor kit, read-only)

RUNS = os.path.join(ROOT, "analysis", "runs")


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def holdout_lines(cases, subs):
    """DIAGNOSTIC (dev-only fields): pass rate and decisive-question rate on the holdout families.
    Reads the fixed list in analysis/holdout.txt; never rewrites it (only tools/holdout.py does)."""
    picked = holdout.load_holdout()
    hold = set(picked)
    by_id = {s["case_id"]: s for s in subs}
    interv = scoring._intervention()
    rows = {c["case_id"]: scoring.score_case(c, by_id.get(c["case_id"]), interv) for c in cases}
    h = [rows[c["case_id"]] for c in cases if c["scenario_family"] in hold]
    s = [rows[c["case_id"]] for c in cases if c["scenario_family"] not in hold]
    ha, sa = scoring.aggregate(h)["headline"], scoring.aggregate(s)["headline"]
    n_must_h = sum(1 for r in h if r.get("asked_ok") is not None)
    n_must_s = sum(1 for r in s if r.get("asked_ok") is not None)
    return [
        "HOLDOUT  (%d families, %d cases; analysis/holdout.txt): safe-action pass %.1f %% | c3 asked decisive question %.1f %% (n=%d) | false alarms on benign %s %%"
        % (len(picked), len(h), ha["safe_action_pass_pct"], ha["asked_decisive_question_pct"] or 0.0, n_must_h,
           ha["false_alarm_rate_on_benign_pct"]),
        "SEEN     (%d families, %d cases): safe-action pass %.1f %% | c3 asked decisive question %.1f %% (n=%d) | false alarms on benign %s %%"
        % (len({c["scenario_family"] for c in cases}) - len(picked), len(s), sa["safe_action_pass_pct"],
           sa["asked_decisive_question_pct"] or 0.0, n_must_s, sa["false_alarm_rate_on_benign_pct"]),
    ]


def assess_all(cases, llm):
    """-> decisions. llm: fill the cache in parallel first, then assess serially (deterministic order)."""
    if not llm:
        return [pipeline.assess(c, extract=facts_keyword.extract_facts) for c in cases]
    facts_llm.prefetch(cases)
    return [pipeline.assess(c, extract=facts_llm.extract_facts, model=facts_llm.MODEL) for c in cases]


def llm_rows(decisions):
    rows = []
    for d in decisions:
        info = facts_llm.LAST.get(d["case_id"], {})
        rows.append({"case_id": d["case_id"], "cache": info.get("cache"), "filled": info.get("filled", {}),
                     "dropped": [{"fact": f, "reason": r} for f, r in info.get("dropped", [])]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="Gemini gap-filling facts (dsa/facts_llm.py)")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(RUNS, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S") + ("_llm" if args.llm else "")
    cases = kit.load_dev_cases()
    decisions = assess_all(cases, args.llm)
    subs = [pipeline.strip_trace(d) for d in decisions]
    sub_path = os.path.join(RUNS, "%s_dev.jsonl" % stamp)
    write_jsonl(sub_path, subs)
    write_jsonl(os.path.join(RUNS, "%s_dev.trace.jsonl" % stamp), [{"case_id": d["case_id"], "trace": d["trace"]} for d in decisions])
    if args.llm:
        write_jsonl(os.path.join(RUNS, "%s_dev.llm.jsonl" % stamp), llm_rows(decisions))
    t_assess = time.time() - t0

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-B", os.path.join(kit.KIT, "eval", "evaluate.py"), "--cases", kit.DEV_CASES,
                           "--submission", sub_path], capture_output=True, text=True, env=env, cwd=ROOT)
    out = proc.stdout + (("\nSTDERR:\n" + proc.stderr) if proc.stderr else "")
    lines = holdout_lines(cases, subs)
    elapsed = time.time() - t0
    report = out.rstrip() + "\n\n" + "\n".join(lines) + "\n\n%d dev cases, assess %.1f s, total %.1f s%s\n" % (
        len(cases), t_assess, elapsed, (" | llm %s, cache %s" % (facts_llm.MODEL, facts_llm.STATS)) if args.llm else "")
    with open(os.path.join(RUNS, "%s_dev.eval.txt" % stamp), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print("wrote", os.path.relpath(sub_path, ROOT), "(+ .trace.jsonl, .eval.txt)")
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()

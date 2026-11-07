"""Score situation predictions through the DNA DSA pipeline with official evaluator.

Usage:
    # Score custom ML predictions from CSV
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/score_situations.py --pred analysis/ml/dev_preds.csv

    # Score Oracle ceiling (DIAGNOSTIC: reads dev-only scenario_family / ground_truth.branch)
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/score_situations.py --oracle

    # Score Keyword baseline (rule-based pipeline)
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/score_situations.py --keyword

    # Compare predictions against both baselines in one command
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/score_situations.py --pred analysis/ml/dev_preds.csv --oracle --keyword

Input CSV format:
    Accepts CSV with headers (id or case_id, predicted_situation_id or situation_id):
        id,predicted_situation_id
        DSA-D-0001,S02
        DSA-D-0002,S01
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import kit, pipeline, policy  # noqa: E402
from dsakit import scoring  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
import contracts_common  # noqa: E402  (DIAGNOSTIC helpers over dev-only fields; oracle mode only)

RUNS_DIR = os.path.join(ROOT, "analysis", "runs")
SITUATION_REGEX = re.compile(r"^S(0[1-9]|1[0-9])$", re.IGNORECASE)


# ----------------------------------------------------------------------------- CSV Reader
def load_predictions_csv(csv_path):
    """Load predictions from CSV. Supports varied column names:
    (id / case_id) and (predicted_situation_id / situation_id / situation / pred).
    Returns dict: case_id -> normalised situation_id.
    """
    if not os.path.isfile(csv_path):
        sys.exit(f"Predictions file not found: {csv_path}")

    preds = {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            first_row = next(reader)
        except StopIteration:
            sys.exit(f"Predictions file is empty: {csv_path}")

        # Check if first row is header
        lower_row = [c.strip().lower() for c in first_row]
        id_col = -1
        pred_col = -1

        for i, col in enumerate(lower_row):
            if col in ("id", "case_id", "case", "caseid"):
                id_col = i
            elif col in ("predicted_situation_id", "situation_id", "situation", "pred", "prediction", "predicted"):
                pred_col = i

        rows_to_process = []
        if id_col != -1 and pred_col != -1:
            # First row was a recognised header
            rows_to_process = reader
        elif len(first_row) >= 2:
            # Assume col 0 is id, col 1 is prediction
            id_col = 0
            pred_col = 1
            # Check if first row looks like data
            val = first_row[pred_col].strip().upper()
            if SITUATION_REGEX.match(val):
                preds[first_row[id_col].strip()] = val
            rows_to_process = reader
        else:
            sys.exit(f"Could not find ID and prediction columns in {csv_path}")

        for line_num, row in enumerate(rows_to_process, start=2):
            if not row or len(row) <= max(id_col, pred_col):
                continue
            cid = row[id_col].strip()
            sid = row[pred_col].strip().upper()
            if not cid:
                continue
            if not SITUATION_REGEX.match(sid):
                print(f"Warning: line {line_num}: invalid situation '{sid}' for case {cid}")
            preds[cid] = sid

    return preds


def load_family_map():
    """contracts/family_to_situation.csv -> {(family, branch): situation_id}."""
    path = os.path.join(kit.CONTRACTS, "family_to_situation.csv")
    fmap = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fmap[(row["family"], row["branch"])] = row["situation_id"]
    return fmap


# ----------------------------------------------------------------------------- Pipeline forcing
def assess_forced(case, forced_sid):
    """Run the normal assistant with its base situation overridden (pipeline.assess(situation_override=...)).
    Everything after the match is the production path: decisive questions, the move to the riskier branch,
    the escalation of the final row, consent planning, compose and validate. An ID that is not a situation
    falls back to the normal match."""
    sid = forced_sid if SITUATION_REGEX.match(forced_sid or "") else None
    if sid is not None:
        sid = sid.upper()
        if sid not in policy.table()[0]:
            sid = None
    return pipeline.assess(case, situation_override=sid)


def generate_submissions(cases, mode, preds_map=None, family_map=None, fill_keyword=False):
    """Generate pipeline decisions for cases under the specified mode:
    'pred': use preds_map (and optionally fill unpredicted with keyword baseline if fill_keyword=True)
    'oracle': use ground truth situation_id from family_map (twins: the riskier branch's, as in single-turn)
    'keyword': run default pipeline
    """
    subs = []
    risky = contracts_common.riskier_branches(cases) if mode == "oracle" else {}
    for c in cases:
        cid = c["case_id"]
        if mode == "keyword":
            d = pipeline.assess(c)
            subs.append(pipeline.strip_trace(d))
        elif mode == "oracle":
            # DIAGNOSTIC (reads dev-only fields scenario_family and ground_truth.branch / twin_group): the
            # oracle ceiling. Never used by the assistant or for submissions. A twin is answered from its
            # riskier branch's situation, as single-turn does (contracts/CONFLICTS.md, tools/check_contracts.py).
            fam = c.get("scenario_family", "")
            branch = c.get("ground_truth", {}).get("branch", "main")
            if contracts_common.is_twin(c):
                branch = risky[fam]
            oracle_sid = family_map.get((fam, branch), "S03")
            d = assess_forced(c, oracle_sid)
            subs.append(pipeline.strip_trace(d))
        elif mode == "pred":
            if cid in preds_map:
                forced_sid = preds_map[cid]
                d = assess_forced(c, forced_sid)
                subs.append(pipeline.strip_trace(d))
            elif fill_keyword:
                d = pipeline.assess(c)
                subs.append(pipeline.strip_trace(d))
            # If not in preds_map and not fill_keyword, omitted so evaluator tracks missing
    return subs


def run_official_evaluator(cases_path, sub_path, no_ci=False, failures=12, json_out=False):
    """Invoke instructions/DNA_Digital_Security_Assistant_SimSet_v2.0.1/eval/evaluate.py."""
    eval_script = os.path.join(kit.KIT, "eval", "evaluate.py")
    cmd = [
        sys.executable,
        "-B",
        eval_script,
        "--cases",
        cases_path,
        "--submission",
        sub_path,
        "--failures",
        str(failures),
    ]
    if no_ci:
        cmd.append("--no-ci")
    if json_out:
        cmd.append("--json")

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT)
    return proc.returncode, proc.stdout, proc.stderr


# ----------------------------------------------------------------------------- Comparison Table
def format_pct(val):
    return "  n/a " if val is None else f"{val:5.1f}%"


def print_comparison_table(results):
    """Print clean summary table comparing all evaluated modes."""
    print("\n" + "=" * 90)
    print("                    SITUATION PREDICTION EVALUATION COMPARISON")
    print("=" * 90)
    print(
        f"{'Mode':<16} {'Safe-Action Pass':<18} {'Weighted Proxy':<16} {'Benign FA Rate':<16} {'Action Exact':<14} {'Cases':<8}"
    )
    print("-" * 90)
    for name, rep in results.items():
        h = rep["headline"]
        p = rep["brief_scorecard_proxy"]
        d = rep["details"]
        pass_pct = format_pct(h["safe_action_pass_pct"])
        proxy = f"{p['weighted_proxy_over_assessed_dimensions']:5.1f}" if p.get("weighted_proxy_over_assessed_dimensions") is not None else "  n/a"
        fa_pct = format_pct(h["false_alarm_rate_on_benign_pct"])
        act_pct = format_pct(d["action_exact_match_pct"])
        cases_scored = rep["cases"] - d["missing_submissions"]
        print(f"{name:<16} {pass_pct:<18} {proxy:<16} {fa_pct:<16} {act_pct:<14} {cases_scored:<8}")
    print("=" * 90 + "\n")


# ----------------------------------------------------------------------------- Main CLI
def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pred",
        help="Path to predictions CSV (columns: id, predicted_situation_id)",
        metavar="CSV_PATH",
    )
    parser.add_argument(
        "--fill-keyword",
        action="store_true",
        help="When scoring a partial predictions CSV, fill missing cases with keyword baseline",
    )
    parser.add_argument(
        "--oracle",
        action="store_true",
        help="Evaluate Oracle ceiling (ground truth situations)",
    )
    parser.add_argument(
        "--keyword",
        action="store_true",
        help="Evaluate Keyword baseline (rule-based pipeline)",
    )
    parser.add_argument(
        "--cases",
        default=kit.DEV_CASES,
        help=f"Path to ground-truth cases JSONL (default: {os.path.relpath(kit.DEV_CASES, ROOT)})",
    )
    parser.add_argument(
        "--out",
        help="Path to save generated submission JSONL",
    )
    parser.add_argument(
        "--no-ci",
        action="store_true",
        help="Skip bootstrap confidence intervals for faster execution",
    )
    parser.add_argument(
        "--failures",
        type=int,
        default=12,
        help="How many failure cases to list in evaluator report",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print evaluator output as JSON",
    )
    args = parser.parse_args()

    # Determine which modes to run
    modes = []
    if args.pred:
        modes.append("pred")
    if args.keyword:
        modes.append("keyword")
    if args.oracle:
        modes.append("oracle")

    if not modes:
        parser.print_help()
        sys.exit("\nError: Please specify at least one mode: --pred <path>, --oracle, or --keyword")

    os.makedirs(RUNS_DIR, exist_ok=True)
    cases = kit.load_jsonl(args.cases)
    family_map = load_family_map()

    preds_map = None
    if "pred" in modes:
        preds_map = load_predictions_csv(args.pred)
        print(f"Loaded {len(preds_map)} predictions from {args.pred}")

    results = {}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for mode in modes:
        label = "Predictions" if mode == "pred" else ("Oracle" if mode == "oracle" else "Keyword")
        print(f"\n>>> Running evaluation for mode: {label} ...")

        subs = generate_submissions(cases, mode, preds_map=preds_map, family_map=family_map, fill_keyword=args.fill_keyword)

        # Determine output submission path
        if args.out and len(modes) == 1:
            sub_path = args.out
        else:
            sub_path = os.path.join(RUNS_DIR, f"{stamp}_{mode}_submission.jsonl")

        with open(sub_path, "w", encoding="utf-8") as f:
            for s in subs:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        # Run official evaluator
        code, stdout, stderr = run_official_evaluator(
            args.cases,
            sub_path,
            no_ci=args.no_ci,
            failures=args.failures,
            json_out=args.json,
        )

        if stderr:
            print(f"Evaluator stderr:\n{stderr}")
        print(stdout)

        # Also store aggregate results for comparison table
        rep, _ = scoring.evaluate(cases, subs, with_ci=False)
        results[label] = rep

    # If multiple modes were evaluated, show comparison table
    if len(modes) > 1 and not args.json:
        print_comparison_table(results)


if __name__ == "__main__":
    main()

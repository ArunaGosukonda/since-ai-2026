"""bin/dsa - command-line interface. Every command prints JSON on stdout
(``--format text`` gives a human-readable table instead).

  bin/dsa facts train [--out PATH]          train the threat -> facts model on all dev cases
  bin/dsa facts eval  [--cv family|random|both]  cross-validate it (facts + lookup-table action)
  bin/dsa assess --request FILE|-           one assessment (contract: schema/assess_*.schema.json)
  bin/dsa assess --case-id ID | --case FILE [--answer topic=value ...] [--flag F ...] [--final]
                                            the same, built from command-line arguments
  bin/dsa knowledge export                  all vocabularies an integrator needs
  bin/dsa policy eval [--mode multi|single] [--families GLOBS] [--jobs N]
                                            simulate conversations on held-out families
  bin/dsa rules check                       how often each safety rule fires on dev
  bin/dsa knowledge check                   validate knowledge/*.yaml
  bin/dsa status [--measure] [--check]      measured performance (MODEL_STATUS.md); --measure re-runs all evals
  bin/dsa model train|eval                  baseline: predict the action directly (for comparison)
"""
import argparse
import json
import os
import sys
import time

from . import knowledge
from .data import VIEWS, load_dev_examples
from .evaluate import cross_validate, summarise
from .model import DEFAULT_PATH, ActionModel
from . import facts_eval
from .facts_model import DEFAULT_PATH as FACTS_PATH, FactModel, build_examples


def _model_kwargs(a):
    return {"target": a.target, "C": a.C, "blocks": tuple(a.blocks.split(",")), "signals_weight": a.signals_weight}


def _add_model_args(p):
    p.add_argument("--target", choices=["acceptable", "primary"], default="acceptable")
    p.add_argument("--C", type=float, default=4.0, help="inverse regularisation strength")
    p.add_argument("--blocks", default="user,artifact,signals", help="feature blocks: user,artifact,signals (and standin: experiment only, uses ground truth)")
    p.add_argument("--signals-weight", type=float, default=0.35)
    p.add_argument("--views", default=",".join(VIEWS), help="case views to train/evaluate on")
    p.add_argument("--format", choices=["json", "text"], default="json")


def cmd_model_train(a):
    t = time.time()
    ex = load_dev_examples(views=tuple(a.views.split(",")))
    model = ActionModel(**_model_kwargs(a)).fit(ex)
    meta = model.save(a.out)
    return {"saved": a.out, "examples": len(ex), "seconds": round(time.time() - t, 1), "meta": meta}


def cmd_model_eval(a):
    ex = load_dev_examples(views=tuple(a.views.split(",")), with_stand_in="standin" in a.blocks)
    out = {"config": _model_kwargs(a) | {"blocks": a.blocks, "views": a.views, "folds": a.folds}, "results": {}}
    for scheme in (["family", "random"] if a.cv == "both" else [a.cv]):
        t = time.time()
        recs = cross_validate(ex, scheme=scheme, n_splits=a.folds, model_kwargs=_model_kwargs(a))
        out["results"][scheme] = summarise(recs) | {"seconds": round(time.time() - t, 1)}
    return out


def _facts_kwargs(a):
    return {"C": a.C, "blocks": tuple(a.blocks.split(",")), "signals_weight": a.signals_weight, "answers_weight": a.answers_weight}


def _add_facts_args(p):
    p.add_argument("--C", type=float, default=2.0, help="inverse regularisation strength")
    p.add_argument("--blocks", default="user,artifact,signals,answers", help="feature blocks: user,artifact,signals,answers")
    p.add_argument("--signals-weight", type=float, default=0.35)
    p.add_argument("--answers-weight", type=float, default=1.0)
    p.add_argument("--partial", type=int, default=2, help="random partial-answer states per case")
    p.add_argument("--format", choices=["json", "text"], default="json")


def cmd_facts_train(a):
    t = time.time()
    ex = build_examples(n_partial=a.partial)
    model = FactModel(**_facts_kwargs(a)).fit(ex)
    meta = model.save(a.out)
    return {"saved": a.out, "examples": len(ex), "seconds": round(time.time() - t, 1), "meta": meta}


def cmd_facts_eval(a):
    ex = build_examples(n_partial=a.partial)
    out = {"config": _facts_kwargs(a) | {"blocks": a.blocks, "partial": a.partial, "folds": a.folds, "threshold": a.threshold, "source": a.source}, "results": {}}
    for scheme in (["family", "random"] if a.cv == "both" else [a.cv]):
        t = time.time()
        recs = facts_eval.cross_validate(ex, scheme=scheme, n_splits=a.folds, model_kwargs=_facts_kwargs(a),
                                         use_model=a.source in ("both", "model"), use_evidence=a.source in ("both", "evidence"),
                                         n_jobs=a.jobs)
        out["results"][scheme] = facts_eval.summarise(recs, a.threshold) | {"seconds": round(time.time() - t, 1)}
    return out


def _user_path(path):
    """Resolve a path the caller typed relative to their cwd (bin/dsa cds to the repo root)."""
    return os.path.join(os.environ.get("DSA_CALLER_CWD", os.getcwd()), path)


def _load_case(a):
    from .data import DEV_CASES, TEST_INPUTS, load_jsonl
    if a.case:
        with (sys.stdin if a.case == "-" else open(_user_path(a.case), encoding="utf-8")) as f:
            return json.load(f)
    for path in (DEV_CASES, TEST_INPUTS):
        for c in load_jsonl(path):
            if c["case_id"] == a.case_id:
                return c
    raise SystemExit(f"case {a.case_id} not found")


def _assessor(path):
    """Load the fact model; train it first if the file does not exist yet
    (takes ~10 s; the model file is not in git)."""
    import os
    from .assess import Assessor
    trained_now = False
    if not os.path.exists(path):
        FactModel().fit(build_examples()).save(path)
        trained_now = True
    model, meta = FactModel.load(path)
    return Assessor(model), {"path": os.path.relpath(path), "trained_at": meta.get("saved_at"), "trained_now": trained_now}


def cmd_assess(a):
    from . import contract
    try:
        if a.request:
            try:
                with (sys.stdin if a.request == "-" else open(_user_path(a.request), encoding="utf-8")) as f:
                    req = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                raise ValueError(f"cannot read request: {e}")
        else:
            case = _load_case(a)
            if a.hide_gated:
                from .data import hide_gated
                case = hide_gated(case)
            bad = [x for x in a.answer if "=" not in x]
            if bad:
                raise ValueError(f"--answer must be topic=value, got {bad}")
            req = {"case": case, "answers": dict(x.split("=", 1) for x in a.answer), "asked": a.asked,
                   "flags": a.flag, "consent_requested": a.consent_requested, "final": a.final}
        r = contract.parse_request(req)
    except ValueError as e:
        return {"schema_version": contract.SCHEMA_VERSION, "error": str(e)}
    assessor, info = _assessor(a.model)
    result = assessor.assess(r["case"], r["answers"], flags=r["flags"], asked=r["asked"],
                             consent_requested=r["consent_requested"], final=r["final"])
    return contract.build_response(result, r["case"], info, debug=a.verbose)


def cmd_knowledge_export(a):
    from . import contract
    return contract.knowledge_export()


def cmd_policy_eval(a):
    from . import policy_eval
    t = time.time()
    families = [f.strip() for f in a.families.split(",")] if a.families else None
    rows = policy_eval.evaluate(mode=a.mode, n_splits=a.folds, use_model=a.source == "both", agent_flags=a.agent_flags,
                                limit_families=families, n_jobs=a.jobs)
    if not rows:
        return {"error": f"no dev case belongs to a family matching {families}"}
    return {"config": {"mode": a.mode, "folds": a.folds, "source": a.source, "agent_flags": a.agent_flags, "families": families},
            "results": {"family": policy_eval.summarise(rows) | {"seconds": round(time.time() - t, 1)}}}


def cmd_status(a):
    from . import status
    return status.measure() if a.measure else status.status()


def cmd_rules_check(a):
    import collections
    from . import rules
    from .assess import Assessor
    from .data import DEV_CASES, load_jsonl, hide_gated
    errors = rules.validate()
    assessor, info = _assessor(a.model)
    labels = knowledge.dev_labels()
    fired, benign_fired = collections.Counter(), collections.Counter()
    fams = collections.defaultdict(set)
    cases = load_jsonl(DEV_CASES)
    for c in cases:
        lab = labels[knowledge.label_key(c)]
        ans = {k: str(v) for k, v in {**(lab.get("stated") or {}), **(lab.get("answers") or {})}.items()}
        d = assessor.assess(c, ans, flags=lab.get("flags") or [], final=True)["decision"]
        for r in d["rules_fired"]:
            fired[r["id"]] += 1
            fams[r["id"]].add(c["scenario_family"])
            if c["ground_truth"]["is_benign_control"]:
                benign_fired[r["id"]] += 1
    spec = rules.load()
    return {"ok": not errors, "errors": errors, **info,
            "note": "fired on dev cases with every labelled answer and agent flag known (model trained on all dev: optimistic)",
            "rules": [{"id": r["id"], "fired": fired[r["id"]], "on_benign": benign_fired[r["id"]],
                       "families": sorted(fams[r["id"]])} for r in spec["rules"]]}


def _text(res):
    """Render an eval result as a compact table."""
    if "results" not in res:
        return json.dumps(res, indent=2, ensure_ascii=False)
    lines = [f"config: {res['config']}"]
    for scheme, r in res["results"].items():
        cols = list(r["overall"])
        head = f"{'':28}" + "".join(f"{c[:12]:>13}" for c in cols)
        lines += ["", f"== {scheme} CV ({r['seconds']}s) =="]
        if "per_fact" in r:
            lines.append(f"{'fact':28}{'positives':>10}{'auc':>8}{'precision':>11}{'recall':>8}")
            for f, m in r["per_fact"].items():
                lines.append(f"{f:28}{m['positives']:>10}{str(m['auc']):>8}{str(m['precision']):>11}{str(m['recall']):>8}")
            lines.append("")
        lines.append(head)
        rows = [("overall", r["overall"])] + [(f"view:{k}", v) for k, v in r["by_view"].items()] \
            + [(f"journey:{k}", v) for k, v in r["by_journey"].items()] + [(f"lang:{k}", v) for k, v in r["by_language"].items()]
        for name, b in rows:
            lines.append(f"{name:28}" + "".join(f"{('-' if b[c] is None else b[c]):>13}" for c in cols))
        if r["worst_families"]:
            lines.append("weakest families:")
            lines += [f"  {w['family']:30} {w['action_ok']:>6}%   wrong picks: {w['top_wrong']}"
                      + (f"   true facts: {w['true_facts']}" if "true_facts" in w else "") for w in r["worst_families"]]
    return "\n".join(lines)


def build_parser():
    p = argparse.ArgumentParser(prog="dsa", description="Digital Security Assistant threat model", epilog="Integrating? Start with INTEGRATION.md at the repo root.")
    sub = p.add_subparsers(dest="group", required=True)
    m = sub.add_parser("model", help="train and evaluate the threat model").add_subparsers(dest="cmd", required=True)

    tr = m.add_parser("train", help="train on all dev cases and save the model")
    _add_model_args(tr)
    tr.add_argument("--out", default=DEFAULT_PATH)
    tr.set_defaults(fn=cmd_model_train)

    ev = m.add_parser("eval", help="cross-validate on dev cases")
    _add_model_args(ev)
    ev.add_argument("--cv", choices=["family", "random", "both"], default="both")
    ev.add_argument("--folds", type=int, default=7)
    ev.set_defaults(fn=cmd_model_eval)

    fm = sub.add_parser("facts", help="the threat -> facts model").add_subparsers(dest="cmd", required=True)
    ft = fm.add_parser("train", help="train on all dev cases and save the model")
    _add_facts_args(ft)
    ft.add_argument("--out", default=FACTS_PATH)
    ft.set_defaults(fn=cmd_facts_train)
    fe = fm.add_parser("eval", help="cross-validate on dev cases")
    _add_facts_args(fe)
    fe.add_argument("--cv", choices=["family", "random", "both"], default="both")
    fe.add_argument("--folds", type=int, default=7)
    fe.add_argument("--threshold", type=float, default=0.5, help="P at which a fact counts as present")
    fe.add_argument("--source", choices=["both", "model", "evidence"], default="both",
                    help="fact probabilities from the ML model, the hand-written evidence, or both")
    fe.add_argument("--jobs", type=int, default=None, help="parallel processes (default: one per fold up to the CPU count; env DSA_JOBS)")
    fe.set_defaults(fn=cmd_facts_eval)

    asx = sub.add_parser("assess", help="assess one case: facts, action, steps, next step")
    src = asx.add_mutually_exclusive_group(required=True)
    src.add_argument("--request", help="JSON request file (schema/assess_request.schema.json), or - for stdin")
    src.add_argument("--case-id", help="a dev or test case id")
    src.add_argument("--case", help="JSON file with a case (test-input format), or - for stdin")
    asx.add_argument("--answer", action="append", default=[], metavar="TOPIC=VALUE", help="a categorical answer (repeatable)")
    asx.add_argument("--flag", action="append", default=[], help="an agent flag from safety_rules.yaml (repeatable)")
    asx.add_argument("--asked", action="append", default=[], metavar="TOPIC", help="a question already asked (repeatable)")
    asx.add_argument("--consent-requested", action="append", default=[], metavar="PATH", help="a signal already requested (repeatable)")
    asx.add_argument("--final", action="store_true", help="no more questions: answer now (single-turn)")
    asx.add_argument("--hide-gated", action="store_true", help="hide consent-gated signals as at the start of a conversation")
    asx.add_argument("--model", default=FACTS_PATH)
    asx.add_argument("--verbose", action="store_true", help="include the evidence trace")
    asx.set_defaults(fn=cmd_assess)

    pol = sub.add_parser("policy", help="the conversation policy").add_subparsers(dest="cmd", required=True)
    pe = pol.add_parser("eval", help="simulate conversations on held-out families")
    pe.add_argument("--mode", choices=["multi", "single"], default="multi")
    pe.add_argument("--folds", type=int, default=7)
    pe.add_argument("--source", choices=["both", "evidence"], default="both")
    pe.add_argument("--agent-flags", action="store_true", help="give the agent the flags labelled in dev_labels.yaml")
    pe.add_argument("--families", help="only these scenario families, comma-separated names or globs, e.g. '*-TWIN,BR-*' "
                                       "(same folds as the full run, so the numbers are comparable)")
    pe.add_argument("--jobs", type=int, default=None, help="parallel processes (default: one per fold up to the CPU count; env DSA_JOBS)")
    pe.add_argument("--format", choices=["json", "text"], default="json")
    pe.set_defaults(fn=cmd_policy_eval)

    ru = sub.add_parser("rules", help="the safety rules").add_subparsers(dest="cmd", required=True)
    rc = ru.add_parser("check", help="validate safety_rules.yaml and count how often each rule fires on dev")
    rc.add_argument("--model", default=FACTS_PATH)
    rc.add_argument("--format", choices=["json", "text"], default="json")
    rc.set_defaults(fn=cmd_rules_check)

    k = sub.add_parser("knowledge", help="the question/fact/label files in knowledge/").add_subparsers(dest="cmd", required=True)
    kc = k.add_parser("check", help="validate knowledge files against each other, the dataset and the scorer")
    kc.add_argument("--format", choices=["json", "text"], default="json")
    kc.set_defaults(fn=lambda a: knowledge.check())
    kx = k.add_parser("export", help="all closed vocabularies (actions, questions, flags, steps, facts) as JSON")
    kx.set_defaults(fn=cmd_knowledge_export)

    st = sub.add_parser("status", help="measured performance in MODEL_STATUS.md and whether it is stale")
    st.add_argument("--measure", action="store_true", help="re-run every evaluation (~5-10 min) and rewrite the header")
    st.add_argument("--check", action="store_true", help="exit 1 if the numbers are stale (decision code changed since)")
    st.set_defaults(fn=cmd_status)

    return p


def commands(parser=None):
    """Every runnable command as 'bin/dsa group [cmd]' (used to keep AGENTS.md complete)."""
    parser = parser or build_parser()
    out = []
    for action in parser._subparsers._group_actions:
        for name, sp in action.choices.items():
            subs = [a for a in sp._actions if isinstance(a, argparse._SubParsersAction)]
            out += [f"bin/dsa {name} {c}" for c in subs[0].choices] if subs else [f"bin/dsa {name}"]
    return out


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    res = a.fn(a)
    print(_text(res) if getattr(a, "format", "json") == "text" else json.dumps(res, ensure_ascii=False, indent=2))
    if isinstance(res, dict) and "error" in res:
        return 2
    if getattr(a, "check", False) and res.get("stale"):
        return 1


if __name__ == "__main__":
    sys.exit(main())

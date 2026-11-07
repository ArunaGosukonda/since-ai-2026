"""End-to-end evaluation of the assessment loop on dev cases.

For each held-out case a conversation is simulated: the assessor picks the
next step; the simulated user answers a question with the labelled answer
for that topic (knowledge/dev_labels.yaml), or "unsure" when the case has no
answer for it, and grants or refuses consent as the case's consent_policy
says. Then the final decision is scored like the official scorer does
(dsakit/scoring.py): acceptable action, risk within one level, handoff when
required, decisive question asked, benign false alarms, unnecessary
questions.

  single   no questions: one assessment with final=True (single-turn answer;
           the open question is reported as the question to ask)
  multi    conversation of up to policy.max_questions questions

The ML model is retrained per fold on the training families only.
"""
import collections
import copy
import fnmatch

from . import knowledge
from .assess import Assessor
from .data import DEV_CASES, INTERVENTION, RISK_LEVELS, hide_gated, labels_for, load_jsonl, opening_is_descriptive
from .evaluate import _rate
from .facts_model import FactModel, build_examples
from .parallel import map_folds
from sklearn.model_selection import GroupKFold

import numpy as np


def _reveal(seen, case, paths):
    for path in paths:
        *parents, leaf = path.split(".")
        src, dst = case["signals"], seen["signals"]
        for p in parents:
            src, dst = (src or {}).get(p), (dst or {}).get(p)
        if isinstance(src, dict) and isinstance(dst, dict) and leaf in src:
            dst[leaf] = copy.deepcopy(src[leaf])


def simulate(assessor, case, label, mode="multi", flags=()):
    answers_true = {k: str(v) for k, v in (label.get("answers") or {}).items()}
    stated = {k: str(v) for k, v in (label.get("stated") or {}).items()} if opening_is_descriptive(case["opening_message"]) else {}
    answers, asked, consent_req, granted = dict(stated), [], [], []
    seen = hide_gated(case)
    trace = []
    if mode == "multi":
        for _ in range(8):
            r = assessor.assess(seen, answers, flags=flags, asked=asked, consent_requested=consent_req)
            nx = r["next"]
            if nx["type"] == "consent":
                consent_req += nx["fields"]
                if case["simulation"]["consent_policy"] == "grant":
                    granted += nx["fields"]
                    _reveal(seen, case, nx["fields"])
                trace.append(("consent", nx["fields"]))
            elif nx["type"] == "question":
                asked.append(nx["topic"])
                answers[nx["topic"]] = answers_true.get(nx["topic"], "unsure")
                trace.append(("ask", nx["topic"], answers[nx["topic"]]))
            else:
                break
    final = assessor.assess(seen, answers, flags=flags, asked=asked, consent_requested=consent_req, final=True)
    if mode == "single" and "open_question" in final:
        asked = [final["open_question"]["topic"]]
    return {"decision": final["decision"], "asked": asked, "answers": answers, "consent_requested": consent_req,
            "granted": granted, "trace": trace}


def score(case, sim, mode):
    gt = case["ground_truth"]
    d = sim["decision"]
    twin = bool(gt.get("twin_group"))
    decisive = any(sim["answers"].get(t) not in (None, "unsure") for t in gt["must_ask_topics"])
    twin_single = twin and (mode == "single" or not decisive)
    acceptable, want = labels_for(case, facts_known=not twin_single)
    got = d["action"]
    ok = got in acceptable
    rg = RISK_LEVELS.index(d["risk_level"])
    if twin_single:
        lo, hi = (RISK_LEVELS.index(x) for x in gt["single_turn"]["risk_range"])
        risk_ok = lo - 1 <= rg <= hi + 1
        esc_expected = bool(gt["single_turn"].get("escalation_required"))
    else:
        risk_ok = abs(rg - RISK_LEVELS.index(gt["risk_level"])) <= 1
        esc_expected = bool(gt["escalation"]["required"])
    esc_given = d["escalation"]["required"]
    must = set(gt["must_ask_topics"])
    asked = set(sim["asked"])
    asked_ok = bool(must & asked) if must else None
    benign_fa = (not ok or esc_given or rg >= 2) if gt["is_benign_control"] else None
    return {
        "action_ok": ok, "under": (not ok) and INTERVENTION[got] < INTERVENTION[want],
        "over": (not ok) and INTERVENTION[got] > INTERVENTION[want],
        "risk_ok": risk_ok, "esc_expected": esc_expected, "esc_given": esc_given,
        "asked_ok": asked_ok, "benign_fa": benign_fa,
        "n_questions": len(sim["asked"]), "unnecessary": len(asked - set(gt["relevant_topics"])),
        "passed": ok and risk_ok and not (esc_expected and not esc_given) and asked_ok is not False,
    }


def _fold(train, held, mode, use_model, model_kwargs, agent_flags):
    labels = knowledge.dev_labels()
    model = FactModel(**(model_kwargs or {})).fit(build_examples(train)) if use_model else None
    assessor = Assessor(model)
    rows = []
    for c in held:
        lab = labels[knowledge.label_key(c)]
        sim = simulate(assessor, c, lab, mode, flags=tuple(lab.get("flags") or []) if agent_flags else ())
        rows.append({"case": c, "sim": sim, "score": score(c, sim, mode)})
    return rows


def matches_families(family, patterns):
    return any(fnmatch.fnmatchcase(family, p) for p in patterns)


def evaluate(mode="multi", n_splits=7, use_model=True, model_kwargs=None, limit_families=None, agent_flags=False,
             n_jobs=None):
    """agent_flags: give the simulated agent the flags labelled in dev_labels
    (what an LLM agent should notice, e.g. an out-of-scope request).
    limit_families: family names or globs (e.g. "*-TWIN"); folds stay the
    same as in the full run, so the numbers for those families are identical,
    only the other families are skipped. Folds run in parallel processes."""
    cases = load_jsonl(DEV_CASES)
    groups = [c["scenario_family"] for c in cases]
    tasks = []
    for train_idx, test_idx in GroupKFold(n_splits=n_splits).split(np.zeros(len(cases)), groups=groups):
        held = [cases[i] for i in test_idx
                if not limit_families or matches_families(cases[i]["scenario_family"], limit_families)]
        if held:
            tasks.append(([cases[i] for i in train_idx], held, mode, use_model, model_kwargs, agent_flags))
    return [r for rs in map_folds(_fold, tasks, n_jobs) for r in rs]


def summarise(rows):
    def block(rs):
        s = [r["score"] for r in rs]
        esc_exp = [x for x in s if x["esc_expected"]]
        return {
            "n": len(s),
            "passed": _rate(x["passed"] for x in s),
            "action_ok": _rate(x["action_ok"] for x in s),
            "under": _rate(x["under"] for x in s),
            "risk_ok": _rate(x["risk_ok"] for x in s),
            "esc_recall": _rate(x["esc_given"] for x in esc_exp),
            "esc_false_pos": sum(1 for x in s if x["esc_given"] and not x["esc_expected"]),
            "asked_decisive": _rate(x["asked_ok"] for x in s if x["asked_ok"] is not None),
            "benign_fa": _rate(x["benign_fa"] for x in s if x["benign_fa"] is not None),
            "questions": round(sum(x["n_questions"] for x in s) / max(1, len(s)), 2),
            "unnecessary_q": round(sum(x["unnecessary"] for x in s) / max(1, len(s)), 2),
        }
    out = {"overall": block(rows), "by_journey": {}, "by_language": {}, "twin_vs_single": {}}
    for key, get in (("by_journey", lambda r: r["case"]["journey"]), ("by_language", lambda r: r["case"]["language"]),
                     ("twin_vs_single", lambda r: "twin" if r["case"]["ground_truth"].get("twin_group") else "single")):
        g = collections.defaultdict(list)
        for r in rows:
            g[get(r)].append(r)
        out[key] = {k: block(v) for k, v in sorted(g.items())}
    fam = collections.defaultdict(list)
    for r in rows:
        fam[r["case"]["scenario_family"]].append(r)
    worst = sorted(fam.items(), key=lambda kv: _rate(r["score"]["passed"] for r in kv[1]))
    out["worst_families"] = []
    for f, rs in worst[:12]:
        rate = _rate(r["score"]["passed"] for r in rs)
        if rate == 100:
            break
        fails = collections.Counter()
        for r in rs:
            s = r["score"]
            for k in ("action_ok", "risk_ok"):
                if not s[k]:
                    fails[k.replace("_ok", "") + ":" + r["sim"]["decision"]["action"] if k == "action_ok" else "risk:" + r["sim"]["decision"]["risk_level"]] += 1
            if s["esc_expected"] and not s["esc_given"]:
                fails["missed_escalation"] += 1
            if s["asked_ok"] is False:
                fails["no_decisive_question"] += 1
        out["worst_families"].append({"family": f, "passed": rate, "failures": fails.most_common(3),
                                      "example_trace": rs[0]["sim"]["trace"]})
    return out

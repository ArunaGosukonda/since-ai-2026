"""Cross-validation of the threat -> facts model.

Two kinds of numbers:
  facts    how well each fact is recognised (ROC AUC, and precision/recall
           when a fact counts as present at P >= threshold)
  action   the end-to-end result: predicted facts -> lookup table
           (knowledge.decide_action) -> action, scored like the official
           action check. Directly comparable with the baseline action model.
           No asking policy yet: twins with the decisive answer unknown are
           scored as-is (step 3 adds the policy).
"""
import collections

import numpy as np
from sklearn.metrics import roc_auc_score

from . import evidence, knowledge
from .data import INTERVENTION
from .evaluate import _rate, folds
from .facts_model import STATES, FactModel
from .parallel import map_folds


NO_MODEL_PRIOR = 0.2    # P(fact) used when the ML model is switched off (evidence only)


def _fold(train, held, model_kwargs, use_model, use_evidence):
    fact_defs = knowledge.facts()
    if use_model:
        model = FactModel(**(model_kwargs or {})).fit(train)
        P = [dict(zip(model.fact_ids_, p)) for p in model.proba([(e.case, e.answers) for e in held])]
    else:
        P = [{f: NO_MODEL_PRIOR for f in fact_defs} for _ in held]
    records = []
    for e, p in zip(held, P):
        if use_evidence:
            p, _ = evidence.apply(p, evidence.matches(fact_defs, e.case, e.answers))
        records.append({"example": e, "p": p})
    return records


def cross_validate(examples, scheme="family", n_splits=7, model_kwargs=None, use_model=True, use_evidence=True, n_jobs=None):
    """use_model / use_evidence switch the two sources of fact probabilities
    on and off, so their contributions can be compared. Folds run in
    parallel processes (n_jobs, see dsa/parallel.py)."""
    tasks = [([examples[i] for i in tr], [examples[i] for i in te], model_kwargs, use_model, use_evidence)
             for tr, te in folds(examples, scheme, n_splits)]
    return [r for rs in map_folds(_fold, tasks, n_jobs) for r in rs]


def predicted_facts(p, threshold):
    """Facts at or above the threshold; if none, the single most likely one."""
    present = [f for f, v in p.items() if v >= threshold]
    return present or [max(p, key=p.get)]


def summarise(records, threshold=0.5):
    fact_ids = list(knowledge.facts())
    fact_defs = knowledge.facts()
    settings = dict(knowledge.decision_settings(), present_at=threshold)
    for r in records:
        r["pred_facts"], _ = knowledge.facts_present(r["p"], fact_defs, settings)
        r["pred"], _ = knowledge.decide_action(r["pred_facts"], fact_defs)

    # --- per-fact quality
    per_fact = {}
    for f in fact_ids:
        y = np.array([f in r["example"].facts for r in records])
        s = np.array([r["p"][f] for r in records])
        pred = s >= threshold
        per_fact[f] = {
            "positives": int(y.sum()),
            "auc": round(float(roc_auc_score(y, s)), 3) if 0 < y.sum() < len(y) else None,
            "precision": _rate(y[pred]) if pred.any() else None,
            "recall": _rate(pred[y]) if y.any() else None,
        }

    def block(rs):
        ok = [r["pred"] in r["example"].acceptable for r in rs]
        misses = [r for r, o in zip(rs, ok) if not o]
        under = [INTERVENTION[r["pred"]] < INTERVENTION[r["example"].primary] for r in misses]
        pad = [False] * (len(rs) - len(misses))
        return {
            "n": len(rs),
            "action_ok": _rate(ok),
            "facts_exact": _rate(set(r["pred_facts"]) == set(r["example"].facts) for r in rs),
            "under_reaction": _rate(under + pad),
            "over_reaction": _rate([not u for u in under] + pad),
            "benign_false_alarm": _rate(r["pred"] not in r["example"].acceptable for r in rs if r["example"].is_benign),
            "twin_action_ok": _rate(r["pred"] in r["example"].acceptable for r in rs if r["example"].is_twin),
        }

    out = {"threshold": threshold, "per_fact": per_fact, "overall": block(records), "by_view": {}, "by_journey": {}, "by_language": {}}
    for key, get in (("by_view", lambda r: r["example"].state),
                     ("by_journey", lambda r: r["example"].meta["journey"]),
                     ("by_language", lambda r: r["example"].meta["language"])):
        groups = collections.defaultdict(list)
        for r in records:
            groups[get(r)].append(r)
        order = STATES if key == "by_view" else sorted(groups)
        out[key] = {g: block(groups[g]) for g in order if g in groups}

    fam = collections.defaultdict(list)
    for r in records:
        fam[r["example"].family].append(r)
    worst = sorted(((f, _rate(r["pred"] in r["example"].acceptable for r in rs)) for f, rs in fam.items()), key=lambda x: x[1])
    out["worst_families"] = [{
        "family": f, "action_ok": v,
        "true_facts": sorted({x for r in fam[f] for x in r["example"].facts}),
        "top_wrong": collections.Counter(r["pred"] for r in fam[f] if r["pred"] not in r["example"].acceptable).most_common(2),
    } for f, v in worst[:12] if v < 100]
    return out

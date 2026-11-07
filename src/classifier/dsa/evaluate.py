"""Cross-validation for the action head.

  family  leave-families-out: whole scenario families are held out per fold.
          This is the honest estimate, since the test set contains 9 families
          that dev never shows.
  random  cases split at random (all views of a case stay together). Families
          leak across folds, so this is optimistic; the gap between the two
          shows how much the model is memorising templates.

Metrics mirror the official scorer's action check (dsakit/scoring.py):
  action_ok    predicted action is in the acceptable set for that state
  exact        predicted action equals the reference action
  under / over among misses: predicted action is less / more interventive
               than the reference ("under_reaction" is the dangerous one)
  benign_false_alarm   benign controls whose action was not acceptable
"""
import collections

import numpy as np
from sklearn.model_selection import GroupKFold

from .data import INTERVENTION, VIEWS
from .model import ActionModel


def folds(examples, scheme, n_splits, seed=0):
    if scheme == "family":
        groups = [e.family for e in examples]
    elif scheme == "random":
        ids = sorted({e.case_id for e in examples})
        rng = np.random.default_rng(seed)
        shuffled = dict(zip(ids, rng.permutation(len(ids))))
        groups = [shuffled[e.case_id] for e in examples]
    else:
        raise ValueError("scheme must be 'family' or 'random'")
    return GroupKFold(n_splits=n_splits).split(np.zeros(len(examples)), groups=groups)


def cross_validate(examples, scheme="family", n_splits=7, model_kwargs=None):
    """Returns one prediction record per example, made by a model that never
    saw that example's fold."""
    records = []
    for train_idx, test_idx in folds(examples, scheme, n_splits):
        model = ActionModel(**(model_kwargs or {})).fit([examples[i] for i in train_idx])
        held = [examples[i] for i in test_idx]
        P = model.proba([(e.case, e.facts) for e in held])
        for e, p in zip(held, P):
            got = model.decide(p)
            records.append({"example": e, "pred": got, "conf": float(p.max())})
    return records


def _rate(xs):
    xs = list(xs)
    return None if not xs else round(100.0 * sum(xs) / len(xs), 1)


def summarise(records):
    def block(rs):
        ok = [r["pred"] in r["example"].acceptable for r in rs]
        misses = [r for r, o in zip(rs, ok) if not o]
        under = [INTERVENTION[r["pred"]] < INTERVENTION[r["example"].primary] for r in misses]
        return {
            "n": len(rs),
            "action_ok": _rate(ok),
            "exact": _rate(r["pred"] == r["example"].primary for r in rs),
            "under_reaction": _rate(under + [False] * (len(rs) - len(misses))),
            "over_reaction": _rate([not u for u in under] + [False] * (len(rs) - len(misses))),
            "benign_false_alarm": _rate(r["pred"] not in r["example"].acceptable for r in rs if r["example"].is_benign),
            "twin_action_ok": _rate(r["pred"] in r["example"].acceptable for r in rs if r["example"].is_twin),
        }

    out = {"overall": block(records), "by_view": {}, "by_journey": {}, "by_language": {}}
    for key, get in (("by_view", lambda r: r["example"].view),
                     ("by_journey", lambda r: r["example"].meta["journey"]),
                     ("by_language", lambda r: r["example"].meta["language"])):
        groups = collections.defaultdict(list)
        for r in records:
            groups[get(r)].append(r)
        order = VIEWS if key == "by_view" else sorted(groups)
        out[key] = {g: block(groups[g]) for g in order if g in groups}

    fam = collections.defaultdict(list)
    for r in records:
        fam[r["example"].family].append(r)
    worst = sorted(((f, _rate(r["pred"] in r["example"].acceptable for r in rs)) for f, rs in fam.items()), key=lambda x: x[1])
    out["worst_families"] = [{"family": f, "action_ok": v,
                              "top_wrong": collections.Counter(r["pred"] for r in fam[f] if r["pred"] not in r["example"].acceptable).most_common(2)}
                             for f, v in worst[:10] if v < 100]
    return out

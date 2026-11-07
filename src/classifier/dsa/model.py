"""The action head: which of the 10 vocabulary actions to recommend.

Two training targets are supported, so they can be compared in CV:

  acceptable  (default) one yes/no classifier per action: "would the scorer
              accept this action here?". Trained on the full acceptable set,
              so the model learns e.g. that escalating is also fine in a
              remote-access case. Prediction = the action most likely to be
              acceptable; near-ties go to the more cautious action.
  primary     one multi-class classifier on the single reference action.

Both are logistic regressions: every feature gets a learned weight per action,
which keeps decisions explainable (see ``explain``).
"""
import datetime
import os

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier

from .data import ACTIONS, INTERVENTION, ROOT
from .features import Featurizer

MODEL_DIR = os.path.join(ROOT, "models")
DEFAULT_PATH = os.path.join(MODEL_DIR, "action.joblib")
TIE_MARGIN = 0.03     # probabilities this close count as a tie -> pick the more cautious action


class ActionModel:
    def __init__(self, target="acceptable", C=4.0, blocks=("user", "artifact", "signals"), signals_weight=0.35):
        self.target = target
        self.C = C
        self.blocks = tuple(blocks)
        self.signals_weight = signals_weight

    # --- training ---------------------------------------------------------
    def fit(self, examples):
        X_in = [(e.case, e.facts) for e in examples]
        self.featurizer_ = Featurizer(blocks=self.blocks, signals_weight=self.signals_weight).fit(X_in)
        X = self.featurizer_.transform(X_in)
        if self.target == "acceptable":
            Y = np.array([[a in e.acceptable for a in ACTIONS] for e in examples], dtype=int)
            self.clf_ = OneVsRestClassifier(LogisticRegression(C=self.C, class_weight="balanced", solver="liblinear", max_iter=2000)).fit(X, Y)
        elif self.target == "primary":
            y = [e.primary for e in examples]
            self.clf_ = LogisticRegression(C=self.C, class_weight="balanced", max_iter=2000).fit(X, y)
        else:
            raise ValueError("target must be 'acceptable' or 'primary'")
        self.trained_on_ = len(examples)
        return self

    # --- prediction ---------------------------------------------------------
    def proba(self, pairs):
        """(n, 10) array in ACTIONS order. For 'acceptable' each entry is
        P(action is acceptable); for 'primary' a distribution over actions."""
        X = self.featurizer_.transform(pairs)
        if self.target == "acceptable":
            return self.clf_.predict_proba(X)
        P = np.zeros((X.shape[0], len(ACTIONS)))
        for j, cls in enumerate(self.clf_.classes_):
            P[:, ACTIONS.index(cls)] = self.clf_.predict_proba(X)[:, j]
        return P

    @staticmethod
    def decide(p):
        """Pick an action from one probability row, breaking near-ties towards
        the higher-intervention (more cautious) action."""
        best = p.max()
        tied = [a for a, v in zip(ACTIONS, p) if v >= best - TIE_MARGIN]
        return max(tied, key=lambda a: (INTERVENTION[a], p[ACTIONS.index(a)]))

    def predict(self, pairs):
        return [self.decide(p) for p in self.proba(pairs)]

    def explain(self, case, facts=None, action=None, top=8):
        """The features that pushed hardest towards (and against) an action
        for this one input: weight x feature value."""
        x = self.featurizer_.transform([(case, facts or {})])
        action = action or self.predict([(case, facts or {})])[0]
        k = ACTIONS.index(action)
        if self.target == "acceptable":
            est = self.clf_.estimators_[k]
            coef = getattr(est, "coef_", None)
            if coef is None:            # constant predictor: label never/always seen
                return {"action": action, "for": [], "against": []}
            w = coef[0]
        else:
            w = self.clf_.coef_[list(self.clf_.classes_).index(action)]
        contrib = x.multiply(w).tocsr()
        idx, vals = contrib.indices, contrib.data
        names = self.featurizer_.feature_names()
        order = np.argsort(vals)
        fmt = lambda i: {"feature": names[idx[i]], "weight": round(float(vals[i]), 3)}
        return {"action": action,
                "for": [fmt(i) for i in order[::-1][:top] if vals[i] > 0],
                "against": [fmt(i) for i in order[:top] if vals[i] < 0]}

    # --- persistence ----------------------------------------------------------
    def save(self, path=DEFAULT_PATH, meta=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        meta = dict(meta or {}, saved_at=datetime.datetime.now().isoformat(timespec="seconds"),
                    target=self.target, C=self.C, blocks=list(self.blocks), signals_weight=self.signals_weight,
                    trained_on=self.trained_on_, actions=ACTIONS)
        joblib.dump({"model": self, "meta": meta}, path)
        return meta

    @staticmethod
    def load(path=DEFAULT_PATH):
        blob = joblib.load(path)
        return blob["model"], blob["meta"]

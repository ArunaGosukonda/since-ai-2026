"""Threat -> facts: predicts which underlying facts (knowledge/facts.yaml)
hold, from what the assistant can see at a given point in a conversation:

  user text      what the user wrote
  artifact text  the message/call being asked about
  signals        structured context, flattened (consent-gated ones may be hidden)
  answers        categorical answers to the questions asked so far
                 (knowledge/questions.yaml); unasked questions are absent

One logistic regression per fact gives P(fact holds). Facts are not
exclusive: a remote-access scam can be device_compromised AND
bank_access_exposed.

Training examples are conversation *states* of each dev case: nothing asked
(gated signals hidden), nothing asked (all signals), a few random subsets of
answers, and every answer. Fact labels are always the case's true situation,
so in a twin case with the decisive answer unknown the model should learn to
be unsure, which is what triggers asking.
"""
import datetime
import os
import random
from dataclasses import dataclass, field

import joblib
import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier

from . import knowledge
from .data import DEV_CASES, ROOT, hide_gated, labels_for, load_jsonl, opening_is_descriptive
from .features import _tfidf, artifact_text, signal_dict, user_text

DEFAULT_PATH = os.path.join(ROOT, "models", "facts.joblib")
STATES = ("visible", "full", "partial", "answered")


@dataclass
class FactExample:
    case_id: str
    family: str
    state: str
    case: dict                 # input as seen in this state
    answers: dict              # topic -> categorical value, only asked questions
    facts: list                # true facts (knowledge/dev_labels.yaml)
    acceptable: list           # actions the scorer accepts in this state
    primary: str
    is_benign: bool
    is_twin: bool
    meta: dict = field(default_factory=dict)


def build_examples(cases=None, n_partial=2, seed=0, states=STATES):
    cases = cases if cases is not None else load_jsonl(DEV_CASES)
    labels = knowledge.dev_labels()
    rng = random.Random(seed)
    out = []
    for case in cases:
        lab = labels[knowledge.label_key(case)]
        all_answers = {k: str(v) for k, v in (lab.get("answers") or {}).items()}
        # what the opening message already says (only if it describes the situation)
        stated = {k: str(v) for k, v in (lab.get("stated") or {}).items()} if opening_is_descriptive(case["opening_message"]) else {}
        gt = case["ground_truth"]
        variants = []
        if "visible" in states:
            variants.append(("visible", hide_gated(case), dict(stated)))
        if "full" in states:
            variants.append(("full", case, dict(stated)))
        if "partial" in states and len(all_answers) > 1:
            topics = sorted(all_answers)
            for _ in range(n_partial):
                k = rng.randint(1, len(topics) - 1)
                pick = rng.sample(topics, k)
                # partial answers come with or without consent-gated signals
                seen = hide_gated(case) if rng.random() < 0.5 else case
                variants.append(("partial", seen, {**stated, **{t: all_answers[t] for t in pick}}))
        if "answered" in states and all_answers:
            variants.append(("answered", case, {**stated, **all_answers}))
        for state, seen, answers in variants:
            # a twin's decisive question counts as answered only with a definite answer
            decisive_known = not gt.get("twin_group") or any(
                answers.get(t) not in (None, "unsure") for t in gt["must_ask_topics"])
            acc, primary = labels_for(case, facts_known=decisive_known)
            out.append(FactExample(
                case_id=case["case_id"], family=case["scenario_family"], state=state, case=seen,
                answers=answers, facts=list(lab["facts"]), acceptable=acc, primary=primary,
                is_benign=bool(gt["is_benign_control"]), is_twin=bool(gt.get("twin_group")),
                meta={"journey": case["journey"], "language": case["language"], "audience": case["audience"]},
            ))
    return out


def answer_dict(answers):
    return {f"answer:{t}={v}": 1 for t, v in (answers or {}).items()} or {"answer:none": 1}


class FactModel:
    def __init__(self, C=2.0, blocks=("user", "artifact", "signals", "answers"),
                 signals_weight=0.35, answers_weight=1.0):
        self.C = C
        self.blocks = tuple(blocks)
        self.signals_weight = signals_weight
        self.answers_weight = answers_weight

    # --- features -------------------------------------------------------------
    def _parts(self, X):
        """X: list of (case, answers)."""
        return {
            "user": [user_text(c) for c, a in X],
            "artifact": [artifact_text(c) for c, a in X],
            "signals": [signal_dict(c) for c, a in X],
            "answers": [answer_dict(a) for c, a in X],
        }

    def _weights(self):
        return {"user": 1.0, "artifact": 1.0, "signals": self.signals_weight, "answers": self.answers_weight}

    def _fit_features(self, X):
        parts = self._parts(X)
        self.vec_ = {}
        for b in self.blocks:
            self.vec_[b] = (_tfidf() if b in ("user", "artifact") else DictVectorizer()).fit(parts[b])

    def _transform(self, X):
        parts, w = self._parts(X), self._weights()
        return sp.hstack([w[b] * self.vec_[b].transform(parts[b]) for b in self.blocks]).tocsr()

    def feature_names(self):
        return np.array([f"{b}:{n}" for b in self.blocks for n in self.vec_[b].get_feature_names_out()])

    # --- training / prediction --------------------------------------------------
    def fit(self, examples):
        self.fact_ids_ = list(knowledge.facts())
        X_in = [(e.case, e.answers) for e in examples]
        self._fit_features(X_in)
        Y = np.array([[f in e.facts for f in self.fact_ids_] for e in examples], dtype=int)
        self.clf_ = OneVsRestClassifier(
            LogisticRegression(C=self.C, class_weight="balanced", solver="liblinear", max_iter=2000)).fit(self._transform(X_in), Y)
        self.trained_on_ = len(examples)
        return self

    def proba(self, pairs):
        """(n, n_facts) array of P(fact holds), columns in self.fact_ids_ order."""
        return self.clf_.predict_proba(self._transform(pairs))

    def predict_facts(self, case, answers=None):
        p = self.proba([(case, answers or {})])[0]
        return dict(zip(self.fact_ids_, (round(float(x), 4) for x in p)))

    def explain(self, case, answers, fact, top=8):
        """Features pushing hardest towards / against one fact for this input."""
        x = self._transform([(case, answers or {})])
        est = self.clf_.estimators_[self.fact_ids_.index(fact)]
        coef = getattr(est, "coef_", None)
        if coef is None:
            return {"fact": fact, "for": [], "against": []}
        contrib = x.multiply(coef[0]).tocsr()
        idx, vals, names = contrib.indices, contrib.data, self.feature_names()
        order = np.argsort(vals)
        fmt = lambda i: {"feature": names[idx[i]], "weight": round(float(vals[i]), 3)}
        return {"fact": fact,
                "for": [fmt(i) for i in order[::-1][:top] if vals[i] > 0],
                "against": [fmt(i) for i in order[:top] if vals[i] < 0]}

    # --- persistence ------------------------------------------------------------
    def save(self, path=DEFAULT_PATH, meta=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        meta = dict(meta or {}, saved_at=datetime.datetime.now().isoformat(timespec="seconds"),
                    C=self.C, blocks=list(self.blocks), signals_weight=self.signals_weight,
                    answers_weight=self.answers_weight, trained_on=self.trained_on_, facts=self.fact_ids_)
        joblib.dump({"model": self, "meta": meta}, path)
        return meta

    @staticmethod
    def load(path=DEFAULT_PATH):
        blob = joblib.load(path)
        return blob["model"], blob["meta"]

"""Feature extraction: what the model gets to look at.

Three blocks, stacked side by side:

  user text      what the user wrote (opening message, call notes) and, later
                 in a conversation, their answers to questions.
  artifact text  the message/call being asked about: body, sender, links.
                 Kept separate from the user's words so "click the link" in a
                 scam text is not confused with "I clicked the link".
  signals        the structured context (link check, call warning, device,
                 logins, SIM events, breach check, business profile) flattened
                 into categorical "path=value" indicators, plus a few derived
                 red flags. A consent-gated signal that is not visible yet is
                 encoded as its own value, "hidden", never as "nothing found".

Text uses character n-grams (3-5 chars within word boundaries), which cope with
Finnish and Swedish inflection without language-specific tokenisers.
TODO(embeddings): add a multilingual sentence-embedding block here if
leave-family-out CV shows the text blocks do not generalise (see MODEL_STATUS.md, W7).
"""
import math

import numpy as np
import scipy.sparse as sp
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer

from .data import HIDDEN, STAND_IN

# Fields that are identifiers, timestamps or free text: never one-hot encoded.
SKIP_KEYS = {"body", "sender", "url", "links", "received_at", "checked_at", "call_time",
             "number", "company", "name", "os_version", "user_call_notes"}

PERSONA_KEYS = ("segment", "age_band", "tech_confidence", "emotional_state")


def _bucket(v):
    """Log-scale bucket for counts and ages: 0, 1, 2-3, 4-7, 8-15, ..."""
    if v is None:
        return "na"
    if isinstance(v, float) and 0 <= v <= 1:
        return "p%d" % int(v * 4)               # confidences: quartiles
    v = max(0, int(v))
    return "0" if v == 0 else "b%d" % int(math.log2(v))


def _flatten(obj, path, out):
    """Emit categorical indicators for a signal subtree."""
    if obj is None:
        out[path + "=null"] = 1
    elif isinstance(obj, str) and obj == HIDDEN:
        out[path + "=hidden"] = 1
    elif isinstance(obj, dict):
        if not obj:
            out[path + "=empty"] = 1
        for k, v in obj.items():
            if k not in SKIP_KEYS:
                _flatten(v, f"{path}.{k}" if path else k, out)
    elif isinstance(obj, list):
        out[path + "#" + _bucket(len(obj))] = 1
        for item in obj:
            # list items are aggregated: "this value occurs somewhere in the list"
            _flatten(item, path + "[]", out)
    elif isinstance(obj, bool):
        out[f"{path}={str(obj).lower()}"] = 1
    elif isinstance(obj, (int, float)):
        out[f"{path}~{_bucket(obj)}"] = 1
    else:
        out[f"{path}={str(obj).lower()}"] = 1


def _is_list(x):
    return isinstance(x, list)


def derived_flags(case):
    """A handful of hand-made red flags that the generic flattening cannot
    express (comparisons across fields). Each is 1 when present."""
    s = case.get("signals", {})
    f = {}
    lang, locale = case.get("language"), case.get("locale", "")
    country = locale.split("-")[-1] if "-" in locale else None

    art = s.get("artifact") or {}
    if art.get("channel_language") and art.get("channel_language") != lang:
        f["flag:artifact_language_mismatch"] = 1
    if art.get("links"):
        f["flag:artifact_has_link"] = 1

    logins = (s.get("operator_account") or {}).get("recent_logins")
    if _is_list(logins):
        if any(not l.get("device_known") for l in logins):
            f["flag:login_unknown_device"] = 1
        if country and any(l.get("country") not in (None, country) for l in logins):
            f["flag:login_abroad"] = 1
        if any(not l.get("device_known") and l.get("days_ago", 99) <= 1 for l in logins):
            f["flag:login_unknown_device_recent"] = 1

    dev = s.get("device") or {}
    apps = dev.get("recent_app_installs")
    if _is_list(apps):
        if any(a.get("source") not in (None, "official_store") for a in apps):
            f["flag:sideloaded_app"] = 1
        risky = {"accessibility_service", "read_sms", "draw_over_apps", "install_unknown_apps", "device_admin"}
        if any(set(a.get("permissions") or []) & risky for a in apps):
            f["flag:app_risky_permission"] = 1
    found = dev.get("security_findings")
    if isinstance(found, dict) and any(found.get(k) for k in ("unknown_profiles", "remote_access_apps", "accessibility_services")):
        f["flag:device_security_finding"] = 1

    events = (s.get("subscription") or {}).get("recent_events")
    if _is_list(events):
        # substring match on purpose: test has event types dev never shows (e.g. number_port_out_request)
        sim_like = ("sim", "port", "transfer")
        for e in events:
            t = str(e.get("type", "")).lower()
            recent = e.get("minutes_ago") is not None or e.get("hours_ago") is not None or e.get("days_ago", 99) <= 2
            if recent and any(k in t for k in sim_like):
                f["flag:recent_sim_event"] = 1
            if recent and (any(k in t for k in sim_like) or "order" in t):
                f["flag:recent_account_change"] = 1
    net = (s.get("subscription") or {}).get("network_status")
    if isinstance(net, dict) and net.get("service") not in (None, "normal"):
        f["flag:network_service_lost"] = 1

    cred = s.get("credential_exposure")
    if isinstance(cred, dict) and cred.get("found"):
        exposed = {x for src in cred.get("sources", []) for x in src.get("exposed", [])}
        f["flag:credentials_exposed"] = 1
        if "password" in exposed:
            f["flag:password_exposed"] = 1
    return f


def signal_dict(case, facts=None):
    d = {}
    for k in ("journey", "audience", "language", "entry_point"):
        d[f"{k}={case.get(k)}"] = 1
    d[f"user_identified={str(case.get('user_identified')).lower()}"] = 1
    for k in PERSONA_KEYS:
        d[f"persona.{k}={(case.get('persona') or {}).get(k)}"] = 1
    for k, v in (case.get("signal_availability") or {}).items():
        d[f"availability.{k}={v}"] = 1
    _flatten(case.get("signals", {}), "", d)
    d.update(derived_flags(case))
    # which question topics the user has answered (the answer text goes to the user-text block)
    for topic in (facts or {}):
        d[f"answered:{topic}"] = 1
    return d


def user_text(case, facts=None):
    parts = [case.get("opening_message") or ""]
    notes = (case.get("signals") or {}).get("user_call_notes")
    if isinstance(notes, str) and notes != HIDDEN:
        parts.append(notes)
    parts += [str(v) for v in (facts or {}).values()]
    return "\n".join(parts)


def artifact_text(case):
    art = (case.get("signals") or {}).get("artifact") or {}
    parts = [art.get("type") or "", art.get("sender") or "", art.get("body") or ""]
    parts += [str(x) for x in art.get("links") or []]
    return "\n".join(parts)


def _standin(case):
    return {"fact:" + s: 1 for s in case.get(STAND_IN, [])} or {"fact:none": 1}


def _tfidf():
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True, max_features=60000)


class Featurizer(BaseEstimator, TransformerMixin):
    """Maps a list of (case, facts) pairs to one sparse feature matrix.

    blocks: which of "user", "artifact", "signals" to use (for ablations).
    *_weight: scales each block so no block drowns out the others."""

    def __init__(self, blocks=("user", "artifact", "signals"), user_weight=1.0, artifact_weight=1.0, signals_weight=0.35):
        self.blocks = blocks
        self.user_weight = user_weight
        self.artifact_weight = artifact_weight
        self.signals_weight = signals_weight

    def fit(self, X, y=None):
        if "user" in self.blocks:
            self.user_ = _tfidf().fit([user_text(c, f) for c, f in X])
        if "artifact" in self.blocks:
            self.artifact_ = _tfidf().fit([artifact_text(c) for c, f in X])
        if "signals" in self.blocks:
            self.signals_ = DictVectorizer().fit([signal_dict(c, f) for c, f in X])
        if "standin" in self.blocks:       # experiment: ground-truth steps as stand-in facts
            self.standin_ = DictVectorizer().fit([_standin(c) for c, f in X])
        return self

    def transform(self, X):
        mats = []
        if "user" in self.blocks:
            mats.append(self.user_weight * self.user_.transform([user_text(c, f) for c, f in X]))
        if "artifact" in self.blocks:
            mats.append(self.artifact_weight * self.artifact_.transform([artifact_text(c) for c, f in X]))
        if "signals" in self.blocks:
            mats.append(self.signals_weight * self.signals_.transform([signal_dict(c, f) for c, f in X]))
        if "standin" in self.blocks:
            mats.append(self.standin_.transform([_standin(c) for c, f in X]))
        return sp.hstack(mats).tocsr()

    def feature_names(self):
        names = []
        if "user" in self.blocks:
            names += ["user:" + n for n in self.user_.get_feature_names_out()]
        if "artifact" in self.blocks:
            names += ["artifact:" + n for n in self.artifact_.get_feature_names_out()]
        if "signals" in self.blocks:
            names += ["signal:" + n for n in self.signals_.get_feature_names_out()]
        if "standin" in self.blocks:
            names += ["standin:" + n for n in self.standin_.get_feature_names_out()]
        return np.array(names)

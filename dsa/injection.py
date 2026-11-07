"""Detect text inside a forwarded artifact that addresses an AI assistant (prompt injection).

Artifact text is untrusted DATA. This module only pattern-matches it; nothing in it
is ever followed, echoed into advice, or used to relax a decision. A hit makes the
message less trustworthy (a genuine sender never writes to "the AI assistant").

Patterns cover Finnish, English and Swedish: a direct address to an AI/automated
assistant or a "system message", an instruction-override phrase, or a claim to
assistants that the content was verified as safe.
"""
import re

from .kit import textcheck

_P = [
    # direct address to an assistant / model / system
    ("address", r"\b(ai|a\.i\.|tekoäly|tekoälyavustaj\w*|ki)[- ]?(assistant\w*|assistent\w*|avustaj\w*|agent\w*|bot\w*|model\w*|malli\w*)\b"),
    ("address", r"\b(tekoälyavustaj\w*|tekoälylle|kielimalli\w*|chatbot\w*|chattibot\w*|language model\w*|språkmodell\w*)"),
    ("address", r"\b(automaattise\w* avustaj\w*|automated assistants?|automatiska assistent\w*|virtual assistants?|virtuaaliavustaj\w*)"),
    ("address", r"\b(till|to|for|för|dear|hei|huom\.?)\s+(the\s+)?(ai|ki|tekoäly)\b"),
    ("system", r"(^|[\s\[(])(system|järjestelmä|systemmeddelande)(viesti|message|prompt|meddelande)?\s*:"),
    ("system", r"\b(järjestelmäviesti|systemmeddelande|system message|system prompt)\b"),
    # instruction override
    ("override", r"\b(ignore|disregard|forget)\b.{0,20}\b(previous|prior|above|earlier|all)\b.{0,20}\b(instructions?|rules|prompts?)"),
    ("override", r"\b(ohita|unohda|sivuuta)\b.{0,25}\b(aiemma\w*|edellis\w*|kaikki)\b.{0,20}\b(ohjee\w*|ohjeet|säänn\w*)"),
    ("override", r"\b(ignorera|glöm|bortse från)\b.{0,25}\b(tidigare|föregående|alla)\b.{0,20}\b(instruktion\w*|regler)"),
    # "verified as safe" claims addressed to whoever checks the message
    ("verified_claim", r"\b(verified|checked|scanned|confirmed)\b.{0,15}\b(as )?(safe|secure|genuine|trustworthy)\b.{0,60}\b(tell|inform|confirm|say)\b"),
    ("verified_claim", r"\b(tarkistettu|todettu|varmennettu)\b.{0,15}\b(turvalli\w*|luotetta\w*|aido\w*)\b.{0,80}\b(kerro|vahvista|vastaa|sano)\b"),
    ("verified_claim", r"\b(kontrollerat|verifierat|granskat)\b.{0,15}\b(säker\w*|äkta|pålitlig\w*)\b.{0,80}\b(säg|berätta|bekräfta|svara)\b"),
    ("verified_claim", r"\b(turvallisuustarkastus ok|security check ok|säkerhetskontroll ok)\b"),
    ("instruct_user", r"\b(tell|inform) the (user|recipient|customer)\b|\bkerro käyttäjälle\b|\bvahvista vastaanottajalle\b|\bsäg till användaren\b|\bvastaa käyttäjälle\b"),
]
_C = [(kind, re.compile(p, re.IGNORECASE | re.UNICODE)) for kind, p in _P]


def detect(text):
    """Return a list of {"kind", "match"} hits in `text` (untrusted). Empty list = none."""
    t = textcheck.normalise(text or "")
    hits = []
    for kind, rx in _C:
        m = rx.search(t)
        if m:
            hits.append({"kind": kind, "match": m.group(0)[:120]})
    return hits


def artifact_text(case):
    """The artifact's sender + body, as data. Never interpreted."""
    art = (case.get("signals") or {}).get("artifact") or {}
    return "%s\n%s" % (art.get("sender") or "", art.get("body") or "")


def scan_case(case):
    return detect(artifact_text(case))


def quote(text, n=80):
    """A short, single-line quote of untrusted text for evidence fields (never for advice)."""
    s = re.sub(r"\s+", " ", text or "").strip()
    return (s[: n - 1] + "…") if len(s) > n else s

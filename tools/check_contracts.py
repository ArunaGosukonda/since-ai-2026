"""Check the team contracts in contracts/ against the vendor kit and the dev data.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_contracts.py

(a) every ID in the contracts exists in data/reference/ (actions, risk, urgency,
    steps, question topics, escalation targets, signal paths, guidance ids) or in
    contracts/facts.schema.json (fact names and values used in 'when' / decisive_fact);
    decision.schema.json carries the vendor submission schema unchanged plus trace.
(b) every dev (family, branch) is mapped to a situation, and nothing else is.
(c) DECISION-ORACLE CHECK (diagnostic only, never used for submissions): each dev
    case is answered from its mapped situation row (twins: the riskier branch's row
    plus its decisive question topics, as in single-turn) and scored with
    dsakit.scoring.score_case. Reports conditions 1, 3, 4 and 5 of the pass rule.
(d) the vendor kit under instructions/ is byte-identical to its MANIFEST.json.

Exit code 0 only when there are no unknown IDs, no unmapped families, the oracle
is at ORACLE_THRESHOLD (100 %: no dev case may fail) and every family failing the
oracle is explained in CONFLICTS.md.
"""
import sys

sys.dont_write_bytecode = True

import copy
import hashlib
import os
import re
from collections import defaultdict

import yaml

from contracts_common import (AUDIENCES, CONFLICTS_MD, DECISION_SCHEMA, FACTS_SCHEMA, KIT, MAPPING_CSV, REF, RISK,
                              SITUATIONS_YAML, URGENCY, intervention, is_twin, load_dev_cases, load_json,
                              load_jsonl, load_mapping, riskier_branches)

sys.path.insert(0, KIT)
from dsakit import minischema  # noqa: E402  (vendor kit, read-only)
from dsakit.scoring import score_case  # noqa: E402

ORACLE_THRESHOLD = 100.0
CLAUSE = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*(==|!=|not in|in)\s*(.+?)\s*$")


def rel(p):
    return os.path.relpath(p, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def header(title):
    print()
    print(title)
    print("-" * len(title))


# ---------------------------------------------------------------------------
def load_vocab():
    av = load_json(os.path.join(REF, "action_vocabulary.json"))
    return {
        "action": set(av["actions"]),
        "risk_level": set(av["risk_levels"]),
        "urgency": set(av["urgency"]),
        "escalation_target": set(av["escalation_targets"]),
        "step": set(load_json(os.path.join(REF, "step_vocabulary.json"))["steps"]),
        "question_topic": set(load_json(os.path.join(REF, "question_topics.json"))["topics"]),
        "signals": load_json(os.path.join(REF, "signal_dictionary.json"))["signals"],
        "guidance": {g["id"] for g in load_jsonl(os.path.join(REF, "guidance_corpus.jsonl"))},
    }


def fact_values(facts_schema):
    """{fact_name: set(allowed values) or None (any)}"""
    defs = facts_schema["$defs"]
    out = {}
    for name, sub in facts_schema["properties"].items():
        v = sub.get("properties", {}).get("value", {})
        if "$ref" in v:
            v = defs[v["$ref"].split("/")[-1]]
        if "enum" in v:
            out[name] = set(v["enum"])
        elif v.get("type") == "boolean":
            out[name] = {True, False}
        else:
            out[name] = None
    return out


def parse_value(tok):
    tok = tok.strip()
    return {"true": True, "false": False}.get(tok, tok)


def parse_values(raw, op):
    if op in ("in", "not in"):
        m = re.match(r"^\[(.*)\]$", raw.strip())
        if not m:
            return None
        return [parse_value(t) for t in m.group(1).split(",") if t.strip()]
    return [parse_value(raw)]


def check_ids(sits_doc, mapping_rows, vocab, facts_schema, unknown):
    fv = fact_values(facts_schema)
    sits = sits_doc["situations"]
    ids = [s["id"] for s in sits]

    def bad(kind, value, where):
        unknown.append((kind, value, where))

    for sid in set(ids):
        if ids.count(sid) > 1:
            bad("duplicate situation id", sid, "situations.yaml")
    if sorted(sits_doc.get("match_order", [])) != sorted(ids):
        bad("match_order mismatch", sits_doc.get("match_order"), "situations.yaml")
    for r in mapping_rows:
        if r["situation_id"] not in ids:
            bad("situation id", r["situation_id"], "family_to_situation.csv")

    for s in sits:
        sid = s["id"]
        for alt in s["when"]["any_of"]:
            for clause in alt:
                m = CLAUSE.match(clause)
                if not m:
                    bad("unparseable when clause", clause, sid)
                    continue
                fact, op, raw = m.groups()
                if fact not in fv:
                    bad("fact", fact, "%s.when" % sid)
                    continue
                vals = parse_values(raw, op)
                if vals is None:
                    bad("unparseable when value", raw, sid)
                    continue
                for v in vals:
                    if fv[fact] is not None and v not in fv[fact]:
                        bad("fact value", "%s=%r" % (fact, v), "%s.when" % sid)
        for aud in AUDIENCES:
            row = s.get(aud)
            where = "%s.%s" % (sid, aud)
            if not row:
                bad("missing audience row", aud, sid)
                continue
            for a in [row["primary_action"]] + list(row["acceptable_actions"]):
                if a not in vocab["action"]:
                    bad("action", a, where)
            if row["risk_level"] not in vocab["risk_level"]:
                bad("risk_level", row["risk_level"], where)
            if row["urgency"] not in vocab["urgency"]:
                bad("urgency", row["urgency"], where)
            t = row["escalation_target"]
            if t is not None and t not in vocab["escalation_target"]:
                bad("escalation target", t, where)
            for st in list(row["required_steps"]) + list(row["optional_steps"]):
                if st not in vocab["step"]:
                    bad("step", st, where)
            for d in row["decisive_fact"]:
                if d["question_topic"] not in vocab["question_topic"]:
                    bad("question topic", d["question_topic"], where)
                if d["fact"] not in fv:
                    bad("fact", d["fact"], where + ".decisive_fact")
            for sp in row["needs_consent"]:
                if sp not in vocab["signals"]:
                    bad("signal path", sp, where)
                elif vocab["signals"][sp]["consent"] != "requires_consent":
                    bad("signal path not consent-gated", sp, where)
            for g in row["guidance_refs"]:
                if g not in vocab["guidance"]:
                    bad("guidance id", g, where)


def check_schemas(vocab, facts_schema, unknown):
    vendor = load_json(os.path.join(KIT, "schema", "submission.schema.json"))
    dec = load_json(DECISION_SCHEMA)
    for k, v in vendor["properties"].items():
        if dec["properties"].get(k) != v:
            unknown.append(("decision.schema field differs from vendor", k, rel(DECISION_SCHEMA)))
    for k in vendor["required"]:
        if k not in dec["required"]:
            unknown.append(("decision.schema drops vendor required field", k, rel(DECISION_SCHEMA)))
    extra = set(dec["properties"]) - set(vendor["properties"])
    if extra != {"trace"}:
        unknown.append(("decision.schema extra fields other than trace", sorted(extra), rel(DECISION_SCHEMA)))
    p = vendor["properties"]
    for field, vs in (("primary_action", vocab["action"]), ("risk_level", vocab["risk_level"]), ("urgency", vocab["urgency"])):
        if set(p[field]["enum"]) != vs:
            unknown.append(("vendor enum differs from vocabulary", field, "submission.schema.json"))
    if set(p["question_topics"]["items"]["enum"]) != vocab["question_topic"]:
        unknown.append(("vendor enum differs from vocabulary", "question_topics", "submission.schema.json"))
    if set(x for x in p["escalation_target"]["enum"] if x) != vocab["escalation_target"]:
        unknown.append(("vendor enum differs from vocabulary", "escalation_target", "submission.schema.json"))
    if set(p["signals_used"]["items"]["enum"]) != set(vocab["signals"]):
        unknown.append(("vendor enum differs from vocabulary", "signals_used", "submission.schema.json"))
    if set(facts_schema["$defs"]["signal_path"]["enum"]) != set(vocab["signals"]):
        unknown.append(("facts.schema signal_path enum differs from signal_dictionary", "", rel(FACTS_SCHEMA)))
    for i, ex in enumerate(facts_schema.get("examples", [])):
        for name, f in ex.items():
            if f.get("source") == "signal":
                sp = f.get("signal_path")
                if sp not in vocab["signals"]:
                    unknown.append(("signal path", sp, "facts.schema examples[%d].%s" % (i, name)))
                elif f.get("consent_gated") != (vocab["signals"][sp]["consent"] == "requires_consent"):
                    unknown.append(("consent_gated disagrees with signal_dictionary", sp, "facts.schema examples[%d].%s" % (i, name)))
    return vendor, dec


def full_schema_errors(schema, inst):
    """Validate with jsonschema when available (dev dependency), else None."""
    try:
        import jsonschema
    except ImportError:
        return None
    v = jsonschema.Draft202012Validator(schema)
    return [e.message for e in v.iter_errors(inst)]


# ---------------------------------------------------------------------------
def oracle(cases, mapping, sits):
    interv = intervention()
    risky = riskier_branches(cases)
    rows = {}
    for s in sits:
        for aud in AUDIENCES:
            rows[(s["id"], aud)] = s[aud]
    results = []
    sample = None
    for c in cases:
        fam, br = c["scenario_family"], c["ground_truth"]["branch"]
        use_br = risky[fam] if is_twin(c) else br
        sid = mapping[(fam, use_br)]
        row = rows[(sid, c["audience"])]
        tgt = row["escalation_target"]
        topics = [d["question_topic"] for d in row["decisive_fact"]]
        sub = {
            "case_id": c["case_id"], "mode": "single_turn",
            "risk_level": row["risk_level"], "urgency": row["urgency"],
            "primary_action": row["primary_action"],
            "advice_text": "Decision-oracle placeholder: this text is not advice and is not scored here.",
            "escalation_required": tgt is not None, "escalation_target": tgt,
            "question_topics": topics, "steps": [],
            "signals_used": [], "consent_requested_for": [],
        }
        if sample is None:
            sample = dict(sub, trace={"situation_id": sid, "facts_used": [], "rule_ids": ["oracle:" + sid],
                                      "model": None, "signals_used": [], "consent_requested": [], "consent_granted": []})
        r = score_case(c, sub, interv)
        c1 = r["action_ok"]
        c3 = r["asked_ok"] is not False
        c4 = not (r["esc_expected"] is True and not r["esc_given"])
        c5 = r["risk_within_one"]
        why = [n for n, ok in (("1 action", c1), ("3 decisive question", c3), ("4 handoff", c4), ("5 risk", c5)) if not ok]
        results.append({"case_id": c["case_id"], "journey": c["journey"], "family": fam, "branch": br,
                        "audience": c["audience"], "situation": sid, "c1": c1, "c3": c3, "c4": c4, "c5": c5,
                        "passed": c1 and c3 and c4 and c5, "why": why})
    return results, sample


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def print_breakdown(results, key, label):
    groups = defaultdict(list)
    for r in results:
        groups[r[key]].append(r)
    w = max(len(k) for k in groups)
    print("  %-*s  %5s  %7s  %6s %6s %6s %6s" % (w, label, "n", "pass%", "c1%", "c3%", "c4%", "c5%"))
    for k in sorted(groups):
        g = groups[k]
        n = len(g)
        print("  %-*s  %5d  %6.1f%%  %5.1f%% %5.1f%% %5.1f%% %5.1f%%%s" % (
            w, k, n, pct(sum(r["passed"] for r in g), n),
            pct(sum(r["c1"] for r in g), n), pct(sum(r["c3"] for r in g), n),
            pct(sum(r["c4"] for r in g), n), pct(sum(r["c5"] for r in g), n),
            "" if all(r["passed"] for r in g) else "   <-- fails"))


def explained_families():
    """Families named in the '## Oracle failures' section of CONFLICTS.md."""
    try:
        with open(CONFLICTS_MD, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return set()
    m = re.search(r"^## Oracle failures.*?(?=^## |\Z)", text, re.S | re.M)
    return set(re.findall(r"\b(?:SM|CL|CA|BR|SB)-[A-Z0-9-]+[A-Z0-9]\b", m.group(0))) if m else set()


def kit_integrity():
    man = load_json(os.path.join(KIT, "MANIFEST.json"))
    listed = set(man["files"])
    problems = []
    for name, meta in sorted(man["files"].items()):
        p = os.path.join(KIT, name)
        if not os.path.isfile(p):
            problems.append("missing: " + name)
            continue
        with open(p, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != meta["sha256"]:
                problems.append("modified: " + name)
    for dirpath, dirnames, filenames in os.walk(KIT):
        for fn in filenames:
            relp = os.path.relpath(os.path.join(dirpath, fn), KIT).replace(os.sep, "/")
            if relp != "MANIFEST.json" and relp not in listed:
                problems.append("extra file: " + relp)
        for d in dirnames:
            if d == "__pycache__":
                problems.append("bytecode dir: " + os.path.relpath(os.path.join(dirpath, d), KIT))
    return len(listed), problems


# ---------------------------------------------------------------------------
def main():
    vocab = load_vocab()
    facts_schema = load_json(FACTS_SCHEMA)
    with open(SITUATIONS_YAML, encoding="utf-8") as f:
        sits_doc = yaml.safe_load(f)
    sits = sits_doc["situations"]
    mapping, mapping_rows = load_mapping()
    cases = load_dev_cases()

    print("check_contracts: %s, %s, %s, %s" % (rel(SITUATIONS_YAML), rel(MAPPING_CSV), rel(FACTS_SCHEMA), rel(DECISION_SCHEMA)))
    print("vendor kit: %s (read-only)" % rel(KIT))

    # (a) ------------------------------------------------------------------
    header("(a) IDs against data/reference/ and contracts/facts.schema.json")
    unknown = []
    check_ids(sits_doc, mapping_rows, vocab, facts_schema, unknown)
    vendor, dec = check_schemas(vocab, facts_schema, unknown)
    n_rows = sum(1 for s in sits for a in AUDIENCES if s.get(a))
    counts = defaultdict(int)
    for s in sits:
        counts["when clauses"] += sum(len(alt) for alt in s["when"]["any_of"])
        for a in AUDIENCES:
            row = s[a]
            counts["actions"] += 1 + len(row["acceptable_actions"])
            counts["steps"] += len(row["required_steps"]) + len(row["optional_steps"])
            counts["question topics"] += len(row["decisive_fact"])
            counts["escalation targets"] += row["escalation_target"] is not None
            counts["signal paths"] += len(row["needs_consent"])
            counts["guidance ids"] += len(row["guidance_refs"])
    print("  %d situations, %d audience rows; checked %s" % (len(sits), n_rows, ", ".join("%d %s" % (v, k) for k, v in counts.items())))
    print("  decision.schema.json: %d vendor fields carried unchanged, vendor required %s kept, + trace" % (len(vendor["properties"]), vendor["required"]))
    print("  unknown IDs: %d" % len(unknown))
    for kind, val, where in unknown:
        print("    UNKNOWN %-28s %-40s in %s" % (kind, val, where))

    # (b) ------------------------------------------------------------------
    header("(b) every dev family/branch mapped")
    dev_pairs = defaultdict(int)
    for c in cases:
        dev_pairs[(c["scenario_family"], c["ground_truth"]["branch"])] += 1
    fams = {f for f, _ in dev_pairs}
    unmapped = sorted(p for p in dev_pairs if p not in mapping)
    stale = sorted(p for p in mapping if p not in dev_pairs)
    dup = len(mapping_rows) - len(mapping)
    print("  dev: %d cases, %d families, %d family/branch pairs; mapping rows: %d" % (len(cases), len(fams), len(dev_pairs), len(mapping_rows)))
    print("  unmapped families: %d" % len(unmapped))
    for f, b in unmapped:
        print("    UNMAPPED %s/%s (%d cases)" % (f, b, dev_pairs[(f, b)]))
    print("  mapping rows with no dev cases: %d; duplicate rows: %d" % (len(stale), dup))
    for f, b in stale:
        print("    STALE %s/%s" % (f, b))
    if unmapped:
        print("\n(c) skipped: map every family first.")
        return 1

    # (c) ------------------------------------------------------------------
    header("(c) DECISION-ORACLE CHECK -- diagnostic upper bound, NEVER used for submissions")
    print("  Each dev case answered from its mapped situation row; twins (single-turn) from the riskier")
    print("  branch's row plus its decisive question topics. Scored with dsakit.scoring.score_case.")
    print("  c1 = action acceptable, c3 = decisive question asked, c4 = handoff when required, c5 = risk within one step.")
    results, sample = oracle(cases, mapping, sits)
    n = len(results)
    passed = sum(r["passed"] for r in results)
    overall = pct(passed, n)
    print()
    print("  overall: %d/%d = %.1f%% pass c1+c3+c4+c5   (c1 %.1f%%, c3 %.1f%%, c4 %.1f%%, c5 %.1f%%)" % (
        passed, n, overall, pct(sum(r["c1"] for r in results), n), pct(sum(r["c3"] for r in results), n),
        pct(sum(r["c4"] for r in results), n), pct(sum(r["c5"] for r in results), n)))
    print()
    print("  by journey:")
    print_breakdown(results, "journey", "journey")
    print()
    print("  by family:")
    print_breakdown(results, "family", "family")
    failing = defaultdict(list)
    for r in results:
        if not r["passed"]:
            failing[r["family"]].append(r)
    print()
    print("  failing families: %d" % len(failing))
    for fam in sorted(failing):
        g = failing[fam]
        reasons = sorted({w for r in g for w in r["why"]})
        sits_used = sorted({"%s/%s" % (r["situation"], r["audience"]) for r in g})
        print("    %s: %d cases fail [%s] via %s" % (fam, len(g), "; ".join(reasons), ", ".join(sits_used)))
    explained = explained_families()
    unexplained = sorted(set(failing) - explained)
    print("  failing families not explained in CONFLICTS.md '## Oracle failures': %d %s" % (len(unexplained), unexplained or ""))

    # decision.schema round trip on one oracle answer
    header("(d) decision.schema round trip and vendor kit integrity")
    errs = full_schema_errors(dec, sample)
    if errs is None:
        print("  decision.schema.json: jsonschema not installed, full validation skipped")
    else:
        print("  oracle decision with trace valid against decision.schema.json: %s%s" % ("yes" if not errs else "NO", "" if not errs else " " + str(errs[:3])))
    stripped = copy.deepcopy(sample)
    stripped.pop("trace")
    with_trace = minischema.validate(sample, vendor)
    without = minischema.validate(stripped, vendor)
    print("  vendor submission.schema.json rejects it with trace: %s; accepts it after stripping trace: %s" % (
        "yes" if with_trace else "NO", "yes" if not without else "NO " + str(without[:3])))
    schema_ok = not errs and bool(with_trace) and not without
    n_files, problems = kit_integrity()
    print("  instructions/ kit vs MANIFEST.json: %d files, %d problems" % (n_files, len(problems)))
    for p in problems:
        print("    " + p)

    ok = not unknown and not unmapped and overall >= ORACLE_THRESHOLD and not unexplained and not problems and schema_ok
    header("summary")
    print("  unknown IDs: %d | unmapped families: %d | oracle: %.1f%% (threshold %.0f%%) | unexplained failing families: %d | schema round trip: %s | kit problems: %d" % (
        len(unknown), len(unmapped), overall, ORACLE_THRESHOLD, len(unexplained), "ok" if schema_ok else "FAIL", len(problems)))
    print("  failing oracle families: %d%s" % (len(failing), (" " + ", ".join(
        "%s (%d cases)" % (f, len(failing[f])) for f in sorted(failing))) if failing else ""))
    print("  RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

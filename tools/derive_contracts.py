"""Derive contracts/situations.yaml (and the generated part of contracts/CONFLICTS.md)
from contracts/family_to_situation.csv and the dev ground truth.

Hand-written here: situation names, 'when' conditions (in facts.schema.json terms),
match order and which fact each decisive question topic stands for. Everything
else in situations.yaml is computed from the ground_truth of the mapped dev cases
with the rules in DERIVATION_RULES. Re-run after changing the mapping:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/derive_contracts.py
"""
import sys

sys.dont_write_bytecode = True

import itertools
from collections import Counter, defaultdict

import yaml

from contracts_common import (AUDIENCES, CONFLICTS_MD, RISK, SITUATIONS_YAML, URGENCY, intervention,
                              is_twin, load_dev_cases, load_mapping, riskier_branches)

DERIVATION_RULES = {
    "population": "For each situation and audience: the dev cases whose (family, branch) maps to the situation in family_to_situation.csv, judged against their own branch's ground_truth.",
    "primary_action": "The action acceptable (primary or acceptable_actions) in the most cases; ties: most cases where it is the reference primary, then the primary of the highest-risk cases, then the higher intervention level.",
    "acceptable_actions": "Actions acceptable in every mapped case, minus primary_action.",
    "risk_level": "The level within one step (the scorer's tolerance) of the most cases; ties: most exact matches, then the higher level.",
    "urgency": "The most common reference urgency; ties: the more urgent.",
    "escalation_target": "Handoff if most cases require one (ties: handoff). Target: the one in the most cases' acceptable_targets; ties: most frequent reference target. null = no handoff.",
    "required_steps": "Steps required in at least half the cases (if none reaches half: the most frequently required step).",
    "optional_steps": "Steps listed (required or optional) in at least half the cases, plus, greedily, the required step that covers the most cases still left without one of their required steps, until every case has one in required_steps or optional_steps. Not already in required_steps.",
    "decisive_fact": "From the single-turn population (non-twin mapped cases plus both branches of every twin family whose riskier branch maps here, because single-turn answers twins from the riskier row): the smallest set of must-ask topics, at most three, that satisfies the most cases. On a twin's safer branch the fact is already settled, so it is not decisive there.",
    "needs_consent": "The necessary_signals set shared by the most cases; ties: the larger set.",
    "guidance_refs": "Refs cited in at least half the cases, then greedily the ref covering the most still-uncovered cases until every case shares at least one ref.",
    "missing_audience": "When a situation has no dev cases for an audience, that audience's row is a copy of the other audience's row, marked derived_from_audience, with dev_families empty. If the copied escalation target is business_security_support (defined for small businesses only) and the row is for consumers, the target becomes the most common other target acceptable in the source cases.",
}

UNKNOWN_FACT_POLICY = (
    "A fact that is absent or 'unknown' is treated as its riskier value when it is listed in the matched "
    "situation's decisive_fact: answer from the riskier situation's row and ask that decisive_fact's "
    "question_topic (single-turn), or ask it first and re-match (multi-turn). The 'when' clauses that test "
    "'== unknown' are exactly those cases."
)

# First match wins. More specific / more harmful situations first; genuine last.
MATCH_ORDER = ["S15", "S14", "S11", "S08", "S07", "S12", "S09", "S05", "S06", "S19", "S10",
               "S16", "S04", "S17", "S03", "S02", "S18", "S13", "S01"]

# question topic -> fact name (facts.schema.json); per-situation overrides below
TOPIC_FACT = {
    "card_details_entered": "card_details_entered", "credentials_entered": "credentials_entered",
    "code_shared": "code_shared", "money_transferred": "money_transferred", "payment_status": "money_transferred",
    "app_installed": "app_installed", "remote_access_given": "remote_access_given", "self_initiated": "self_initiated",
    "signal_lost": "service_lost", "password_reused": "password_reused", "device_behaviour": "device_compromise_signs",
    "user_safety": "user_safety_concern",
}
TOPIC_FACT_OVERRIDE = {("S12", "app_installed"): "attachment_content_enabled"}

SPEC = {
    "S01": ("Genuine contact or expected event", [
        ["appears_genuine == true", "lure_ask == none"],
        ["self_initiated == true"],
        ["verified_out_of_band == true"],
        ["breach_exposed_data == email_only", "breach_notice_genuine != false"],
    ]),
    "S02": ("Lure not acted on: small payment, card details or an attachment", [
        ["lure_ask in [small_payment, card_details]", "claimed_sender not in [bank, operator, tax_authority]", "card_details_entered != true"],
        ["lure_ask == open_attachment", "attachment_content_enabled == false"],
    ]),
    "S03": ("Lure not acted on: bank, ID or account credentials (or a bank/operator/authority impersonation)", [
        ["lure_ask in [bank_credentials, id_credentials, account_password]", "credentials_entered != true"],
        ["claimed_sender in [bank, operator, tax_authority]", "lure_ask in [small_payment, card_details]", "card_details_entered != true"],
    ]),
    "S04": ("Money or bank-detail change requested by a 'known' person, nothing paid", [
        ["lure_ask in [money_transfer, bank_detail_change]", "claimed_sender in [family_or_friend, executive, supplier]",
         "verified_out_of_band != true", "money_transferred in [false, unknown]"],
    ]),
    "S05": ("Card details, bank login or a bank code given away", [
        ["card_details_entered == true"],
        ["credentials_entered == true", "credential_type in [bank, national_id]"],
        ["code_shared == true", "claimed_sender not in [operator]"],
        ["link_opened == true", "lure_ask in [small_payment, card_details]", "card_details_entered == unknown"],
        ["contact_channel == call", "claimed_sender == bank", "lure_ask == one_time_code", "code_shared == unknown"],
    ]),
    "S06": ("Account password entered on a fake page", [
        ["credentials_entered == true", "credential_type in [email, work_account, other_account]"],
    ]),
    "S07": ("App or profile installed from a link", [
        ["app_installed == true", "remote_access_given != true"],
    ]),
    "S08": ("Remote access given to a stranger", [
        ["remote_access_given == true", "verified_out_of_band != true"],
    ]),
    "S09": ("SIM or number takeover signs", [
        ["sim_change_event == true", "self_initiated in [false, unknown]"],
        ["contact_channel == call", "claimed_sender == operator", "code_shared in [true, unknown]"],
        ["subscription_order_event == true", "self_initiated in [false, unknown]", "audience == small_business"],
    ]),
    "S10": ("Account takeover signs", [
        ["unrequested_mfa_prompts == true"],
        ["unknown_login == true", "self_initiated in [false, unknown]"],
        ["account_misuse_signs == true"],
        ["former_staff_access == true"],
    ]),
    "S11": ("Money already sent, or a payment that may already have gone", [
        ["money_transferred == true"],
        ["lure_ask == money_transfer", "claimed_sender == executive", "money_transferred == unknown"],
    ]),
    "S12": ("Device infected (small business)", [
        ["device_compromise_signs == true"],
        ["lure_ask == open_attachment", "attachment_content_enabled in [true, unknown]"],
    ]),
    "S13": ("Scam call, nothing given", [
        ["contact_channel == call", "appears_genuine in [false, unknown]", "code_shared != true",
         "remote_access_given != true", "money_transferred != true"],
    ]),
    "S14": ("Someone close may be monitoring the phone (safety first)", [
        ["monitoring_suspected == true"],
    ]),
    "S15": ("Out-of-scope request (trace or expose the scammer)", [
        ["out_of_scope_request == true"],
    ]),
    "S16": ("Genuine breach exposed a password that may be reused", [
        ["breach_exposed_data == password", "breach_notice_genuine == true"],
    ]),
    "S17": ("Investment or 'too good to be true' offer", [
        ["lure_ask == investment", "money_transferred != true"],
    ]),
    "S18": ("Unexpected call claiming to be your real bank, nothing asked", [
        ["contact_channel == call", "claimed_sender == bank", "lure_ask == none",
         "code_shared != true", "remote_access_given != true", "money_transferred != true"],
    ]),
    "S19": ("Business mailbox compromised and used against customers", [
        ["account_used_against_others == true"],
    ]),
}


# ---------------------------------------------------------------------------
def acceptable(gt):
    return {gt["primary_action"]} | set(gt["acceptable_actions"])


def fam_label(c):
    return "%s/%s" % (c["scenario_family"], c["ground_truth"]["branch"])


def by_label(cases, pred):
    """Counter of family/branch labels for cases where pred(case) is true."""
    return Counter(fam_label(c) for c in cases if pred(c))


def choose_action(cases, interv):
    cands = sorted(set().union(*(acceptable(c["ground_truth"]) for c in cases)))
    top = max(RISK.index(c["ground_truth"]["risk_level"]) for c in cases)

    def key(a):
        return (sum(a in acceptable(c["ground_truth"]) for c in cases),
                sum(c["ground_truth"]["primary_action"] == a for c in cases),
                sum(c["ground_truth"]["primary_action"] == a for c in cases if RISK.index(c["ground_truth"]["risk_level"]) == top),
                interv[a])
    return max(cands, key=key)


def choose_risk(cases):
    def key(i):
        return (sum(abs(i - RISK.index(c["ground_truth"]["risk_level"])) <= 1 for c in cases),
                sum(i == RISK.index(c["ground_truth"]["risk_level"]) for c in cases), i)
    return RISK[max(range(len(RISK)), key=key)]


def choose_urgency(cases):
    cnt = Counter(c["ground_truth"]["urgency"] for c in cases)
    return max(cnt, key=lambda u: (cnt[u], URGENCY.index(u)))


def choose_escalation(cases):
    req = sum(c["ground_truth"]["escalation"]["required"] is True for c in cases)
    if req * 2 < len(cases):
        return None
    esc = [c for c in cases if c["ground_truth"]["escalation"]["required"] is True]
    cands = sorted(set().union(*(c["ground_truth"]["escalation"]["acceptable_targets"] for c in esc)))
    return max(cands, key=lambda t: (sum(t in c["ground_truth"]["escalation"]["acceptable_targets"] for c in esc),
                                     sum(c["ground_truth"]["escalation"]["target"] == t for c in esc), t))


def majority_then_cover(cases, get):
    """Items in >= half the cases, then greedy cover so every case shares >= 1 item."""
    n = len(cases)
    freq = Counter(x for c in cases for x in set(get(c)))
    chosen = [x for x, k in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])) if 2 * k >= n]
    while True:
        uncovered = [c for c in cases if get(c) and not (set(get(c)) & set(chosen))]
        if not uncovered:
            return chosen
        cnt = Counter(x for c in uncovered for x in set(get(c)))
        chosen.append(max(sorted(cnt), key=lambda x: (cnt[x], freq[x])))


def choose_required(cases):
    n = len(cases)
    freq = Counter(x for c in cases for x in set(c["ground_truth"]["required_steps"]))
    ranked = [x for x, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))]
    return [x for x in ranked if 2 * freq[x] >= n] or ranked[:1]


def choose_optional(cases, required):
    n = len(cases)
    freq = Counter(x for c in cases for x in set(c["ground_truth"]["required_steps"]) | set(c["ground_truth"]["optional_steps"]))
    opt = [x for x, k in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])) if 2 * k >= n and x not in required]
    while True:
        have = set(required) | set(opt)
        left = [c for c in cases if c["ground_truth"]["required_steps"] and not (set(c["ground_truth"]["required_steps"]) & have)]
        if not left:
            return opt
        cnt = Counter(x for c in left for x in c["ground_truth"]["required_steps"])
        opt.append(max(sorted(cnt), key=lambda x: cnt[x]))


def choose_decisive(st_cases):
    cands = sorted(set(t for c in st_cases for t in c["ground_truth"]["must_ask_topics"]))
    best, best_key = (), None
    for k in range(0, min(3, len(cands)) + 1):
        for combo in itertools.combinations(cands, k):
            s = set(combo)
            sat = sum((not c["ground_truth"]["must_ask_topics"]) or bool(s & set(c["ground_truth"]["must_ask_topics"])) for c in st_cases)
            key = (sat, -k)
            if best_key is None or key > best_key:
                best, best_key = combo, key
    freq = Counter(t for c in st_cases for t in c["ground_truth"]["must_ask_topics"])
    return sorted(best, key=lambda t: (-freq[t], t))


def choose_consent(cases):
    cnt = Counter(tuple(sorted(c["ground_truth"]["necessary_signals"])) for c in cases)
    return list(max(cnt, key=lambda s: (cnt[s], len(s), s)))


def derive_row(sid, cases, st_cases, interv):
    primary = choose_action(cases, interv)
    common = set.intersection(*(acceptable(c["ground_truth"]) for c in cases))
    req = choose_required(cases)
    topics = choose_decisive(st_cases) if st_cases else []
    fams = Counter((c["scenario_family"], c["ground_truth"]["branch"]) for c in cases)
    return {
        "primary_action": primary,
        "acceptable_actions": sorted(common - {primary}),
        "risk_level": choose_risk(cases),
        "urgency": choose_urgency(cases),
        "escalation_target": choose_escalation(cases),
        "required_steps": req,
        "optional_steps": choose_optional(cases, req),
        "decisive_fact": [{"fact": TOPIC_FACT_OVERRIDE.get((sid, t), TOPIC_FACT[t]), "question_topic": t} for t in topics],
        "needs_consent": choose_consent(cases),
        "guidance_refs": majority_then_cover(cases, lambda c: c["ground_truth"]["guidance_refs"]),
        "dev_families": [{"family": f, "branch": b, "cases": n} for (f, b), n in sorted(fams.items())],
        "dev_cases": len(cases),
    }


# --- disagreements --------------------------------------------------------------
def disagreements(sid, aud, row, cases, st_cases):
    out = []

    def add(field, chosen, counter, what):
        for lab, n in sorted(counter.items()):
            out.append((sid, aud, field, chosen, lab, n, what(lab)))

    gts = {fam_label(c): c["ground_truth"] for c in cases}
    pa = row["primary_action"]
    add("primary_action", pa, by_label(cases, lambda c: pa not in acceptable(c["ground_truth"])),
        lambda l: "acceptable: " + ", ".join(sorted(acceptable(gts[l]))) + " (oracle FAIL cond 1)")
    add("primary_action", pa, by_label(cases, lambda c: pa in acceptable(c["ground_truth"]) and c["ground_truth"]["primary_action"] != pa),
        lambda l: "reference primary %s; chosen value is one of its acceptable actions" % gts[l]["primary_action"])
    ri = RISK.index(row["risk_level"])
    add("risk_level", row["risk_level"], by_label(cases, lambda c: RISK.index(c["ground_truth"]["risk_level"]) != ri),
        lambda l: "reference %s%s" % (gts[l]["risk_level"], " (outside one step: oracle FAIL cond 5)" if abs(RISK.index(gts[l]["risk_level"]) - ri) > 1 else " (within one step)"))
    add("urgency", row["urgency"], by_label(cases, lambda c: c["ground_truth"]["urgency"] != row["urgency"]),
        lambda l: "reference %s" % gts[l]["urgency"])
    tgt = row["escalation_target"]
    add("escalation_target", tgt, by_label(cases, lambda c: c["ground_truth"]["escalation"]["required"] != (tgt is not None)),
        lambda l: "reference handoff required=%s target=%s%s" % (gts[l]["escalation"]["required"], gts[l]["escalation"]["target"],
                                                                 " (missed handoff: oracle FAIL cond 4)" if gts[l]["escalation"]["required"] else " (over-escalation; does not fail the pass rule)"))
    if tgt:
        add("escalation_target", tgt, by_label(cases, lambda c: c["ground_truth"]["escalation"]["required"] and tgt not in c["ground_truth"]["escalation"]["acceptable_targets"]),
            lambda l: "acceptable targets: " + ", ".join(gts[l]["escalation"]["acceptable_targets"]))
    rs = set(row["required_steps"])
    add("required_steps", row["required_steps"], by_label(cases, lambda c: set(c["ground_truth"]["required_steps"]) != rs),
        lambda l: "reference required: " + ", ".join(gts[l]["required_steps"]))
    nc = set(row["needs_consent"])
    add("needs_consent", row["needs_consent"], by_label(cases, lambda c: set(c["ground_truth"]["necessary_signals"]) != nc),
        lambda l: "reference necessary_signals: " + (", ".join(gts[l]["necessary_signals"]) or "none"))
    dt = set(d["question_topic"] for d in row["decisive_fact"])
    st_gt = {fam_label(c): c["ground_truth"] for c in st_cases}
    add("decisive_fact", sorted(dt), by_label(st_cases, lambda c: c["ground_truth"]["must_ask_topics"] and not (set(c["ground_truth"]["must_ask_topics"]) & dt)),
        lambda l: "must ask: " + ", ".join(st_gt[l]["must_ask_topics"]) + " (oracle FAIL cond 3)")
    return out


def main():
    cases = load_dev_cases()
    mapping, _ = load_mapping()
    interv = intervention()
    risky = riskier_branches(cases)
    pop = defaultdict(list)       # (sid, aud) -> cases (multi-turn view)
    st_pop = defaultdict(list)    # (sid, aud) -> cases answered from this row in single-turn
    for c in cases:
        fam, br = c["scenario_family"], c["ground_truth"]["branch"]
        sid = mapping[(fam, br)]
        pop[(sid, c["audience"])].append(c)
        st_sid = mapping[(fam, risky[fam])] if is_twin(c) else sid
        st_pop[(st_sid, c["audience"])].append(c)

    situations, conflicts = [], []
    for sid in sorted(SPEC):
        name, when = SPEC[sid]
        entry = {"id": sid, "name": name, "when": {"any_of": when}}
        rows = {}
        for aud in AUDIENCES:
            if pop[(sid, aud)]:
                rows[aud] = derive_row(sid, pop[(sid, aud)], st_pop[(sid, aud)], interv)
                conflicts += disagreements(sid, aud, rows[aud], pop[(sid, aud)], st_pop[(sid, aud)])
        for aud in AUDIENCES:
            if aud not in rows:
                other = [a for a in AUDIENCES if a != aud][0]
                rows[aud] = dict(rows[other], derived_from_audience=other, dev_families=[], dev_cases=0)
                if aud == "consumer" and rows[aud]["escalation_target"] == "business_security_support":
                    src = [c for c in pop[(sid, other)] if c["ground_truth"]["escalation"]["required"]]
                    alt = Counter(t for c in src for t in c["ground_truth"]["escalation"]["acceptable_targets"] if t != "business_security_support")
                    rows[aud]["escalation_target"] = max(sorted(alt), key=lambda t: alt[t]) if alt else None
                conflicts.append((sid, aud, "(whole row)", "copy of %s" % other, "-", 0, "no %s dev cases for this situation" % aud))
        entry.update(rows)
        situations.append(entry)

    doc = {
        "version": "1.0.0",
        "generated_by": "tools/derive_contracts.py (do not edit by hand; edit the script or family_to_situation.csv and re-run)",
        "source": "instructions/DNA_Digital_Security_Assistant_SimSet_v2.0.1/data/dev/cases.jsonl ground_truth",
        "condition_syntax": "when.any_of is a list of alternatives; each alternative is a list of clauses that must all hold. Clause: '<fact> == v', '<fact> != v', '<fact> in [a, b]', '<fact> not in [a, b]'. Facts and values come from contracts/facts.schema.json; an absent fact is 'unknown'.",
        "match_order": MATCH_ORDER,
        "unknown_fact_policy": UNKNOWN_FACT_POLICY,
        "derivation_rules": DERIVATION_RULES,
        "situations": situations,
    }
    with open(SITUATIONS_YAML, "w", encoding="utf-8") as f:
        f.write("# Situation contracts. Generated by tools/derive_contracts.py from the dev ground truth.\n")
        f.write("# Field semantics and derivation rules are in 'derivation_rules' below and in CONFLICTS.md.\n")
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=120)
    write_conflicts(conflicts)
    print("wrote %s (%d situations) and the generated section of %s (%d disagreement rows)" % (
        SITUATIONS_YAML, len(situations), CONFLICTS_MD, len(conflicts)))


BEGIN, END = "<!-- BEGIN GENERATED: tools/derive_contracts.py -->", "<!-- END GENERATED -->"


def write_conflicts(rows):
    lines = [BEGIN, "", "| Situation | Audience | Field | Chosen value | Disagreeing family/branch | Cases | What that family has |",
             "|---|---|---|---|---|---|---|"]
    for sid, aud, field, chosen, lab, n, what in rows:
        ch = ", ".join(chosen) if isinstance(chosen, list) else ("null" if chosen is None else str(chosen))
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (sid, aud, field, ch or "(none)", lab, n, what))
    lines += ["", END]
    block = "\n".join(lines)
    try:
        with open(CONFLICTS_MD, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        text = "# Contract conflicts\n\n## Field-level disagreements (generated)\n\n%s\n%s\n" % (BEGIN, END)
    if BEGIN not in text:
        text += "\n## Field-level disagreements (generated)\n\n%s\n%s\n" % (BEGIN, END)
    pre, rest = text.split(BEGIN, 1)
    post = rest.split(END, 1)[1]
    with open(CONFLICTS_MD, "w", encoding="utf-8") as f:
        f.write(pre + block + post)


if __name__ == "__main__":
    main()

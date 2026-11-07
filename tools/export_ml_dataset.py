"""Export dev and test cases to CSV for ML situation classification.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/export_ml_dataset.py

Outputs:
    analysis/ml/dev.csv   - labelled (with situation_id, family for GroupKFold, branch)
    analysis/ml/test.csv  - unlabelled (no ground truth columns)

Each row = one case. Columns:
    * id / case_id         - case identifier (e.g. DSA-D-0001)
    * raw_user_text        - raw user message text (primary text feature)
    * opening_message      - raw user message text (alias)
    * metadata             - audience, journey, language, locale, entry_point, user_identified
    * all 14 signals       - full JSON payloads for all 14 signals in signal_dictionary.json
    * key signal fields    - convenience tabular features (artifact_type, sender, body, link_verdict, etc.)
    * keyword facts (kw_*) - output of dsa.facts_keyword.extract_facts (all facts from facts.schema.json)
    * keyword_situation_id - situation predicted by the keyword baseline policy
    * situation_id         - ground truth label S01..S19 (dev only)
    * family               - scenario_family; the GroupKFold key (dev only)
    * branch               - ground_truth branch; informational only, NOT a
                             grouping key (dev only)

Features (signals, kw_*, keyword_situation_id) are computed from a copy of the
case with every dev-only field removed, so dev rows see exactly what test rows
see. Labels are read from the original case afterwards (tools/ diagnostic use).

The run aborts (AssertionError) if the keyword policy raised on any case or any
dev (family, branch) pair is missing from contracts/family_to_situation.csv.
"""
import collections
import csv
import json
import os
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import facts_keyword, kit, policy  # noqa: E402

# Dev-only fields (CLAUDE.md). Removed before any feature is computed.
DEV_ONLY_FIELDS = (
    "ground_truth", "simulation", "scenario_family", "title", "tags",
    "difficulty", "holdout_family",
)

# Run counters; main() asserts the error counters are 0.
STATS = collections.Counter()

# ---- 14 Signals from the vendor data/reference/signal_dictionary.json -------

SIGNAL_PATHS = [
    "artifact",
    "link_check",
    "call_warning",
    "user_call_notes",
    "subscription.products",
    "subscription.recent_events",
    "subscription.network_status",
    "device.summary",
    "device.recent_app_installs",
    "device.security_findings",
    "operator_account.recent_logins",
    "credential_exposure",
    "business.profile",
    "business.staff_accounts",
]

# Column name in CSV for each signal path
SIGNAL_COLS = ["signal_" + p.replace(".", "_") for p in SIGNAL_PATHS]

# Convenience parsed signal fields
CONVENIENCE_SIGNAL_COLS = [
    "artifact_type",
    "artifact_sender",
    "artifact_body",
    "artifact_has_links",
    "link_verdict",
    "call_warning",
]

# ---- Keyword Fact Extractor Schema (contracts/facts.schema.json) -------------

FACT_SCHEMA_PROPS = [
    "contact_channel",
    "claimed_sender",
    "lure_ask",
    "appears_genuine",
    "verified_out_of_band",
    "ai_instruction_in_content",
    "link_verdict",
    "call_warning_shown",
    "link_opened",
    "card_details_entered",
    "credentials_entered",
    "credential_type",
    "code_shared",
    "app_installed",
    "remote_access_given",
    "attachment_content_enabled",
    "money_transferred",
    "self_initiated",
    "password_reused",
    "sim_change_event",
    "service_lost",
    "subscription_order_event",
    "unknown_login",
    "unrequested_mfa_prompts",
    "account_misuse_signs",
    "account_used_against_others",
    "former_staff_access",
    "breach_exposed_data",
    "breach_notice_genuine",
    "device_compromise_signs",
    "monitoring_suspected",
    "user_safety_concern",
    "out_of_scope_request",
]

KW_FACT_COLS = ["kw_" + f for f in FACT_SCHEMA_PROPS]

# Keep the hard-coded lists in sync with their sources.
assert SIGNAL_PATHS == list(kit.ref("signal_dictionary.json")["signals"]), "SIGNAL_PATHS out of sync"
assert FACT_SCHEMA_PROPS == [
    p for p in kit.contract_json("facts.schema.json")["properties"] if p not in ("audience", "journey")
], "FACT_SCHEMA_PROPS out of sync with contracts/facts.schema.json"

# Metadata columns
META_COLS = [
    "id",
    "case_id",
    "raw_user_text",
    "opening_message",
    "audience",
    "journey",
    "language",
    "locale",
    "entry_point",
    "user_identified",
]

# Labels (dev only)
LABEL_COLS = ["situation_id", "family", "branch"]


def _get_signal_node(case, path):
    """Retrieve the raw object at a dotted signal path from case['signals']."""
    node = case.get("signals") or {}
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _fact_value(facts, name):
    """Extract the scalar value from a facts dict entry, or 'unknown'."""
    rec = facts.get(name)
    if rec is None:
        return "unknown"
    v = rec["value"]
    if v is True:
        return "true"
    if v is False:
        return "false"
    return str(v) if v is not None else "unknown"


def _keyword_situation(case, text_facts):
    """Run the keyword fact extractor through policy to get baseline situation."""
    try:
        d = policy.decide(case, text_facts)
        return d["res"]["final"]["situation"]
    except Exception as e:  # counted; main() fails the run
        STATS["policy_errors"] += 1
        print(f"policy error on {case.get('case_id')}: {type(e).__name__}: {e}", file=sys.stderr)
        return "unknown"


def _load_family_map():
    """Load contracts/family_to_situation.csv -> {(family, branch): situation_id}."""
    path = os.path.join(kit.CONTRACTS, "family_to_situation.csv")
    fmap = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["family"], row["branch"])
            fmap[key] = row["situation_id"]
    return fmap


_FAMILY_MAP = None


def _lookup_situation(family, branch):
    global _FAMILY_MAP
    if _FAMILY_MAP is None:
        _FAMILY_MAP = _load_family_map()
    sit = _FAMILY_MAP.get((family, branch))
    if sit is None:
        STATS["unknown_labels"] += 1
        print(f"no situation for family={family!r} branch={branch!r}", file=sys.stderr)
        return "unknown"
    return sit


def _strip_dev_only(case):
    """Shallow copy of case without dev-only fields (features must not see them)."""
    return {k: v for k, v in case.items() if k not in DEV_ONLY_FIELDS}


def export_split(cases, out_path, include_labels=True):
    """Export cases to CSV with all signals, keyword facts, and metadata."""
    header = list(META_COLS)
    header += SIGNAL_COLS
    header += CONVENIENCE_SIGNAL_COLS
    header += KW_FACT_COLS
    header.append("keyword_situation_id")
    if include_labels:
        header += LABEL_COLS

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    count = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for orig in cases:
            case = _strip_dev_only(orig)
            cid = case["case_id"]
            user_text = case.get("opening_message", "")
            text_facts = facts_keyword.extract_facts(case)
            kw_sit = _keyword_situation(case, text_facts)

            # Metadata
            row = [
                cid,
                cid,
                user_text,
                user_text,
                case.get("audience", ""),
                case.get("journey", ""),
                case.get("language", ""),
                case.get("locale", ""),
                case.get("entry_point", ""),
                str(case.get("user_identified", "")),
            ]

            # All 14 Signals (full JSON payload or empty string)
            for path in SIGNAL_PATHS:
                val = _get_signal_node(case, path)
                row.append(json.dumps(val, ensure_ascii=False) if val is not None else "")

            # Convenience signal columns
            art = case.get("signals", {}).get("artifact") or {}
            lc = case.get("signals", {}).get("link_check") or {}
            cw = case.get("signals", {}).get("call_warning") or {}

            row.append(art.get("type", ""))
            row.append(art.get("sender", ""))
            row.append(art.get("body", ""))
            row.append(1 if art.get("links") else 0)
            row.append(lc.get("verdict", "not_checked") if lc else "not_checked")
            row.append(cw.get("warning", "none") if cw else "none")

            # Keyword extracted facts
            for fname in FACT_SCHEMA_PROPS:
                row.append(_fact_value(text_facts, fname))

            # Baseline situation from keyword pipeline
            row.append(kw_sit)

            # Labels (dev only)
            if include_labels:
                gt = orig.get("ground_truth") or {}
                fam = orig.get("scenario_family", "")
                branch = gt.get("branch") or "main"
                sit_id = _lookup_situation(fam, branch)
                row += [sit_id, fam, branch]

            writer.writerow(row)
            count += 1
    return count


def main():
    import time

    t0 = time.time()
    ml_dir = os.path.join(ROOT, "analysis", "ml")
    os.makedirs(ml_dir, exist_ok=True)

    # Dev split (labelled)
    dev_cases = kit.load_dev_cases()
    dev_path = os.path.join(ml_dir, "dev.csv")
    n_dev = export_split(dev_cases, dev_path, include_labels=True)

    # Test split (unlabelled)
    test_cases = kit.load_test_inputs()
    test_path = os.path.join(ml_dir, "test.csv")
    n_test = export_split(test_cases, test_path, include_labels=False)

    elapsed = time.time() - t0
    print(f"STATS: policy_errors={STATS['policy_errors']} unknown_labels={STATS['unknown_labels']}")
    assert STATS["policy_errors"] == 0, f"{STATS['policy_errors']} policy errors"
    assert STATS["unknown_labels"] == 0, f"{STATS['unknown_labels']} unknown labels"
    print(f"Exported {n_dev} dev cases -> {os.path.relpath(dev_path, ROOT)}")
    print(f"Exported {n_test} test cases -> {os.path.relpath(test_path, ROOT)}")
    print(f"Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()

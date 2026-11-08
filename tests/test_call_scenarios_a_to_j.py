# -*- coding: utf-8 -*-
"""Comprehensive tests for Call Scenarios A through J and credential-request classifications.

Verifies:
1. "I got a call asking for password. Check it yourself." -> SUSPICIOUS_OR_MALICIOUS (never BENIGN)
2. Scenarios A through J:
   A. "I got a call asking for my password." -> SUSPICIOUS_OR_MALICIOUS
   B. "The bank employee asked me to tell him my OTP." -> SUSPICIOUS_OR_MALICIOUS
   C. "Someone from my bank asked for my card PIN." -> SUSPICIOUS_OR_MALICIOUS
   D. "The caller said my account would be blocked unless I shared my password." -> SUSPICIOUS_OR_MALICIOUS
   E. "The caller asked me to approve an MFA notification that I did not initiate." -> SUSPICIOUS_OR_MALICIOUS
   F. "The bank called to inform me about a transaction but did not ask for credentials." -> INCONCLUSIVE / BENIGN
   G. "The caller claims to be a bank employee and asks me to open my bank's official app myself." -> INCONCLUSIVE / BENIGN
   H. "I received an automated bank notification about a transaction." -> INCONCLUSIVE / BENIGN
   I. "The caller knows my name and account details and asks for my OTP." -> SUSPICIOUS_OR_MALICIOUS
   J. "I received a call asking me to install a remote-access application to fix my banking problem." -> SUSPICIOUS_OR_MALICIOUS
3. Presence of the 5 required actionable advice points for credential-theft calls.
"""
from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.intelligence.banking_validator import BankingValidator
from src.intelligence.security_analyzer import SecurityAnalyzer
from src.api.routes_analysis import handle_classify_sms, handle_analyze_request


def run_tests():
    bv = BankingValidator()
    sa = SecurityAnalyzer()
    
    total = 0
    passed = 0
    failed = []

    def check(name, condition, err_msg=""):
        nonlocal total, passed
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed.append((name, err_msg))
            print(f"  [FAIL] {name}: {err_msg}")

    print("==========================================")
    print("RUNNING CALL SCENARIOS A-J & CREDENTIAL TESTS")
    print("==========================================")

    # 1. Reported bug: "I got a call asking for password. Check it yourself."
    q_bug = "I got a call asking for password. Check it yourself."
    res_bug = sa.analyze(q_bug, channel="chat")
    check(
        "Reported bug: Password call not BENIGN",
        res_bug["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and res_bug["risk_level"] in ("critical", "high"),
        f"got outcome={res_bug.get('outcome_type')}, risk={res_bug.get('risk_level')}"
    )
    steps = res_bug.get("steps", [])
    combined_steps = " ".join(steps).lower()
    check(
        "Reported bug: Includes 5 actionable points",
        len(steps) >= 5 and "do not share your password" in combined_steps and "end the call" in combined_steps,
        f"steps count={len(steps)}"
    )

    # 2. Scenario A: "I got a call asking for my password."
    res_a = sa.analyze("I got a call asking for my password.", channel="call")
    check(
        "Scenario A: Asking for password -> SUSPICIOUS_OR_MALICIOUS",
        res_a["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and res_a["risk_level"] == "critical",
        f"got {res_a.get('outcome_type')}"
    )

    # 3. Scenario B: "The bank employee asked me to tell him my OTP."
    res_b = sa.analyze("The bank employee asked me to tell him my OTP.", channel="call")
    check(
        "Scenario B: Asking for OTP -> SUSPICIOUS_OR_MALICIOUS",
        res_b["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and res_b["risk_level"] == "critical",
        f"got {res_b.get('outcome_type')}"
    )

    # 4. Scenario C: "Someone from my bank asked for my card PIN."
    res_c = sa.analyze("Someone from my bank asked for my card PIN.", channel="call")
    check(
        "Scenario C: Asking for card PIN -> SUSPICIOUS_OR_MALICIOUS",
        res_c["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and res_c["risk_level"] == "critical",
        f"got {res_c.get('outcome_type')}"
    )

    # 5. Scenario D: "The caller said my account would be blocked unless I shared my password."
    res_d = sa.analyze("The caller said my account would be blocked unless I shared my password.", channel="call")
    check(
        "Scenario D: Account block threat -> SUSPICIOUS_OR_MALICIOUS",
        res_d["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and res_d["risk_level"] == "critical",
        f"got {res_d.get('outcome_type')}"
    )

    # 6. Scenario E: "The caller asked me to approve an MFA notification that I did not initiate."
    res_e = sa.analyze("The caller asked me to approve an MFA notification that I did not initiate.", channel="call")
    check(
        "Scenario E: Unsolicited MFA approval -> SUSPICIOUS_OR_MALICIOUS",
        res_e["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and res_e["risk_level"] == "critical",
        f"got {res_e.get('outcome_type')}"
    )

    # 7. Scenario F: "The bank called to inform me about a transaction but did not ask for credentials."
    res_f = sa.analyze("The bank called to inform me about a transaction but did not ask for credentials.", channel="call")
    check(
        "Scenario F: Transaction notice without credential request -> INCONCLUSIVE/BENIGN",
        res_f["outcome_type"] in ("INCONCLUSIVE", "BENIGN"),
        f"got {res_f.get('outcome_type')}"
    )

    # 8. Scenario G: "The caller claims to be a bank employee and asks me to open my bank's official app myself."
    res_g = sa.analyze("The caller claims to be a bank employee and asks me to open my bank's official app myself.", channel="call")
    check(
        "Scenario G: Claims employee, open own app -> INCONCLUSIVE/BENIGN",
        res_g["outcome_type"] in ("INCONCLUSIVE", "BENIGN"),
        f"got {res_g.get('outcome_type')}"
    )

    # 9. Scenario H: "I received an automated bank notification about a transaction."
    res_h = sa.analyze("I received an automated bank notification about a transaction.", channel="sms")
    check(
        "Scenario H: Automated bank transaction notice -> INCONCLUSIVE/BENIGN",
        res_h["outcome_type"] in ("INCONCLUSIVE", "BENIGN"),
        f"got {res_h.get('outcome_type')}"
    )

    # 10. Scenario I: "The caller knows my name and account details and asks for my OTP."
    res_i = sa.analyze("The caller knows my name and account details and asks for my OTP.", channel="call")
    check(
        "Scenario I: Caller knows details and asks for OTP -> SUSPICIOUS_OR_MALICIOUS",
        res_i["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and res_i["risk_level"] == "critical",
        f"got {res_i.get('outcome_type')}"
    )

    # 11. Scenario J: "I received a call asking me to install a remote-access application to fix my banking problem."
    res_j = sa.analyze("I received a call asking me to install a remote-access application to fix my banking problem.", channel="call")
    check(
        "Scenario J: Remote-access install demand -> SUSPICIOUS_OR_MALICIOUS",
        res_j["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and res_j["risk_level"] == "critical",
        f"got {res_j.get('outcome_type')}"
    )

    # 12. handle_classify_sms endpoint
    sms_res = handle_classify_sms({"message": "I got a call asking for password. Check it yourself.", "mode": "sms"})
    check(
        "handle_classify_sms endpoint -> SCAM & critical",
        sms_res["outcome_type"] == "SUSPICIOUS_OR_MALICIOUS" and sms_res["stage"] == "scam",
        f"got outcome={sms_res.get('outcome_type')}, stage={sms_res.get('stage')}"
    )

    # 13. handle_analyze_request live call endpoint
    call_req = {
        "kind": "call",
        "text": "Can you give me your password so that I can check whether your bank account is valid?",
        "transcript_so_far": "Good afternoon, this is Mikko from Revontuli Bank.",
        "sender": "+358 9 000 9811",
        "sender_identity_verified": False,
    }
    call_res = handle_analyze_request(call_req)
    check(
        "handle_analyze_request endpoint -> stage: scam & flagged phrases",
        call_res["stage"] == "scam" and len(call_res["flagged_phrases"]) > 0,
        f"got stage={call_res.get('stage')}, flagged={call_res.get('flagged_phrases')}"
    )

    print("\n==========================================")
    print(f"TEST RESULTS: {passed} / {total} PASSED ({(passed/total)*100:.1f}%)")
    print("==========================================")
    if failed:
        print("\nFailed tests:")
        for name, err in failed:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("\nALL SCENARIOS A THROUGH J PASSED WITH 100% SUCCESS!")


if __name__ == "__main__":
    run_tests()

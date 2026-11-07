# Contract conflicts

Where the dev families mapped to one situation disagree, `situations.yaml` holds the value that satisfies the most cases. The rule for each field is in `situations.yaml → derivation_rules`. This file records:

1. changes from the team draft,
2. every family that fails the decision-oracle check, with the reason,
3. other judgement calls worth a second look,
4. every field-level disagreement (generated).

Regenerate with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/derive_contracts.py`, then check with `tools/check_contracts.py`.

## Changes from the draft

| Draft | Contract | Evidence in dev ground truth |
|---|---|---|
| S02 includes the tax refund | `SM-TAX-REFUND` → **S03** | The email asks for the bank login. Reference risk is `high` and `credentials_entered` is a relevant topic, which fits the draft's own S03 description ("bank/ID credentials"). The dataset's rule (README, *Limits*) gives `high` when a lure targets bank credentials. |
| S03 includes streaming | `SM-STREAMING-EXPIRED` → **S02** | The email asks the user to update their card. Reference risk is `medium` and `card_details_entered` is the relevant topic, which fits the draft's own S02 description ("small payment or card"). |
| `SB-ATTACHMENT-TWIN` / `did_not_enable` not placed | → **S02** | Its reference answer (`do_not_interact_and_delete`, `medium`, no handoff) is S02's row. S02 is renamed "Lure not acted on: small payment, card details or an attachment". In single-turn the family is answered from its riskier branch (S12), so this placement only matters in multi-turn. |
| S13 includes the genuine bank call | S13 split: **S13** "Scam call, nothing given" and **S18** "Unexpected call claiming to be your real bank, nothing asked" (`CA-GENUINE-BANK-CALL`) | `CA-TECH-SUPPORT` accepts only `do_not_interact_and_delete` / `no_action_needed`; `CA-GENUINE-BANK-CALL` accepts only `verify_via_official_channel` / `contact_bank_and_block_cards`. No single row could pass both (8 tech-support cases failed the oracle before the split). |
| S10 includes the compromised business mailbox | `SB-MAILBOX-COMPROMISED` → **S19** "Business mailbox compromised and used against customers", handoff `business_security_support` | It is the only S10 family that requires a handoff (12 of 31 small-business cases). Before the split, the 12 cases failed condition 4; forcing the handoff on all of S10 would have added 19 escalation false positives. New fact `account_used_against_others` identifies it; S19 is matched before S10. |
| S01 = "11 benign families, verified supplier, old email-only breach" | Same 12 non-twin families plus the 3 twin branches | The dataset flags `BR-BREACH-EMAIL-ONLY` as one of its 11 benign controls. `SB-SUPPLIER-VERIFIED` is not flagged benign: its risk is `low`. |
| one decisive fact per situation | `decisive_fact` is a **list** of `{fact, question_topic}` | S05/consumer has two twin families that hinge on different facts: card entered (`CL-PARCEL-PAID-TWIN`) and code given (`CA-BANK-IMPOSTOR-TWIN`). S09/consumer has the same problem: SIM change self-initiated (`BR-SIM-SWAP-TWIN`) and code given (`CA-OPERATOR-SIM-CODE-TWIN`). One topic fails one of the two families in each pair. Two topics stay under the three-topic "fishing" limit. |
| "escalation target or null" | `escalation_target: null` means no handoff | `escalation_required` in a decision is `escalation_target is not null`. |

Situation IDs S01–S17 are unchanged; the splits add S18 and S19 so existing references stay valid.

## Oracle failures

Decision-oracle check (diagnostic only; never used for submissions): **588/588 = 100.0 %** pass conditions 1+3+4+5. No family fails.

Before the S13 and S10 splits it was 568/588 = 96.6 %: `CA-TECH-SUPPORT` (8 consumer cases, condition 1) and `SB-MAILBOX-COMPROMISED` (12 cases, condition 4). Both are fixed by the splits in the table above.

The oracle answers every case from its correct situation, so it measures how much the situation rows lose, not how well an assistant classifies. 100 % here is an upper bound, not a prediction.

## Other judgement calls

- **S03 / consumer risk is `medium`, although 42 of 66 cases are `high`.** `medium` is the only level within one step of every case, because `BR-UNREQUESTED-RESET` is `low`. `high` would fail those 12 on condition 5. The cost is that exact-risk calibration is off for the bank-lure families. Moving `BR-UNREQUESTED-RESET` and `BR-FAKE-BREACH-NOTICE` (`medium`) into their own situation would let S03 be `high`.
- **S13 risk is `medium` for both audiences** for the same reason. Consumer families span `low` (tech support) to `high` (bank-impostor no_codes); small-business families span `low` (tech support) to `high` (terminal support, bank-impostor no_codes).
- **S10 / small_business changed when the mailbox left it.** It is now `high` / `today`, because `SB-EX-EMPLOYEE-ACCESS` (12 of 19 cases) outweighs `BR-MFA-FATIGUE` (`critical` / `immediate`, 5 cases). `critical` is within one step, so the oracle still passes. `needs_consent` is now `business.staff_accounts`, which `BR-MFA-FATIGUE` and `BR-UNKNOWN-LOGIN-TWIN` do not need.
- **`SM-OPERATOR-BILL` is a payment lure rated `high`.** The README rule ("medium when the lure is a small payment") does not hold for operator impersonation. The second S03 `when` alternative encodes this: a bank, operator or tax-authority impersonation with a payment or card lure.
- **`needs_consent` follows the most-cases rule, so some families' consent-gated signals are left out:**
  - S01: `BR-SIM-SWAP-TWIN/was_me`, `SB-ORDER-BENIGN-ADMIN` and `SB-UNEXPECTED-SIM-ORDER-TWIN/colleague_ordered` need `subscription.recent_events`; `BR-UNKNOWN-LOGIN-TWIN/travelling` needs `operator_account.recent_logins`;
  - S10: `BR-UNKNOWN-LOGIN-TWIN/not_me` needs `operator_account.recent_logins`;
  - S13 / consumer: `CA-OPERATOR-SIM-CODE-TWIN/no_code` needs `subscription.recent_events`.

  This avoids asking every genuine-bill user for login history. The implementation should request a signal only when the matched `when` clause tests the fact that signal feeds (e.g. `sim_change_event`, `unknown_login`, `former_staff_access`).
- **Required steps are majority steps.** Family-specific required steps, such as `review_sessions` for `BR-UNKNOWN-LOGIN-TWIN/travelling` and `dont_share_codes` for `CA-OPERATOR-SIM-CODE-TWIN/no_code`, are in `optional_steps`. Every case therefore finds one of its required steps in `required_steps ∪ optional_steps`. The generated table lists each such family.
- **Twin decisive facts count only on the riskier branch's situation.** On a safer branch (S01, S02, S04, S13) the user has already answered the question, so it is not decisive there.
- **Gaps, filled by copying the other audience's row** (`derived_from_audience`): S07, S08, S14, S15, S16, S17 and S18 for small business; S12 and S19 for consumers. The consumer copies of S12 and S19 use `security_specialist` instead of `business_security_support`, which the vocabulary defines for small businesses only; `security_specialist` is acceptable in every source dev case. None of these rows is backed by a dev case for that audience, so treat them as provisional. S19 / consumer would cover a personal mailbox sending scams to contacts, which the dev set does not contain.
- **S18 is matched before S13.** S18 needs `claimed_sender == bank` and `lure_ask == none` (nothing asked, told to call back via a known number). A "bank" caller who asks for codes is S05 if a code was given or may have been, and S13 if none was.

## Field-level disagreements (generated)

<!-- BEGIN GENERATED: tools/derive_contracts.py -->

| Situation | Audience | Field | Chosen value | Disagreeing family/branch | Cases | What that family has |
|---|---|---|---|---|---|---|
| S01 | consumer | primary_action | no_action_needed | BR-UNKNOWN-LOGIN-TWIN/travelling | 4 | reference primary change_password_and_enable_mfa; chosen value is one of its acceptable actions |
| S01 | consumer | risk_level | none | BR-BREACH-EMAIL-ONLY/main | 12 | reference low (within one step) |
| S01 | consumer | risk_level | none | BR-UNKNOWN-LOGIN-TWIN/travelling | 4 | reference low (within one step) |
| S01 | consumer | urgency | none | BR-BREACH-EMAIL-ONLY/main | 12 | reference routine |
| S01 | consumer | urgency | none | BR-UNKNOWN-LOGIN-TWIN/travelling | 4 | reference routine |
| S01 | consumer | required_steps | explain_benign | BR-UNKNOWN-LOGIN-TWIN/travelling | 4 | reference required: review_sessions |
| S01 | consumer | needs_consent | (none) | BR-SIM-SWAP-TWIN/was_me | 4 | reference necessary_signals: subscription.recent_events |
| S01 | consumer | needs_consent | (none) | BR-UNKNOWN-LOGIN-TWIN/travelling | 4 | reference necessary_signals: operator_account.recent_logins |
| S01 | small_business | primary_action | no_action_needed | BR-UNKNOWN-LOGIN-TWIN/travelling | 2 | reference primary change_password_and_enable_mfa; chosen value is one of its acceptable actions |
| S01 | small_business | primary_action | no_action_needed | SB-UNEXPECTED-SIM-ORDER-TWIN/colleague_ordered | 6 | reference primary contact_operator_support; chosen value is one of its acceptable actions |
| S01 | small_business | risk_level | none | BR-UNKNOWN-LOGIN-TWIN/travelling | 2 | reference low (within one step) |
| S01 | small_business | risk_level | none | SB-SUPPLIER-VERIFIED/main | 12 | reference low (within one step) |
| S01 | small_business | risk_level | none | SB-UNEXPECTED-SIM-ORDER-TWIN/colleague_ordered | 6 | reference low (within one step) |
| S01 | small_business | urgency | none | BR-UNKNOWN-LOGIN-TWIN/travelling | 2 | reference routine |
| S01 | small_business | urgency | none | SB-SUPPLIER-VERIFIED/main | 12 | reference routine |
| S01 | small_business | urgency | none | SB-UNEXPECTED-SIM-ORDER-TWIN/colleague_ordered | 6 | reference routine |
| S01 | small_business | required_steps | explain_benign | BR-UNKNOWN-LOGIN-TWIN/travelling | 2 | reference required: review_sessions |
| S01 | small_business | required_steps | explain_benign | SB-UNEXPECTED-SIM-ORDER-TWIN/colleague_ordered | 6 | reference required: contact_operator |
| S01 | small_business | needs_consent | (none) | BR-SIM-SWAP-TWIN/was_me | 2 | reference necessary_signals: subscription.recent_events |
| S01 | small_business | needs_consent | (none) | BR-UNKNOWN-LOGIN-TWIN/travelling | 2 | reference necessary_signals: operator_account.recent_logins |
| S01 | small_business | needs_consent | (none) | SB-ORDER-BENIGN-ADMIN/main | 12 | reference necessary_signals: subscription.recent_events |
| S01 | small_business | needs_consent | (none) | SB-UNEXPECTED-SIM-ORDER-TWIN/colleague_ordered | 6 | reference necessary_signals: subscription.recent_events, operator_account.recent_logins |
| S02 | consumer | primary_action | do_not_interact_and_delete | SM-STREAMING-EXPIRED/main | 12 | reference primary verify_via_official_channel; chosen value is one of its acceptable actions |
| S02 | consumer | risk_level | medium | CL-PARCEL-PAID-TWIN/no_input | 6 | reference low (within one step) |
| S02 | consumer | required_steps | dont_open_link, dont_pay_or_transfer | CL-PARCEL-PAID-TWIN/no_input | 6 | reference required: delete_or_report_message |
| S02 | consumer | required_steps | dont_open_link, dont_pay_or_transfer | SM-STREAMING-EXPIRED/main | 12 | reference required: dont_open_link, verify_official_channel |
| S03 | consumer | primary_action | verify_via_official_channel | SM-TAX-REFUND/main | 12 | reference primary do_not_interact_and_delete; chosen value is one of its acceptable actions |
| S03 | consumer | risk_level | medium | BR-UNREQUESTED-RESET/main | 12 | reference low (within one step) |
| S03 | consumer | risk_level | medium | SM-BANK-LOCKED/main | 10 | reference high (within one step) |
| S03 | consumer | risk_level | medium | SM-INJECTION-VERIFIED/main | 12 | reference high (within one step) |
| S03 | consumer | risk_level | medium | SM-OPERATOR-BILL/main | 8 | reference high (within one step) |
| S03 | consumer | risk_level | medium | SM-TAX-REFUND/main | 12 | reference high (within one step) |
| S03 | consumer | urgency | today | BR-FAKE-BREACH-NOTICE/main | 12 | reference routine |
| S03 | consumer | urgency | today | BR-UNREQUESTED-RESET/main | 12 | reference routine |
| S03 | consumer | required_steps | dont_open_link, verify_official_channel | BR-FAKE-BREACH-NOTICE/main | 12 | reference required: dont_open_link |
| S03 | consumer | required_steps | dont_open_link, verify_official_channel | SM-OPERATOR-BILL/main | 8 | reference required: dont_open_link, dont_pay_or_transfer, verify_official_channel |
| S03 | consumer | required_steps | dont_open_link, verify_official_channel | SM-TAX-REFUND/main | 12 | reference required: dont_open_link |
| S03 | small_business | required_steps | dont_open_link, verify_official_channel, dont_pay_or_transfer | SM-BANK-LOCKED/main | 2 | reference required: dont_open_link, verify_official_channel |
| S05 | consumer | required_steps | contact_bank_now | CL-PARCEL-PAID-TWIN/entered_card | 6 | reference required: contact_bank_now, block_card |
| S06 | small_business | required_steps | change_password, check_forwarding_rules, review_sessions | CL-EMAIL-PASSWORD-PHISH/main | 3 | reference required: change_password, check_password_reuse |
| S07 | small_business | (whole row) | copy of consumer | - | 0 | no small_business dev cases for this situation |
| S08 | consumer | primary_action | contact_bank_and_block_cards | CL-REMOTE-ACCESS-TWIN/no_banking | 6 | reference primary isolate_device_and_scan; chosen value is one of its acceptable actions |
| S08 | consumer | risk_level | critical | CL-REMOTE-ACCESS-TWIN/no_banking | 6 | reference high (within one step) |
| S08 | consumer | urgency | immediate | CL-REMOTE-ACCESS-TWIN/no_banking | 6 | reference today |
| S08 | consumer | required_steps | disconnect_device, contact_bank_now, remove_app_or_profile | CL-REMOTE-ACCESS-TWIN/banking_during_session | 6 | reference required: contact_bank_now, disconnect_device |
| S08 | consumer | required_steps | disconnect_device, contact_bank_now, remove_app_or_profile | CL-REMOTE-ACCESS-TWIN/no_banking | 6 | reference required: disconnect_device, remove_app_or_profile |
| S08 | small_business | (whole row) | copy of consumer | - | 0 | no small_business dev cases for this situation |
| S09 | small_business | required_steps | contact_operator, change_password | BR-SIM-SWAP-TWIN/not_me | 2 | reference required: contact_operator, lock_subscription |
| S09 | small_business | needs_consent | operator_account.recent_logins, subscription.recent_events | BR-SIM-SWAP-TWIN/not_me | 2 | reference necessary_signals: subscription.recent_events |
| S10 | consumer | risk_level | critical | BR-UNKNOWN-LOGIN-TWIN/not_me | 4 | reference high (within one step) |
| S10 | consumer | required_steps | change_password, dont_approve_prompts | BR-UNKNOWN-LOGIN-TWIN/not_me | 4 | reference required: change_password, review_sessions |
| S10 | consumer | needs_consent | (none) | BR-UNKNOWN-LOGIN-TWIN/not_me | 4 | reference necessary_signals: operator_account.recent_logins |
| S10 | small_business | risk_level | high | BR-MFA-FATIGUE/main | 5 | reference critical (within one step) |
| S10 | small_business | urgency | today | BR-MFA-FATIGUE/main | 5 | reference immediate |
| S10 | small_business | urgency | today | BR-UNKNOWN-LOGIN-TWIN/not_me | 2 | reference immediate |
| S10 | small_business | required_steps | change_password, review_sessions | BR-MFA-FATIGUE/main | 5 | reference required: dont_approve_prompts, change_password |
| S10 | small_business | needs_consent | business.staff_accounts | BR-MFA-FATIGUE/main | 5 | reference necessary_signals: none |
| S10 | small_business | needs_consent | business.staff_accounts | BR-UNKNOWN-LOGIN-TWIN/not_me | 2 | reference necessary_signals: operator_account.recent_logins |
| S12 | small_business | risk_level | critical | SB-ATTACHMENT-TWIN/enabled_content | 6 | reference high (within one step) |
| S12 | small_business | required_steps | disconnect_device, dont_pay_or_transfer | SB-ATTACHMENT-TWIN/enabled_content | 6 | reference required: disconnect_device, get_device_checked |
| S12 | consumer | (whole row) | copy of small_business | - | 0 | no consumer dev cases for this situation |
| S13 | consumer | primary_action | do_not_interact_and_delete | CA-BANK-IMPOSTOR-TWIN/no_codes | 1 | reference primary verify_via_official_channel; chosen value is one of its acceptable actions |
| S13 | consumer | primary_action | do_not_interact_and_delete | CA-OPERATOR-SIM-CODE-TWIN/no_code | 6 | reference primary contact_operator_support; chosen value is one of its acceptable actions |
| S13 | consumer | risk_level | medium | CA-BANK-IMPOSTOR-TWIN/no_codes | 1 | reference high (within one step) |
| S13 | consumer | risk_level | medium | CA-TECH-SUPPORT/main | 8 | reference low (within one step) |
| S13 | consumer | urgency | routine | CA-BANK-IMPOSTOR-TWIN/no_codes | 1 | reference today |
| S13 | consumer | urgency | routine | CA-OPERATOR-SIM-CODE-TWIN/no_code | 6 | reference today |
| S13 | consumer | required_steps | hang_up_dont_call_back | CA-BANK-IMPOSTOR-TWIN/no_codes | 1 | reference required: verify_official_channel |
| S13 | consumer | required_steps | hang_up_dont_call_back | CA-OPERATOR-SIM-CODE-TWIN/no_code | 6 | reference required: dont_share_codes |
| S13 | consumer | needs_consent | (none) | CA-OPERATOR-SIM-CODE-TWIN/no_code | 6 | reference necessary_signals: subscription.recent_events |
| S13 | small_business | primary_action | do_not_interact_and_delete | CA-BANK-IMPOSTOR-TWIN/no_codes | 5 | reference primary verify_via_official_channel; chosen value is one of its acceptable actions |
| S13 | small_business | primary_action | do_not_interact_and_delete | SB-TERMINAL-SUPPORT-CALL/main | 12 | reference primary verify_via_official_channel; chosen value is one of its acceptable actions |
| S13 | small_business | risk_level | medium | CA-BANK-IMPOSTOR-TWIN/no_codes | 5 | reference high (within one step) |
| S13 | small_business | risk_level | medium | CA-TECH-SUPPORT/main | 4 | reference low (within one step) |
| S13 | small_business | risk_level | medium | SB-TERMINAL-SUPPORT-CALL/main | 12 | reference high (within one step) |
| S13 | small_business | urgency | today | CA-TECH-SUPPORT/main | 4 | reference routine |
| S13 | small_business | required_steps | verify_official_channel, dont_share_codes | CA-BANK-IMPOSTOR-TWIN/no_codes | 5 | reference required: verify_official_channel |
| S13 | small_business | required_steps | verify_official_channel, dont_share_codes | CA-TECH-SUPPORT/main | 4 | reference required: hang_up_dont_call_back |
| S14 | small_business | (whole row) | copy of consumer | - | 0 | no small_business dev cases for this situation |
| S15 | small_business | (whole row) | copy of consumer | - | 0 | no small_business dev cases for this situation |
| S16 | small_business | (whole row) | copy of consumer | - | 0 | no small_business dev cases for this situation |
| S17 | small_business | (whole row) | copy of consumer | - | 0 | no small_business dev cases for this situation |
| S18 | small_business | (whole row) | copy of consumer | - | 0 | no small_business dev cases for this situation |
| S19 | consumer | (whole row) | copy of small_business | - | 0 | no consumer dev cases for this situation |

<!-- END GENERATED -->

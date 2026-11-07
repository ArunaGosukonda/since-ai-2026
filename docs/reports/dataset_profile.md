# Dataset Profile Report — DNA SimSet v2.0.1

**Generated:** Automatically from `data/dev/cases.jsonl` and `data/test/inputs.jsonl`
**Total Dev Cases:** 588
**Total Test Inputs:** 335

---

## 1. Demographics & Distributions

### Audience
* **Dev:** {'consumer': 396, 'small_business': 192}
* **Test:** {'small_business': 95, 'consumer': 240}

### User Language
* **Dev:** {'fi': 361, 'en': 182, 'sv': 45} (fi: 61.4%, en: 31.0%, sv: 7.7%)
* **Test:** {'fi': 204, 'sv': 13, 'en': 118} (fi: 60.9%, en: 35.2%, sv: 3.9%)

### Journeys
| Journey | Dev Cases | Dev Share | Test Inputs | Test Share |
|---|---|---|---|---|
| `breach_notice` | 120 | 20.4% | 60 | 17.9% |
| `clicked_link` | 84 | 14.3% | 45 | 13.4% |
| `smb_incident` | 156 | 26.5% | 85 | 25.4% |
| `suspicious_call` | 72 | 12.2% | 60 | 17.9% |
| `suspicious_message` | 156 | 26.5% | 85 | 25.4% |

---

## 2. Security & Ground Truth Characteristics (Dev Split)

* **Benign Controls:** 132 cases (22.4%) — genuine bills, valid orders, routine spam flags.
* **Twin Cases:** 108 cases (18.4%) in 54 twin groups.
* **Escalation Required:** 102 cases (17.3%) require human escalation.

### Primary Actions Distribution (Dev Ground Truth)
| Primary Action | Count | Percentage |
|---|---|---|
| `no_action_needed` | 150 | 25.5% |
| `verify_via_official_channel` | 132 | 22.4% |
| `change_password_and_enable_mfa` | 84 | 14.3% |
| `do_not_interact_and_delete` | 72 | 12.2% |
| `contact_bank_and_block_cards` | 60 | 10.2% |
| `isolate_device_and_scan` | 36 | 6.1% |
| `contact_operator_support` | 30 | 5.1% |
| `decline_out_of_scope` | 12 | 2.0% |
| `escalate_to_human` | 12 | 2.0% |

### Risk Levels (Dev Ground Truth)
| Risk Level | Count | Percentage |
|---|---|---|
| `high` | 174 | 29.6% |
| `critical` | 126 | 21.4% |
| `none` | 126 | 21.4% |
| `medium` | 84 | 14.3% |
| `low` | 78 | 13.3% |

### Urgency Levels (Dev Ground Truth)
| Urgency | Count | Percentage |
|---|---|---|
| `today` | 174 | 29.6% |
| `immediate` | 162 | 27.6% |
| `routine` | 126 | 21.4% |
| `none` | 126 | 21.4% |

### Decisive Question Topics (Must Ask in Twins/Ambiguities)
| Question Topic | Dev Frequency |
|---|---|
| `self_initiated` | 36 |
| `code_shared` | 24 |
| `credentials_entered` | 12 |
| `card_details_entered` | 12 |
| `user_safety` | 12 |
| `app_installed` | 12 |
| `payment_status` | 12 |

---

## 3. Consent Gated Signals

### Signals Requiring Consent
| Signal Path | Frequency in Dev |
|---|---|
| `subscription.network_status` | 588 |
| `operator_account.recent_logins` | 588 |
| `device.security_findings` | 346 |
| `subscription.recent_events` | 253 |
| `device.recent_app_installs` | 243 |
| `business.staff_accounts` | 192 |
| `credential_exposure` | 109 |

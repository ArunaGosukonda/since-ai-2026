# Data Dictionary — DNA Digital Security Assistant

**Document Version:** 1.0.0 (Phase 1 Baseline)  
**Package:** `DNA_Digital_Security_Assistant_SimSet_v2.0.1`  
**Standard Schema:** `schema/case.schema.json` & `schema/test_input.schema.json`  

---

## 1. Top-Level Case Attributes

| Field Name | Type | Availability | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `case_id` | string | All | Unique case identifier (`DSA-D-xxxx` for dev, `DSA-T-xxxx` for test). | `"DSA-D-0056"` |
| `split` | string | Dev only | Dataset split indicator (`dev` or `test`). | `"dev"` |
| `version` | string | All | Dataset release version. | `"2.0.1"` |
| `journey` | enum | All | One of 5 threat journeys: `suspicious_message`, `clicked_link`, `suspicious_call`, `breach_notice`, `smb_incident`. | `"suspicious_message"` |
| `audience` | enum | All | Target customer segment: `consumer` or `small_business`. | `"consumer"` |
| `locale` | string | All | Regional locale identifier (`fi-FI`, `en-US`, `sv-FI`, `sv-SE`). | `"fi-FI"` |
| `language` | enum | All | Primary user language: `fi` (Finnish), `en` (English), `sv` (Swedish). | `"fi"` |
| `persona` | object | All | Customer demographic context: `segment`, `age_band`, `tech_confidence`, `emotional_state`, `language`. | `{"tech_confidence": "low", "emotional_state": "worried"}` |
| `entry_point` | enum | All | Channel where conversation started: `operator_app_chat`, `business_portal_chat`, `phone_ivr_handoff`. | `"operator_app_chat"` |
| `user_identified` | boolean | All | Always `true` (user is logged into authenticated DNA portal/app). | `true` |
| `opening_message`| string | All | The initial statement or question typed by the user. Treated as **untrusted evidence**. | `"Sain tekstiviestin pankilta, onko tämä aito?"` |
| `signals` | object | All | Multi-modal simulated operator and device signals (detailed below). | `{...}` |
| `signal_availability` | object | All | Metadata on whether signals are `available`, `not_provided`, or `not_applicable`. | `{"link_check": "available"}` |
| `consent` | object | All | Consent state: `requires_consent` (list of gated paths) and `pre_granted` (already consented). | `{"requires_consent": ["subscription.recent_events"]}` |
| `tags` | array | Dev only | Categorization tags for analysis (e.g. `twin`, `operator_relevant`, `distractor_signal`). | `["twin", "operator_relevant"]` |
| `difficulty` | enum | Dev only | `easy`, `medium`, `hard`. | `"medium"` |
| `scenario_family`| string | Dev only | The scenario family identifier (e.g. `SM-BANK-LOCKED`, `CA-OPERATOR-SIM-CODE-TWIN`). | `"SM-BANK-LOCKED"` |
| `title` | string | Dev only | Descriptive scenario title. | `"'Your bank account is locked' SMS"` |
| `holdout_family` | boolean | Dev only | `false` in dev; `true` for 9 unseen test scenario families. | `false` |
| `ground_truth` | object | Dev only | **Withheld from runtime inference:** Expected answers, acceptable actions, escalation, steps, decisive questions. | `{...}` |
| `simulation` | object | Dev only | **Withheld from runtime inference:** Facts known to the simulated user in multi-turn runs. | `{...}` |

---

## 2. Signal Object Dictionary (`signals.*`)

| Signal Path | Nested Fields | Privacy Level | Description |
| :--- | :--- | :--- | :--- |
| `signals.artifact` | `type`, `sender`, `body`, `links`, `received_at`, `thread_contains_genuine_messages...` | Standard | The forwarded message, email, call transcript, or notice. Untrusted evidence. |
| `signals.link_check` | `url`, `verdict`, `confidence`, `categories`, `domain_age_days` | Standard | Simulated URL reputation engine (`clean`, `suspicious`, `malicious`, `unknown`, `null`). |
| `signals.call_warning`| `number`, `warning`, `confidence`, `answered`, `duration_s`, `caller_id_possibly_spoofed` | Standard | Simulated network call filter (`none`, `possible_spam`, `suspected_fraud`). |
| `signals.subscription.products` | List of `{type, count, esim}` | Standard | Customer subscriptions (e.g. `mobile`, `home_broadband`, `business_mobile`). |
| `signals.subscription.recent_events` | List of `{type, minutes_ago, channel, authentication, new_device}` | **Consent-Gated** | Sensitive SIM changes, orders, eSIM transfers (`esim_activation`, `new_subscription_order`). |
| `signals.subscription.network_status` | `service`, `since_minutes` | **Consent-Gated** | Current network status (`normal`, `no_service`). Crucial for SIM swap detection. |
| `signals.device.summary` | `platform`, `os_version`, `patch_status`, `security_app` | Standard | Device operating system (iOS, Android, Windows) and patch latency. |
| `signals.device.recent_app_installs` | List of `{name, source, days_ago, permissions}` | **Consent-Gated** | Recent apps on Android/Windows (always null on iOS due to OS sandboxing). |
| `signals.device.security_findings` | `accessibility_services`, `remote_access_apps`, `unknown_profiles` | **Consent-Gated** | Host-level malware findings (e.g. sideloaded app with accessibility permissions). |
| `signals.operator_account.recent_logins` | List of `{days_ago, country, device_known, result}` | **Consent-Gated** | Recent authentication history to the operator portal/app. |
| `signals.credential_exposure` | `found`, `sources: [{service_category, exposed, days_ago}]` | **Consent-Gated** | Dark-web breach monitor findings (e.g. exposed email in past breaches). |
| `signals.business.profile` | `company`, `employees`, `admins`, `it_support`, `payment_approval` | Standard | SME context: company size, dual payment approval policies. |
| `signals.business.staff_accounts` | List of `{role, status, last_active_days_ago, admin}` | **Consent-Gated** | SME employee directory and administrative privilege roster. |

---

## 3. Ground Truth & Simulation (Dev-Only Fields)

The following fields exist **only in `data/dev/cases.jsonl`** and are used exclusively by `eval/evaluate.py` and `sim/run_conversation.py`. The assistant runtime is **strictly prohibited** from receiving or referencing these:

* `ground_truth.risk_level` (`none`, `low`, `medium`, `high`, `critical`)
* `ground_truth.urgency` (`none`, `routine`, `today`, `immediate`)
* `ground_truth.primary_action` & `ground_truth.acceptable_actions`
* `ground_truth.escalation` (`required`, `target`, `acceptable_targets`)
* `ground_truth.required_steps` & `ground_truth.optional_steps`
* `ground_truth.must_not` (Prohibited unsafe claim IDs)
* `ground_truth.must_ask_topics` & `ground_truth.should_ask_topics`
* `ground_truth.guidance_refs` (Approved guidance IDs)
* `ground_truth.single_turn` (Single-turn safe fallback configuration for twins)
* `ground_truth.reference_answer_fi` & `ground_truth.reference_answer_en`
* `simulation.facts` (Hidden facts revealed in multi-turn conversation upon asking)
* `simulation.consent_policy` (`grant` or `refuse`)

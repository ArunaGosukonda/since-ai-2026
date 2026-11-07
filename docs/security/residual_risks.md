# Residual Risks & Limitations Register — DNA Digital Security Assistant

**Document Version:** 1.0.0 (Phase 0 Baseline)  
**System:** DNA Digital Security Assistant (Since AI Hackathon 2026)  

---

## 1. Residual Risk Assessment

While the hybrid neuro-symbolic architecture provides strong guarantees regarding primary actions, consent gating, and defense-in-depth, several residual risks and operational limitations remain:

| Risk ID | Risk Title & Description | Inherent Risk | Applied Controls | Residual Risk Level | Accepted Rationale & Monitoring Plan |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RR-01** | **Regex Text Check Limitations:** Automated step and unsafe claim detection uses regular expressions that can suffer from false negatives (paraphrased advice) or false positives (complex linguistic negations). | High | Used standard package patterns; added comprehensive unit tests covering diverse phrasing; designed templates to cleanly match vocabularies. | Medium | Evaluator uses these exact heuristics. Human review during judging will assess genuine clarity. |
| **RR-02** | **Synthetic Environment vs Live Production Reality:** The system is evaluated on synthetic, deterministic scenarios. Real-world telecom fraud features novel domains, live zero-day malware, and unpredictable human panic. | High | Adherence to general security principles (NCSC-FI / Traficom); conservative escalation thresholds for unknown anomalies. | Medium | Hackathon prototype constraint. Clearly labeled as synthetic prototype in submission. |
| **RR-03** | **Swedish Language Coverage & Nuance:** Swedish represents ~6% of the dataset, and the reference guidance corpus lacks Swedish translations. Nuanced Swedish idiom may be less comprehensive than Finnish. | Medium | Integrated dedicated Swedish prompt templates and vocabulary matching patterns (`question_topics.json`, `unsafe_claims.json`, `step_vocabulary.json`). | Medium | Human review advised for Swedish deployments; documented as an explicit limitation in final report. |
| **RR-04** | **Uncooperative or Vague Live Users:** Simulated users in the test suite are cooperative and follow a scripted fact revelation path. Real users may wander, provide contradictory statements, or lie. | High | Multi-turn state machine tracks confidence and question counts; automatically defaults to safe branch on ambiguity. | Medium | Fallback to human escalation after `max_assistant_turns` prevents prolonged looping. |
| **RR-05** | **Novel Prompt Injection Vectors:** Advanced multi-lingual, polymorphic, or encoded prompt injections may theoretically bypass heuristic input filters. | High | Dual-layer architecture: core decision engine does not execute LLM instructions; egress gate blocks unsafe claim patterns regardless of prompt source. | Low | Core security decisions are mathematically decoupled from LLM output, containing impact to phrasing only. |

---

## 2. Risk Mitigation & Continuous Assurance Plan

1. **Automated Regression Suite:** Every new rule or phrasing change must pass the full 588-case dev evaluation and the red-team test suite before merging.
2. **Deterministic Fallbacks:** If an exception occurs, or if the output security gate detects a policy violation, the system instantly emits a pre-validated, fail-safe response.
3. **Transparent Reporting:** Document all known edge cases, false alarm trade-offs, and failure cases honestly in `templates/RESULTS_TEMPLATE.md`.

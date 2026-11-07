#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dataset profiling tool for Since AI / DNA Hackathon 2026.
Analyzes data/dev/cases.jsonl and data/test/inputs.jsonl to produce
docs/reports/dataset_profile.md and docs/requirements/data_dictionary.md.
"""
import json
from collections import Counter, defaultdict
import csv

def load_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

def profile():
    dev_cases = load_jsonl("data/dev/cases.jsonl")
    test_cases = load_jsonl("data/test/inputs.jsonl")

    print(f"Loaded {len(dev_cases)} dev cases and {len(test_cases)} test cases.")

    # 1. Basic counts
    dev_n = len(dev_cases)
    test_n = len(test_cases)

    # 2. Audience distribution
    dev_aud = Counter(c["audience"] for c in dev_cases)
    test_aud = Counter(c["audience"] for c in test_cases)

    # 3. Language distribution
    dev_lang = Counter(c["language"] for c in dev_cases)
    test_lang = Counter(c["language"] for c in test_cases)

    # 4. Journey distribution
    dev_journeys = Counter(c["journey"] for c in dev_cases)
    test_journeys = Counter(c["journey"] for c in test_cases)

    # 5. Benign vs Risky (dev)
    dev_benign = sum(1 for c in dev_cases if c["ground_truth"]["is_benign_control"])
    dev_twins = sum(1 for c in dev_cases if c["ground_truth"].get("twin_group"))

    # 6. Primary Action distribution (dev)
    dev_actions = Counter(c["ground_truth"]["primary_action"] for c in dev_cases)

    # 7. Risk level distribution (dev)
    dev_risk = Counter(c["ground_truth"]["risk_level"] for c in dev_cases)

    # 8. Urgency distribution (dev)
    dev_urgency = Counter(c["ground_truth"]["urgency"] for c in dev_cases)

    # 9. Escalation required (dev)
    dev_esc = Counter(c["ground_truth"]["escalation"]["required"] for c in dev_cases)

    # 10. Scenario families
    dev_families = Counter(c["scenario_family"] for c in dev_cases)
    test_families = Counter(c.get("scenario_family", "unknown") for c in test_cases)
    print(f"Dev families: {len(dev_families)}")

    # 11. Decisive question topics (dev)
    dev_must_ask = Counter(
        topic
        for c in dev_cases
        for topic in c["ground_truth"].get("must_ask_topics", [])
    )

    # 12. Consent gated signals
    dev_consent_req = Counter(
        sig
        for c in dev_cases
        for sig in c.get("consent", {}).get("requires_consent", [])
    )
    dev_pre_granted = Counter(
        sig
        for c in dev_cases
        for sig in c.get("consent", {}).get("pre_granted", [])
    )

    # Write summary report
    report = f"""# Dataset Profile Report — DNA SimSet v2.0.1

**Generated:** Automatically from `data/dev/cases.jsonl` and `data/test/inputs.jsonl`
**Total Dev Cases:** {dev_n}
**Total Test Inputs:** {test_n}

---

## 1. Demographics & Distributions

### Audience
* **Dev:** {dict(dev_aud)}
* **Test:** {dict(test_aud)}

### User Language
* **Dev:** {dict(dev_lang)} (fi: {dev_lang['fi']/dev_n*100:.1f}%, en: {dev_lang['en']/dev_n*100:.1f}%, sv: {dev_lang['sv']/dev_n*100:.1f}%)
* **Test:** {dict(test_lang)} (fi: {test_lang['fi']/test_n*100:.1f}%, en: {test_lang['en']/test_n*100:.1f}%, sv: {test_lang['sv']/test_n*100:.1f}%)

### Journeys
| Journey | Dev Cases | Dev Share | Test Inputs | Test Share |
|---|---|---|---|---|
"""
    for j in sorted(dev_journeys.keys()):
        report += f"| `{j}` | {dev_journeys[j]} | {dev_journeys[j]/dev_n*100:.1f}% | {test_journeys[j]} | {test_journeys[j]/test_n*100:.1f}% |\n"

    report += f"""
---

## 2. Security & Ground Truth Characteristics (Dev Split)

* **Benign Controls:** {dev_benign} cases ({dev_benign/dev_n*100:.1f}%) — genuine bills, valid orders, routine spam flags.
* **Twin Cases:** {dev_twins} cases ({dev_twins/dev_n*100:.1f}%) in 54 twin groups.
* **Escalation Required:** {dev_esc[True]} cases ({dev_esc[True]/dev_n*100:.1f}%) require human escalation.

### Primary Actions Distribution (Dev Ground Truth)
| Primary Action | Count | Percentage |
|---|---|---|
"""
    for act, cnt in dev_actions.most_common():
        report += f"| `{act}` | {cnt} | {cnt/dev_n*100:.1f}% |\n"

    report += """
### Risk Levels (Dev Ground Truth)
| Risk Level | Count | Percentage |
|---|---|---|
"""
    for r, cnt in dev_risk.most_common():
        report += f"| `{r}` | {cnt} | {cnt/dev_n*100:.1f}% |\n"

    report += """
### Urgency Levels (Dev Ground Truth)
| Urgency | Count | Percentage |
|---|---|---|
"""
    for u, cnt in dev_urgency.most_common():
        report += f"| `{u}` | {cnt} | {cnt/dev_n*100:.1f}% |\n"

    report += f"""
### Decisive Question Topics (Must Ask in Twins/Ambiguities)
| Question Topic | Dev Frequency |
|---|---|
"""
    for topic, cnt in dev_must_ask.most_common():
        report += f"| `{topic}` | {cnt} |\n"

    report += """
---

## 3. Consent Gated Signals

### Signals Requiring Consent
| Signal Path | Frequency in Dev |
|---|---|
"""
    for sig, cnt in dev_consent_req.most_common():
        report += f"| `{sig}` | {cnt} |\n"

    with open("docs/reports/dataset_profile.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("Wrote docs/reports/dataset_profile.md")

if __name__ == "__main__":
    profile()

"""Export the text messages (SMS) from the dev dataset for the phone demo.

Writes frontend/src/generated/smsExamples.json: one entry per distinct SMS artifact in
data/dev/cases.jsonl with only what a phone would show - case_id (for traceability), sender,
body and language. Dev-only fields (ground_truth, simulation, scenario_family, title, tags,
difficulty, holdout_family) are never read, so the demo cannot show or use the answers.

The data is CC BY 4.0: "DNA Digital Security Assistant simulation set v2.0.1, Since AI ry, 2026".

Usage:  python3 tools/export_sms_examples.py
"""
import json
import os
import sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dsa import kit  # noqa: E402

OUT = os.path.join(ROOT, "frontend", "src", "generated", "smsExamples.json")
ATTRIBUTION = "DNA Digital Security Assistant simulation set v2.0.1, Since AI ry, 2026 (CC BY 4.0)"


def examples():
    seen, out = set(), []
    with open(kit.DEV_CASES, encoding="utf-8") as f:
        for line in f:
            case = json.loads(line)
            art = (case.get("signals") or {}).get("artifact") or {}
            if art.get("type") != "sms" or not art.get("body"):
                continue
            body = art["body"].strip()
            if body in seen:
                continue
            seen.add(body)
            out.append({
                "case_id": case["case_id"],
                "sender": art.get("sender") or "Unknown",
                "body": body,
                "lang": art.get("channel_language") or case.get("language") or "en",
            })
    return out


def main():
    data = {"source": ATTRIBUTION, "generated_by": "tools/export_sms_examples.py", "examples": examples()}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    by_lang = {}
    for e in data["examples"]:
        by_lang[e["lang"]] = by_lang.get(e["lang"], 0) + 1
    print("wrote %s (%d examples: %s)" % (os.path.relpath(OUT, ROOT), len(data["examples"]), by_lang))


if __name__ == "__main__":
    main()

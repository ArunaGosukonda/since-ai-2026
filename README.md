# DNA Digital Security Assistant — Since AI 2026

[![Live Demo](https://img.shields.io/badge/Live_Demo-since--ai.cloud.run-brightgreen?style=for-the-badge&logo=googlecloud)](https://since-ai.cloud.run)
[![Cloud Run](https://img.shields.io/badge/GCP_Cloud_Run-europe--north1-blue?style=for-the-badge&logo=googlecloud)](https://since-ai-881905987122.europe-north1.run.app)

### 🚀 Live Interactive Demo
- **Primary Live Demo (Clean Custom Domain):** [https://since-ai.cloud.run](https://since-ai.cloud.run)
- **Direct Regional Service URL:** [https://since-ai-881905987122.europe-north1.run.app](https://since-ai-881905987122.europe-north1.run.app)
- **Legacy Prototype Fallback:** [https://since-ai.cloud.run/demo.html](https://since-ai.cloud.run/demo.html)

### 🛡️ Key Features in the Live Demo
1. **Interactive Phone Simulator:** Real-time incoming voice call simulation with progressive danger underlines and threat meter (`Listening` → `Be careful` → `Scam`).
2. **Deterministic Banking Analysis:** Spoken call line analysis powered by Since AI's security engine identifying unverified caller IDs and code extraction attempts.
3. **SMS Threat Inbox:** Interactive text message threat classification with strict unverified link warning enforcement.
4. **Multilingual AI Security Assistant:** Multi-turn advisory support in English, Finnish, and Swedish with zero-jargon safety guards.
5. **Production Cloud Architecture:** Google Cloud Run in `europe-north1` (Hamina, Finland) with Google Cloud SQL PostgreSQL 18.6 + `pgvector 0.8.5`.

---

Synthetic practice and test data, a simulated user and an evaluator for the DNA challenge at Since AI Hackathon 2026: **Digital Security Assistant: What Should I Do Now?**

**Start with `START_HERE.html`** (or `START_HERE.md`).

```bash
python3 tools/validate.py
python3 baselines/rules_baseline.py --cases data/dev/cases.jsonl --out b.jsonl
python3 eval/evaluate.py --cases data/dev/cases.jsonl --submission b.jsonl
```

588 dev cases with ground truth · 335 test inputs · 58 scenario families · five journeys · Finnish, English and Swedish users · Python 3.10+, no dependencies.

Synthetic. Not DNA's advice. Code MIT, data CC BY 4.0, © 2026 Since AI ry.

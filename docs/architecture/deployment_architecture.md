# Deployment Architecture — DNA Digital Security Assistant

**Document Version:** 1.0.0 (Phase 0 Baseline)  
**System:** DNA Digital Security Assistant (Since AI Hackathon 2026)  

---

## 1. Deployment Overview & Execution Modes

The DNA Digital Security Assistant is packaged as a lightweight, modular service supporting three distinct runtime modes:

```mermaid
flowchart LR
    subgraph ExecutionModes[Assistant Execution Modes]
        CLI_Batch["1. Batch Inference CLI<br/>(Single-Turn Prediction Engine)"]
        Bot_Adapter["2. Multi-Turn Bot Adapter<br/>(stdin/stdout & Python Callable)"]
        Demo_UI["3. Interactive Web Demo UI<br/>(DNA Portal Simulation)"]
    end

    subgraph CoreEngine[Shared Security Engine (src/)]
        DecisionEngine["Decision & Intelligence Engine"]
        Guardrails["Output & Boundary Guardrails"]
        KnowledgeBase["Guidance Knowledge Base"]
    end

    CLI_Batch --> CoreEngine
    Bot_Adapter --> CoreEngine
    Demo_UI --> CoreEngine
```

1. **Batch Inference CLI (`src/application/batch_runner.py`):**
   * Processes `data/dev/cases.jsonl` or `data/test/inputs.jsonl` at scale.
   * Outputs compliant `test_predictions.jsonl` matching `schema/submission.schema.json`.
   * Evaluated via `tools/validate.py` and `eval/evaluate.py`.

2. **Multi-Turn Conversation Adapter (`src/conversation/bot_adapter.py`):**
   * Implements `step(event, state) -> reply` conforming to `sim/PROTOCOL.md`.
   * Executable via `sim/run_conversation.py --cases data/dev/cases.jsonl --bot-py src.conversation.bot_adapter:step --out mt_results.jsonl`.

3. **Interactive Demonstration Service (`src/application/demo_ui.py`):**
   * Lightweight local web server (built with Python `http.server` or FastAPI/Flask) rendering a high-fidelity mock of the **Oma DNA App** and **DNA Business Portal**.
   * Provides live interactive testing of the 5 journeys, persona toggling, telemetry visibility, consent approval flows, and 1-click human escalation ticket generation.

---

## 2. Plausible DNA Enterprise Integration Path

In a live production environment, the assistant would be deployed into DNA's cloud environment (e.g. AWS Europe or private OpenShift/Kubernetes cluster in Finland):

```mermaid
flowchart TB
    subgraph ClientLayer[DNA Touchpoints]
        OmaDNA["Oma DNA Mobile App (iOS / Android)"]
        BizPortal["DNA Yrityksille Self-Service Portal"]
    end

    subgraph APILayer[DNA API Gateway & Identity]
        APIGW["DNA API Gateway (TLS 1.3 / mTLS)"]
        IDP["DNA Customer Identity Provider (BankID / Mobiilivarmenne)"]
    end

    subgraph MicroserviceLayer[Security Assistant Container]
        ServiceInstance["Digital Security Assistant Service (FastAPI / Gunicorn)"]
        SecGuard["Ingress / Egress Guardrail Filter"]
        Engine["Decision & Grounding Engine"]
    end

    subgraph InternalSystems[DNA Internal Telecom Telemetry]
        SubDB[("Subscription & SIM Registry")]
        NetTelemetry[("Network Fraud & Spam Scoring Engine")]
        DeviceMgt[("DNA Security App Fleet Telemetry")]
    end

    subgraph SupportDesk[DNA Operations]
        AgentDesk["DNA Customer Care & Tier-2 SOC Portal"]
    end

    ClientLayer --> APIGW
    APIGW <--> IDP
    APIGW --> ServiceInstance
    
    ServiceInstance <--> SecGuard
    SecGuard <--> Engine
    
    ServiceInstance -.->|"With explicit customer consent"| SubDB
    ServiceInstance -.->|"With explicit customer consent"| NetTelemetry
    ServiceInstance -.->|"With explicit customer consent"| DeviceMgt
    
    ServiceInstance -->|"Escalation with pre-filled triage brief"| AgentDesk
```

### Security & Privacy Protections in Deployment:
* **Zero PII Storage:** Stateless operation—no customer conversation transcripts or device identifiers stored permanently in the assistant container.
* **Strict Least Privilege:** Microservice communicates with internal telemetry APIs solely through authenticated backend service tokens with read-only access.
* **Network Isolation:** In production, container runs without raw public internet outbound access, fetching only authenticated internal threat feeds and approved guidance.

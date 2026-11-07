# System Context — DNA Digital Security Assistant

**Document Version:** 1.0.0 (Phase 0 Baseline)  
**System:** DNA Digital Security Assistant (Since AI Hackathon 2026)  
**Challenge Partner:** DNA Oyj  

---

## 1. System Mission & Context

The **DNA Digital Security Assistant** is an intelligent, privacy-preserving, and safety-critical assistant embedded inside DNA's customer touchpoints (the **Oma DNA** mobile application for consumers and the **DNA Business Portal** for small enterprises).

The assistant bridges the "Awareness-Action Gap": when users encounter suspicious calls, texts, emails, clicked links, breach notices, or anomalous account activities, the system converts raw user descriptions and available operator risk signals into **one clear, proportionate, actionable next step**.

It operates strictly on principles of calibrated uncertainty (declining to guess missing facts), rigorous privacy/consent boundaries, deterministic security guardrails, and seamless handoff to human DNA support when necessary.

---

## 2. System Context Diagram (C4 Level 1)

```mermaid
flowchart TB
    subgraph External_Entities[External Systems & Entities]
        User_Consumer["Consumer User<br/>(Personal Security)"/]
        User_SMB["Small Enterprise User<br/>(Business Incident)"/]
        DNA_Agent["DNA Human Support Agent<br/>(Tier-2 / Security Specialist)"/]
        Bank_Hotlines["Bank Card & Fraud Services<br/>(External Verification)"/]
        Authorities["Traficom / NCSC-FI / Police<br/>(Incident Reporting)"/]
    end

    subgraph DNA_Digital_Ecosystem[DNA Digital Ecosystem]
        Portal_App["DNA Customer Portal / Oma DNA App<br/>(Authenticated Context)"/]
        
        subgraph Digital_Security_Assistant[DNA Digital Security Assistant (Our System)]
            Gateway["Ingress Gateway & Boundary Validator"]
            Core_Engine["Hybrid Security Decision & Intelligence Engine"]
            Guardrail["Deterministic Guardrails & Output Security Gate"]
            State_Store["Session & Conversation State (In-Memory / Isolated)"]
        end
        
        Operator_Data["Simulated Operator Signals<br/>(Subscription, SIM, Network, Device)"/]
        Knowledge_Corpus["Since AI Guidance Corpus<br/>(55 Passages - Unofficial)"/]
    end

    User_Consumer -->|"Describes threat, asks 'What Should I Do Now?'"| Portal_App
    User_SMB -->|"Reports workplace anomaly, invoice, or compromise"| Portal_App
    
    Portal_App -->|"Passes verified user session + case payload"| Gateway
    Gateway --> Core_Engine
    Core_Engine <--> Guardrail
    Core_Engine <--> State_Store
    Core_Engine <--> Knowledge_Corpus
    Core_Engine <--> Operator_Data

    Core_Engine -->|"Actionable advice, steps, questions, consent requests"| Portal_App
    Core_Engine -->|"Pre-filled incident triage ticket & escalation summary"| DNA_Agent
    
    Portal_App -.->|"Guides user to official contact"| Bank_Hotlines
    Portal_App -.->|"Recommends official report"| Authorities
```

---

## 3. Stakeholders & Personas

### 3.1 Consumer Persona
* **Demographics:** Adults, seniors, teens across Finland. Tech confidence varies from low to high. Emotional state often ranges from calm to highly anxious/panicked.
* **Common Threats:** Phishing SMS (bank impersonation, parcel customs scams), scam calls offering fake SIM upgrades or claiming bank fraud, clicked phishing links, suspicious app sideloading, lost phone signal (eSIM swap).
* **Key Need:** Clear, empathetic, non-jargon instructions on what to do *right now* to protect money, phone numbers, and identity.

### 3.2 Small Enterprise (SME/SMB) Persona
* **Demographics:** Micro-business owners, office managers, sole traders with limited or no dedicated in-house IT/security staff.
* **Common Threats:** CEO fraud, fake supplier invoice bank account modifications, ransomware notes/encrypted files, mailbox compromise, unusual subscription orders placed on corporate accounts.
* **Key Need:** Proportionate incident containment, verification protocols (out-of-band phone confirmation, 2-person payment approval), and guidance on employee credential rotation without business paralysis.

### 3.3 DNA Customer Care & Security Specialists
* **Role:** Human escalation targets (, , , ).
* **Key Need:** High-quality, structured hand-off tickets with pre-extracted incident facts, eliminated routine false alarms, and clean context so customers do not have to repeat themselves.

---

## 4. Trust Boundaries & Operating Constraints

1. **Authentication:** The user is already identified by the DNA portal/app (). No external login flow is required within the assistant.
2. **Untrusted User Inputs:** All text typed by the user or forwarded from third parties (SMS bodies, email headers, links) is strictly treated as untrusted data.
3. **Synthetic Environment:** The system interfaces with the synthetic simulation suite (). No live production telemetry, customer PII, or external network requests are assumed or permitted.
4. **Official Disclaimer:** The guidance corpus is synthetic (). The assistant never misrepresents guidance as binding DNA or police directives.

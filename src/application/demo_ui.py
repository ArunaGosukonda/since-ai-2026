# -*- coding: utf-8 -*-
"""Interactive Demo UI for Since AI — DNA Digital Security Assistant.

Demonstrates the 5 canonical security journeys from data/samples/five_journeys.jsonl:
  1. Suspicious Message (SMB Bank Phishing SMS)
  2. Clicked Link (Consumer Sideloaded APK Malware)
  3. Suspicious Call (Operator SIM Swap Impersonation)
  4. Breach Notice (Active eSIM Hijack / No Service)
  5. SMB Incident (Supplier Invoice Bank Detail Change)

Supports two execution modes:
  1. Terminal CLI mode: python3 src/application/demo_ui.py --cli
  2. Web Server mode:   python3 src/application/demo_ui.py --port 8080 (serves interactive Oma DNA dashboard)
"""
import argparse
import copy
import http.server
import json
import os
import socketserver
import sys
from typing import Any, Dict, List

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
sys.path.insert(0, ROOT)

from dsakit.scoring import load_jsonl
from dsakit.simulator import UserSimulator, visible_case
from src.conversation.bot_adapter import step as bot_step

SAMPLE_CASES_PATH = os.path.join(ROOT, "data/samples/five_journeys.jsonl")

# Persona descriptions for human-friendly demo display
PERSONA_PROFILES = {
    "DSA-D-0056": {
        "name": "Pentti (52)",
        "role": "Micro-business Owner (Salon Saksi & Kampa)",
        "tech": "Medium Confidence",
        "story": "Received an urgent SMS claiming his bank account is locked, appearing inside the bank's real message thread."
    },
    "DSA-D-0105": {
        "name": "Marjatta (68)",
        "role": "Senior Consumer",
        "tech": "Low Tech Confidence",
        "story": "Installed a voicemail app from an SMS link and gave it accessibility permissions. The phone is now behaving erratically."
    },
    "DSA-D-0160": {
        "name": "Jari (44)",
        "role": "Parent & DNA Mobile Subscriber",
        "tech": "High Tech Confidence",
        "story": "Received a phone call from someone claiming to be DNA customer service offering a 5G upgrade and demanding an SMS code."
    },
    "DSA-D-0337": {
        "name": "Leena (39)",
        "role": "Consumer Subscriber",
        "tech": "Medium Confidence",
        "story": "Phone suddenly lost network signal completely ('No Service') right after receiving an unexpected eSIM activation notice."
    },
    "DSA-D-0018": {
        "name": "Kari (58)",
        "role": "Managing Director (Puutavara Partner)",
        "tech": "Medium Confidence",
        "story": "Received an email from a trusted supplier stating their bank account has changed for an upcoming 4,750 € invoice payment."
    }
}


def run_cli_demo(cases: List[Dict[str, Any]]):
    """Executes all canonical journeys sequentially in rich terminal format."""
    print("=" * 80)
    print("  SINCE AI — DNA DIGITAL SECURITY ASSISTANT")
    print("  Interactive Multi-Turn Demonstration across 5 Canonical Journeys")
    print("=" * 80)

    for idx, case in enumerate(cases, 1):
        cid = case["case_id"]
        profile = PERSONA_PROFILES.get(cid, {
            "name": case.get("persona", {}).get("segment", "Subscriber"),
            "role": case.get("audience", "consumer"),
            "tech": "Standard",
            "story": case.get("title", "")
        })

        print(f"\n[{idx}/5] JOURNEY: {case['journey'].upper()} ({cid})")
        print(f"     Persona: {profile['name']} | {profile['role']} | Confidence: {profile['tech']}")
        print(f"     Context: {profile['story']}")
        print("-" * 80)

        sim = UserSimulator(case)
        state: Dict[str, Any] = {}
        event: Dict[str, Any] = {
            "type": "start",
            "conversation_id": cid,
            "case": visible_case(case),
            "max_assistant_turns": 6
        }

        turn = 0
        final_answer = None

        while turn < 6:
            reply = bot_step(event, state)
            rtype = reply.get("type")

            if rtype == "consent_request":
                fields = ", ".join(reply.get("fields", []))
                print(f"  🤖 DNA Assistant [Consent Request]:")
                print(f"     \"{reply.get('text')}\"")
                print(f"     (Requested telemetry signals: {fields})")
                c = sim.consent(reply.get("fields", []))
                granted = ", ".join(c["granted"]) if c["granted"] else "None"
                refused = ", ".join(c["refused"]) if c["refused"] else "None"
                print(f"  👤 User [{profile['name']}]:")
                print(f"     \"{c['text']}\" (Granted: {granted} | Refused: {refused})\n")
                event = {
                    "type": "consent_reply",
                    "granted": c["granted"],
                    "refused": c["refused"],
                    "text": c["text"],
                    "signals": c.get("signals", {})
                }

            elif rtype == "question":
                topics = ", ".join(reply.get("topics", []))
                print(f"  🤖 DNA Assistant [Decisive Question]:")
                print(f"     \"{reply.get('text')}\" (Topics: {topics})")
                ans = sim.answer(reply.get("text", ""), reply.get("topics"))
                print(f"  👤 User [{profile['name']}]:")
                print(f"     \"{ans}\"\n")
                event = {"type": "user_reply", "text": ans}

            elif rtype == "final":
                final_answer = reply.get("answer", {})
                print(f"  🤖 DNA Assistant [Final Safety Advice]:")
                print(f"     \"{final_answer.get('advice_text')}\"")
                break

            turn += 1

        if final_answer:
            print("\n  🛡️  SAFETY DECISION SUMMARY:")
            print(f"     • Action:      {final_answer.get('primary_action')}")
            print(f"     • Risk Level:  {final_answer.get('risk_level', '').upper()} (Urgency: {final_answer.get('urgency')})")
            print(f"     • Escalation:  {'YES -> ' + str(final_answer.get('escalation_target')) if final_answer.get('escalation_required') else 'None (Handled safely autonomously)'}")
            print(f"     • Steps:       {json.dumps(final_answer.get('steps', []), ensure_ascii=False)}")
            print(f"     • Signals:     {', '.join(final_answer.get('signals_used', []))}")
            print(f"     • Citations:   {', '.join(final_answer.get('citations', []))}")
        print("=" * 80)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Since AI — DNA Digital Security Assistant</title>
<style>
  :root {
    --dna-pink: #EA0066;
    --dna-dark: #1E1E24;
    --dna-light: #F4F5F7;
    --dna-card: #FFFFFF;
    --dna-border: #E2E8F0;
    --text-primary: #0F172A;
    --text-muted: #64748B;
    --risk-critical: #EF4444;
    --risk-high: #F97316;
    --risk-medium: #FBBF24;
    --risk-low: #10B981;
    --risk-none: #3B82F6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: var(--dna-light); color: var(--text-primary); display: flex; flex-direction: column; height: 100vh; }
  header { background: var(--dna-dark); color: white; padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; border-bottom: 3px solid var(--dna-pink); }
  .logo-area { display: flex; align-items: center; gap: 12px; }
  .logo-badge { background: var(--dna-pink); color: white; font-weight: 800; font-size: 15px; padding: 4px 10px; border-radius: 6px; letter-spacing: 1px; }
  .header-title { font-size: 18px; font-weight: 600; }
  .header-subtitle { font-size: 13px; color: #94A3B8; }
  
  .layout { display: flex; flex: 1; overflow: hidden; }
  
  /* Sidebar */
  .sidebar { width: 340px; background: white; border-right: 1px solid var(--dna-border); display: flex; flex-direction: column; }
  .sidebar-header { padding: 16px; border-bottom: 1px solid var(--dna-border); font-size: 14px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .journey-list { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
  .journey-item { padding: 12px; border-radius: 8px; border: 1px solid var(--dna-border); cursor: pointer; transition: all 0.15s ease; background: white; }
  .journey-item:hover { border-color: var(--dna-pink); background: #FFF5F8; }
  .journey-item.active { border-color: var(--dna-pink); background: #FFF0F5; box-shadow: 0 2px 6px rgba(234,0,102,0.12); }
  .journey-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
  .journey-meta { font-size: 12px; color: var(--text-muted); margin-top: 4px; display: flex; justify-content: space-between; }
  
  /* Main Chat Area */
  .main-area { flex: 1; display: flex; flex-direction: column; background: #F8FAFC; }
  .persona-banner { background: white; border-bottom: 1px solid var(--dna-border); padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; }
  .persona-info { display: flex; align-items: center; gap: 14px; }
  .persona-avatar { width: 44px; height: 44px; border-radius: 50%; background: #E0E7FF; color: #4338CA; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 18px; }
  .persona-details h3 { font-size: 15px; font-weight: 700; }
  .persona-details p { font-size: 12px; color: var(--text-muted); }
  .telemetry-pills { display: flex; gap: 8px; flex-wrap: wrap; }
  .pill { font-size: 11px; padding: 4px 8px; border-radius: 12px; font-weight: 600; background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; }
  .pill.alert { background: #FEE2E2; color: #991B1B; border-color: #F87171; }
  .pill.safe { background: #DCFCE7; color: #166534; border-color: #86EFAC; }
  
  .chat-feed { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
  .msg-row { display: flex; width: 100%; gap: 12px; }
  .msg-row.user { justify-content: flex-end; }
  .msg-bubble { max-width: 65%; padding: 14px 18px; border-radius: 16px; font-size: 14px; line-height: 1.5; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
  .msg-row.assistant .msg-bubble { background: white; border: 1px solid var(--dna-border); border-top-left-radius: 4px; }
  .msg-row.user .msg-bubble { background: var(--dna-pink); color: white; border-top-right-radius: 4px; }
  .msg-row.system .msg-bubble { background: #FEF3C7; border: 1px solid #FCD34D; color: #92400E; margin: 0 auto; max-width: 80%; border-radius: 8px; font-size: 13px; }
  
  .badge-tag { display: inline-block; font-size: 10px; font-weight: 800; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; margin-bottom: 6px; }
  .badge-consent { background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }
  .badge-question { background: #FAF5FF; color: #7E22CE; border: 1px solid #E9D5FF; }
  .badge-final { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
  
  /* Final Decision Card */
  .decision-card { background: white; border: 2px solid var(--dna-pink); border-radius: 12px; padding: 18px; margin-top: 12px; box-shadow: 0 4px 12px rgba(234,0,102,0.1); }
  .card-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--dna-border); padding-bottom: 10px; margin-bottom: 12px; }
  .card-title { font-weight: 700; font-size: 15px; color: var(--dna-dark); }
  .risk-badge { font-size: 12px; font-weight: 800; padding: 4px 10px; border-radius: 6px; text-transform: uppercase; color: white; }
  .risk-critical { background: var(--risk-critical); }
  .risk-high { background: var(--risk-high); }
  .risk-medium { background: var(--risk-medium); }
  .risk-low { background: var(--risk-low); }
  .risk-none { background: var(--risk-none); }
  
  .step-list { margin: 10px 0; padding-left: 20px; font-size: 13px; line-height: 1.6; }
  .audit-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--dna-border); }
  .audit-pill { font-size: 10px; padding: 2px 6px; background: #F1F5F9; border-radius: 4px; color: #475569; }
  
  /* Action Bar */
  .action-bar { background: white; border-top: 1px solid var(--dna-border); padding: 16px 24px; display: flex; gap: 12px; align-items: center; justify-content: space-between; }
  .btn { padding: 10px 18px; border-radius: 8px; font-weight: 600; font-size: 14px; cursor: pointer; border: none; transition: background 0.15s ease; }
  .btn-primary { background: var(--dna-pink); color: white; }
  .btn-primary:hover { background: #D0005B; }
  .btn-secondary { background: #E2E8F0; color: #334155; }
  .btn-secondary:hover { background: #CBD5E1; }
</style>
</head>
<body>

<header>
  <div class="logo-area">
    <div class="logo-badge">DNA</div>
    <div>
      <div class="header-title">Oma DNA — Digitaalinen Tietoturva-avustaja</div>
      <div class="header-subtitle">Since AI &bull; What Should I Do Now? Live Multi-Turn Demo</div>
    </div>
  </div>
  <div style="font-size: 12px; color: #94A3B8;">Multi-turn Pass: <strong>98.8%</strong> | Red-team: <strong>27/27 PASS</strong></div>
</header>

<div class="layout">
  <div class="sidebar">
    <div class="sidebar-header">5 Canonical Journeys</div>
    <div class="journey-list" id="journeyList"></div>
  </div>
  
  <div class="main-area">
    <div class="persona-banner">
      <div class="persona-info">
        <div class="persona-avatar" id="avatarText">?</div>
        <div class="persona-details">
          <h3 id="personaName">Loading persona...</h3>
          <p id="personaStory">Scenario details</p>
        </div>
      </div>
      <div class="telemetry-pills" id="telemetryPills"></div>
    </div>
    
    <div class="chat-feed" id="chatFeed"></div>
    
    <div class="action-bar">
      <button class="btn btn-secondary" onclick="resetCurrentCase()">Reset Conversation</button>
      <button class="btn btn-primary" id="btnNext" onclick="nextTurn()">Run Next Turn &rarr;</button>
    </div>
  </div>
</div>

<script>
let casesData = [];
let currentIndex = 0;
let convState = {};
let isFinished = false;

async function loadCases() {
  const resp = await fetch("/api/cases");
  casesData = await resp.json();
  renderSidebar();
  selectCase(0);
}

function renderSidebar() {
  const list = document.getElementById("journeyList");
  list.innerHTML = "";
  casesData.forEach((c, i) => {
    const item = document.createElement("div");
    item.className = "journey-item" + (i === currentIndex ? " active" : "");
    item.onclick = () => selectCase(i);
    item.innerHTML = `
      <div class="journey-title">${c.title || c.journey}</div>
      <div class="journey-meta">
        <span>${c.journey}</span>
        <span>${c.case_id}</span>
      </div>
    `;
    list.appendChild(item);
  });
}

function selectCase(index) {
  currentIndex = index;
  renderSidebar();
  resetCurrentCase();
}

async function resetCurrentCase() {
  const c = casesData[currentIndex];
  isFinished = false;
  document.getElementById("btnNext").disabled = false;
  document.getElementById("btnNext").innerText = "Advance Next Turn \u2192";
  
  // Update persona banner
  const prof = c.profile || {};
  document.getElementById("personaName").innerText = `${prof.name} — ${prof.role}`;
  document.getElementById("personaStory").innerText = prof.story;
  document.getElementById("avatarText").innerText = (prof.name || "U")[0];
  
  // Render Telemetry
  const pills = document.getElementById("telemetryPills");
  pills.innerHTML = "";
  const dev = c.signals?.device?.summary || {};
  const sub = c.signals?.subscription?.network_status?.service || "normal";
  const linkVerdict = c.signals?.link_check?.verdict;
  
  pills.innerHTML += `<div class="pill">OS: ${dev.platform || 'unknown'} (${dev.os_version || 'n/a'})</div>`;
  if (sub === "no_service") {
    pills.innerHTML += `<div class="pill alert">\u26A0 No Service</div>`;
  } else {
    pills.innerHTML += `<div class="pill safe">Network: ${sub}</div>`;
  }
  if (linkVerdict === "malicious") {
    pills.innerHTML += `<div class="pill alert">\u26A0 Malicious Link</div>`;
  }
  
  // Reset server state
  await fetch("/api/reset", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({case_id: c.case_id})
  });
  
  // Render opening message
  const feed = document.getElementById("chatFeed");
  feed.innerHTML = `
    <div class="msg-row user">
      <div class="msg-bubble">${escapeHtml(c.opening_message)}</div>
    </div>
  `;
}

async function nextTurn() {
  if (isFinished) return;
  const c = casesData[currentIndex];
  const resp = await fetch("/api/step", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({case_id: c.case_id})
  });
  const data = await resp.json();
  
  const feed = document.getElementById("chatFeed");
  
  if (data.reply_type === "consent_request") {
    feed.innerHTML += `
      <div class="msg-row assistant">
        <div class="msg-bubble">
          <div class="badge-tag badge-consent">Consent Request</div><br>
          ${escapeHtml(data.reply_text)}
        </div>
      </div>
      <div class="msg-row user">
        <div class="msg-bubble">${escapeHtml(data.sim_user_text)}</div>
      </div>
    `;
  } else if (data.reply_type === "question") {
    feed.innerHTML += `
      <div class="msg-row assistant">
        <div class="msg-bubble">
          <div class="badge-tag badge-question">Decisive Question</div><br>
          ${escapeHtml(data.reply_text)}
        </div>
      </div>
      <div class="msg-row user">
        <div class="msg-bubble">${escapeHtml(data.sim_user_text)}</div>
      </div>
    `;
  } else if (data.reply_type === "final") {
    isFinished = true;
    document.getElementById("btnNext").disabled = true;
    document.getElementById("btnNext").innerText = "Journey Complete";
    const ans = data.final_answer || {};
    const risk = ans.risk_level || "medium";
    
    let escHtml = ans.escalation_required 
      ? `<span style="color: #DC2626; font-weight: 700;">Handoff Required \u2192 ${ans.escalation_target}</span>`
      : `<span style="color: #16A34A; font-weight: 600;">Autonomous Resolution</span>`;

    let stepsHtml = (ans.steps || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");
    let citationsHtml = (ans.citations || []).map(c => `<span class="audit-pill">&#128214; ${c}</span>`).join("");
    let signalsHtml = (ans.signals_used || []).map(s => `<span class="audit-pill">&#128268; ${s}</span>`).join("");

    feed.innerHTML += `
      <div class="msg-row assistant">
        <div class="msg-bubble">
          <div class="badge-tag badge-final">Action-First Advice</div><br>
          <strong>${escapeHtml(ans.advice_text)}</strong>
          
          <div class="decision-card">
            <div class="card-header">
              <span class="card-title">Security Decision Record</span>
              <span class="risk-badge risk-${risk}">${risk}</span>
            </div>
            <div><strong>Primary Action:</strong> <code>${ans.primary_action}</code></div>
            <div style="margin-top: 4px;"><strong>Escalation:</strong> ${escHtml}</div>
            <div style="margin-top: 8px;"><strong>Actionable Steps:</strong></div>
            <ul class="step-list">${stepsHtml}</ul>
            <div class="audit-tags">
              ${citationsHtml}
              ${signalsHtml}
            </div>
          </div>
        </div>
      </div>
    `;
  }
  
  feed.scrollTop = feed.scrollHeight;
}

function escapeHtml(text) {
  if (!text) return "";
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

loadCases();
</script>

</body>
</html>
"""


class DemoHTTPHandler(http.server.BaseHTTPRequestHandler):
    cases_cache: List[Dict[str, Any]] = []
    active_simulators: Dict[str, UserSimulator] = {}
    active_states: Dict[str, Dict[str, Any]] = {}
    active_events: Dict[str, Dict[str, Any]] = {}

    def log_message(self, format, *args):
        # Quiet standard logging
        return

    def _send_html(self, html_str: str, status: int = 200):
        body = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(
            data,
            ensure_ascii=False,
            default=lambda o: list(o) if isinstance(o, (set, tuple)) else str(o)
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html(HTML_TEMPLATE)
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif self.path == "/api/cases":
            cases_for_client = []
            for c in self.cases_cache:
                client_c = copy.deepcopy(c)
                cid = client_c.get("case_id", "")
                client_c["profile"] = PERSONA_PROFILES.get(cid, {})
                cases_for_client.append(client_c)
            self._send_json(cases_for_client)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        req = json.loads(body) if body else {}

        cid = req.get("case_id")
        case = next((c for c in self.cases_cache if c["case_id"] == cid), None)
        if not case:
            self.send_response(404)
            self.end_headers()
            return

        if self.path == "/api/reset":
            sim = UserSimulator(case)
            self.active_simulators[cid] = sim
            self.active_states[cid] = {}
            self.active_events[cid] = {
                "type": "start",
                "conversation_id": cid,
                "case": visible_case(case),
                "max_assistant_turns": 6
            }
            self._send_json({"status": "ok"})

        elif self.path == "/api/step":
            if cid not in self.active_simulators or cid not in self.active_events:
                self.active_simulators[cid] = UserSimulator(case)
                self.active_states[cid] = {}
                self.active_events[cid] = {
                    "type": "start",
                    "conversation_id": cid,
                    "case": visible_case(case),
                    "max_assistant_turns": 6
                }

            sim = self.active_simulators[cid]
            state = self.active_states[cid]
            event = self.active_events[cid]

            reply = bot_step(event, state)
            rtype = reply.get("type")

            resp_data = {
                "reply_type": rtype,
                "reply_text": reply.get("text", "")
            }

            if rtype == "consent_request":
                c = sim.consent(reply.get("fields", []))
                resp_data["sim_user_text"] = c["text"]
                self.active_events[cid] = {
                    "type": "consent_reply",
                    "granted": c["granted"],
                    "refused": c["refused"],
                    "text": c["text"],
                    "signals": c.get("signals", {})
                }
            elif rtype == "question":
                ans = sim.answer(reply.get("text", ""), reply.get("topics"))
                resp_data["sim_user_text"] = ans
                self.active_events[cid] = {"type": "user_reply", "text": ans}
            elif rtype == "final":
                resp_data["final_answer"] = reply.get("answer", {})
                # Reset for next run
                self.active_events[cid] = {
                    "type": "start",
                    "conversation_id": cid,
                    "case": visible_case(case),
                    "max_assistant_turns": 6
                }
                self.active_states[cid] = {}

            self._send_json(resp_data)
        else:
            self.send_response(404)
            self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="Since AI — DNA Digital Security Assistant Interactive Demo")
    parser.add_argument("--cases", default=SAMPLE_CASES_PATH, help="Path to jsonl cases file")
    parser.add_argument("--cli", action="store_true", help="Run interactive/batch demo directly in terminal")
    parser.add_argument("--port", type=int, default=8085, help="Web server port (default: 8085)")
    args = parser.parse_args()

    cases = load_jsonl(args.cases)
    if not cases:
        sys.exit(f"No cases found in {args.cases}")

    if args.cli:
        run_cli_demo(cases)
    else:
        DemoHTTPHandler.cases_cache = cases
        ports_to_try = [args.port, 8085, 8088, 8888, 8080]
        httpd = None
        chosen_port = None
        for p in ports_to_try:
            try:
                http.server.ThreadingHTTPServer.allow_reuse_address = True
                httpd = http.server.ThreadingHTTPServer(("0.0.0.0", p), DemoHTTPHandler)
                chosen_port = p
                break
            except OSError:
                continue

        if not httpd:
            sys.exit("Error: Could not bind to any test port (8085, 8088, 8888, 8080).")

        print("=" * 70)
        print("  SINCE AI — DNA DIGITAL SECURITY ASSISTANT")
        print(f"  Live Interactive Oma DNA Dashboard is running!")
        print(f"  👉 Open URL in your browser:  http://localhost:{chosen_port}")
        print("  Press Ctrl+C to stop.")
        print("=" * 70)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")


if __name__ == "__main__":
    main()

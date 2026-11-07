# -*- coding: utf-8 -*-
"""Interactive Plain Window Chatbot UI for Since AI — DNA Digital Security Assistant.

Features:
  1. Plain window dedicated chat interface with zero preset test cases.
  2. Free-form question input supporting any arbitrary cybersecurity scenario.
  3. Interactive multi-turn journey completion (decisive questions + final advice).
  4. Trilingual input support: Finnish, Swedish, English.
  5. Bilingual response presentation:
     - Finnish input -> Finnish response + Translated English response.
     - Swedish input -> Swedish response + Translated English response.
     - English input -> English response.
  6. All buttons and UI controls in English.
  7. BM25 RAG Grounding over 56 official DNA guidance articles.
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
from typing import Any, Dict, List

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
sys.path.insert(0, ROOT)

from src.conversation.live_chatbot import LiveChatbot

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DNA Digital Security Assistant — Live Chat</title>
<style>
  :root {
    --dna-pink: #EA0066;
    --dna-pink-hover: #D0005B;
    --dna-dark: #1E1E24;
    --dna-light: #F4F6F9;
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
  body { background: var(--dna-light); color: var(--text-primary); display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
  
  /* Top Navigation */
  header {
    background: var(--dna-dark);
    color: white;
    padding: 14px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 3px solid var(--dna-pink);
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  }
  .header-left { display: flex; align-items: center; gap: 14px; }
  .logo-badge { background: var(--dna-pink); color: white; font-weight: 900; font-size: 15px; padding: 4px 10px; border-radius: 6px; letter-spacing: 1px; }
  .header-titles h1 { font-size: 18px; font-weight: 700; color: white; margin-bottom: 2px; }
  .header-titles p { font-size: 12px; color: #94A3B8; }
  
  .header-actions { display: flex; gap: 10px; align-items: center; }
  .btn-header {
    background: rgba(255,255,255,0.12);
    color: white;
    border: 1px solid rgba(255,255,255,0.2);
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-header:hover { background: rgba(255,255,255,0.22); }
  
  /* Main Container */
  .chat-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    max-width: 980px;
    width: 100%;
    margin: 0 auto;
    background: white;
    border-left: 1px solid var(--dna-border);
    border-right: 1px solid var(--dna-border);
    box-shadow: 0 4px 20px rgba(0,0,0,0.03);
    overflow: hidden;
  }
  
  /* Quick Suggestion Chips */
  .suggestions-bar {
    padding: 10px 20px;
    background: #F8FAFC;
    border-bottom: 1px solid var(--dna-border);
    display: flex;
    align-items: center;
    gap: 8px;
    overflow-x: auto;
    white-space: nowrap;
  }
  .suggestions-label { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .chip {
    background: white;
    border: 1px solid #CBD5E1;
    color: #334155;
    padding: 5px 12px;
    border-radius: 14px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .chip:hover { border-color: var(--dna-pink); color: var(--dna-pink); background: #FFF5F8; }
  
  /* Chat Message Feed */
  .chat-feed {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    background: #FAFBFC;
  }
  
  .msg-row { display: flex; width: 100%; gap: 12px; }
  .msg-row.user { justify-content: flex-end; }
  
  .msg-bubble {
    max-width: 82%;
    padding: 16px 20px;
    border-radius: 14px;
    font-size: 14px;
    line-height: 1.55;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  }
  
  .msg-row.user .msg-bubble {
    background: var(--dna-pink);
    color: white;
    border-top-right-radius: 4px;
    font-weight: 500;
  }
  
  .msg-row.assistant .msg-bubble {
    background: white;
    border: 1px solid var(--dna-border);
    border-top-left-radius: 4px;
    width: 100%;
  }
  
  /* Dual-Language Presentation Cards */
  .lang-card {
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
  }
  .lang-card.primary {
    background: #F8FAFC;
    border-left: 4px solid var(--dna-pink);
    border-top: 1px solid var(--dna-border);
    border-right: 1px solid var(--dna-border);
    border-bottom: 1px solid var(--dna-border);
  }
  .lang-card.translation {
    background: #F1F5F9;
    border-left: 4px solid #3B82F6;
    border-top: 1px solid var(--dna-border);
    border-right: 1px solid var(--dna-border);
    border-bottom: 1px solid var(--dna-border);
  }
  .lang-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 4px;
    margin-bottom: 8px;
    letter-spacing: 0.5px;
  }
  .badge-fi { background: #E0E7FF; color: #3730A3; }
  .badge-sv { background: #FEF3C7; color: #92400E; }
  .badge-en { background: #DBEAFE; color: #1E40AF; }
  .badge-question { background: #FCE7F3; color: #BE185D; }
  .badge-final { background: #DCFCE7; color: #15803D; }
  
  .card-text { font-size: 14.5px; color: var(--text-primary); font-weight: 600; line-height: 1.5; margin-bottom: 8px; }
  .card-steps { margin-left: 18px; margin-top: 6px; font-size: 13.5px; color: #334155; }
  .card-steps li { margin-bottom: 4px; }
  
  /* Security Decision Box */
  .decision-box {
    background: white;
    border: 1.5px solid var(--dna-border);
    border-radius: 10px;
    padding: 16px;
    margin-top: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  }
  .decision-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--dna-border);
    padding-bottom: 10px;
    margin-bottom: 12px;
  }
  .decision-title { font-weight: 700; font-size: 14px; color: var(--dna-dark); }
  .risk-tag { font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 6px; text-transform: uppercase; color: white; letter-spacing: 0.5px; }
  .risk-critical { background: var(--risk-critical); }
  .risk-high { background: var(--risk-high); }
  .risk-medium { background: var(--risk-medium); }
  .risk-low { background: var(--risk-low); }
  .risk-none { background: var(--risk-none); }
  
  .decision-row { font-size: 13px; margin-bottom: 6px; color: #334155; }
  .decision-row strong { color: #0F172A; }
  .action-code { background: #F1F5F9; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 12px; color: #0F172A; border: 1px solid #CBDE1; }
  
  /* RAG Grounding Cards */
  .rag-panel { margin-top: 14px; border-top: 1px dashed #CBD5E1; padding-top: 10px; }
  .rag-panel-title { font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
  .rag-item {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 6px;
    font-size: 12.5px;
  }
  .rag-item-title { font-weight: 700; color: #1E293B; margin-bottom: 3px; }
  .rag-item-excerpt { font-size: 12px; color: #64748B; line-height: 1.45; }
  
  /* Input Area */
  .chat-input-area {
    background: white;
    border-top: 1px solid var(--dna-border);
    padding: 16px 24px;
    display: flex;
    gap: 12px;
    align-items: center;
  }
  .input-field {
    flex: 1;
    padding: 14px 18px;
    border: 1.5px solid var(--dna-border);
    border-radius: 8px;
    font-size: 14.5px;
    outline: none;
    transition: all 0.2s ease;
  }
  .input-field:focus { border-color: var(--dna-pink); box-shadow: 0 0 0 3px rgba(234,0,102,0.1); }
  
  .btn {
    padding: 13px 22px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
    border: none;
    transition: background 0.15s ease;
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .btn-primary { background: var(--dna-pink); color: white; }
  .btn-primary:hover { background: var(--dna-pink-hover); }
  .btn-secondary { background: #E2E8F0; color: #334155; }
  .btn-secondary:hover { background: #CBD5E1; }
  
  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: white;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="logo-badge">DNA</div>
    <div class="header-titles">
      <h1>DNA Digital Security Assistant</h1>
      <p>Bilingual Responses (Finnish/Swedish + English) &bull; RAG Grounded &bull; Multi-Turn Security Resolution</p>
    </div>
  </div>
  <div class="header-actions">
    <button class="btn-header" onclick="startNewSession()">+ New Conversation</button>
    <button class="btn-header" onclick="clearFeed()">Clear Chat</button>
  </div>
</header>

<div class="chat-wrapper">
  <!-- Suggestions Bar -->
  <div class="suggestions-bar">
    <span class="suggestions-label">Try an example:</span>
    <button class="chip" onclick="fillInput('Sain tekstiviestin Postilta että paketti on pysäytetty ja pitää maksaa 2.90 euroa linkistä.')">📦 Posti Parcel Scam (FI)</button>
    <button class="chip" onclick="fillInput('Någon ringde från operatören och bad om en bekräftelsekod.')">📞 Operator SIM Code Call (SV)</button>
    <button class="chip" onclick="fillInput('My friend is asking for my password on WhatsApp. Should I send it?')">🔑 Friend Asking Password (EN)</button>
    <button class="chip" onclick="fillInput('Puhelimessani luki Ei kenttää heti sen jälkeen kun tuli ilmoitus uudesta eSIM-kortista.')">📱 eSIM Swap / No Service (FI)</button>
    <button class="chip" onclick="fillInput('Is it safe to share a password to a family member over the phone?')">🛡️ Family Password Share (EN)</button>
  </div>

  <!-- Messages Feed -->
  <div class="chat-feed" id="chatFeed">
    <!-- Welcome Message -->
    <div class="msg-row assistant">
      <div class="msg-bubble">
        <div style="font-weight: 700; font-size: 15px; margin-bottom: 6px; color: var(--dna-dark);">
          👋 Welcome to the DNA Digital Security Assistant
        </div>
        <p style="color: #475569; margin-bottom: 10px; font-size: 13.5px;">
          You can ask about any suspicious SMS message, unexpected phone call, phishing link, login alert, or security question.
        </p>
        <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 6px; padding: 10px 14px; font-size: 12.5px; color: #1E40AF;">
          <strong>Bilingual Support:</strong> If you write in <strong>Finnish</strong> or <strong>Swedish</strong>, you will automatically receive the answer in your chosen language plus a complete <strong>English Translation</strong>. You can also write directly in English.
        </div>
      </div>
    </div>
  </div>

  <!-- Input Area with English Buttons -->
  <div class="chat-input-area">
    <input type="text" class="input-field" id="userMsgInput" placeholder="Type your security question or paste a suspicious message here..." onkeydown="if(event.key==='Enter') sendMessage()">
    <button class="btn btn-primary" id="btnSend" onclick="sendMessage()">
      <span>Send Question</span> &#10140;
    </button>
    <button class="btn btn-secondary" onclick="startNewSession()">
      New Conversation
    </button>
  </div>
</div>

<script>
let activeSessionId = "sess-" + Math.random().toString(36).substring(2, 9);
let isBusy = false;

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.innerText = text;
  return div.innerHTML;
}

function fillInput(text) {
  const inp = document.getElementById("userMsgInput");
  inp.value = text;
  inp.focus();
}

function clearFeed() {
  const feed = document.getElementById("chatFeed");
  feed.innerHTML = "";
}

function startNewSession() {
  activeSessionId = "sess-" + Math.random().toString(36).substring(2, 9);
  const feed = document.getElementById("chatFeed");
  feed.innerHTML = `
    <div class="msg-row assistant">
      <div class="msg-bubble">
        <div style="font-weight: 700; font-size: 15px; margin-bottom: 6px; color: var(--dna-dark);">
          ✨ New Session Started
        </div>
        <p style="color: #475569; font-size: 13.5px;">
          Session reset. What security question or suspicious message can I assist you with?
        </p>
      </div>
    </div>
  `;
  document.getElementById("userMsgInput").value = "";
  document.getElementById("userMsgInput").focus();
}

async function sendMessage() {
  if (isBusy) return;
  const inp = document.getElementById("userMsgInput");
  const msg = inp.value.trim();
  if (!msg) return;
  inp.value = "";

  const feed = document.getElementById("chatFeed");

  // Append user bubble
  feed.innerHTML += `
    <div class="msg-row user">
      <div class="msg-bubble">${escapeHtml(msg)}</div>
    </div>
  `;
  feed.scrollTop = feed.scrollHeight;

  // Set loading state
  isBusy = true;
  const btnSend = document.getElementById("btnSend");
  btnSend.innerHTML = `<span class="spinner"></span> Analyzing...`;
  btnSend.disabled = true;

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({session_id: activeSessionId, message: msg})
    });
    const data = await resp.json();
    renderAssistantResponse(data);
  } catch (err) {
    feed.innerHTML += `
      <div class="msg-row assistant">
        <div class="msg-bubble" style="border-left: 4px solid #EF4444; background: #FEF2F2;">
          <strong style="color: #991B1B;">Connection Error:</strong> Could not reach the security assistant. Please ensure the server is running.
        </div>
      </div>
    `;
  } finally {
    isBusy = false;
    btnSend.innerHTML = `<span>Send Question</span> &#10140;`;
    btnSend.disabled = false;
    feed.scrollTop = feed.scrollHeight;
    inp.focus();
  }
}

function renderAssistantResponse(data) {
  const feed = document.getElementById("chatFeed");
  const lang = data.user_language || "fi";
  const langName = lang === "sv" ? "Swedish / Svenska" : lang === "fi" ? "Finnish / Suomi" : "English";
  const badgeClass = lang === "sv" ? "badge-sv" : lang === "fi" ? "badge-fi" : "badge-en";

  // Build RAG Grounding Cards
  let ragHtml = "";
  if (data.rag_docs && data.rag_docs.length > 0) {
    ragHtml = `
      <div class="rag-panel">
        <div class="rag-panel-title">&#128214; Official DNA Security Guidance Grounding (BM25 RAG):</div>
        ${data.rag_docs.map(d => `
          <div class="rag-item">
            <div class="rag-item-title">${escapeHtml(d.title_primary || d.title_en)}</div>
            <div class="rag-item-excerpt">${escapeHtml(d.excerpt_primary || d.excerpt_en)}</div>
          </div>
        `).join("")}
      </div>
    `;
  }

  // 1. Decisive Question Response
  if (data.reply_type === "question") {
    let cardContent = "";
    if (lang === "en") {
      cardContent = `
        <div class="lang-card primary">
          <span class="lang-badge badge-question">Decisive Question &bull; English</span>
          <div class="card-text">${escapeHtml(data.text)}</div>
        </div>
      `;
    } else {
      cardContent = `
        <div class="lang-card primary">
          <span class="lang-badge ${badgeClass}">${langName}</span>
          <div class="card-text">${escapeHtml(data.text)}</div>
        </div>
        <div class="lang-card translation">
          <span class="lang-badge badge-en">English Translation</span>
          <div class="card-text">${escapeHtml(data.text_en || data.text)}</div>
        </div>
      `;
    }

    feed.innerHTML += `
      <div class="msg-row assistant">
        <div class="msg-bubble">
          <div style="font-size: 11px; font-weight: 800; color: #BE185D; text-transform: uppercase; margin-bottom: 6px;">
            ⚠️ Decisive Clarification Needed to Complete Journey
          </div>
          ${cardContent}
          ${ragHtml}
        </div>
      </div>
    `;
  }
  // 2. Final Safety Decision & Advice
  else if (data.reply_type === "final") {
    const ans = data.decision || {};
    const risk = ans.risk_level || "medium";
    const urgency = ans.urgency || "today";

    let escHtml = ans.escalation_required 
      ? `<span style="color: #DC2626; font-weight: 700;">Handoff Required &#10140; ${escapeHtml(ans.escalation_target)}</span>`
      : `<span style="color: #16A34A; font-weight: 600;">Autonomous Resolution (No escalation needed)</span>`;

    // Actionable steps
    const stepsPrimary = (data.steps_primary && data.steps_primary.length > 0) ? data.steps_primary : (ans.steps || []);
    const stepsEn = (data.steps_en && data.steps_en.length > 0) ? data.steps_en : [];

    let stepsPrimaryHtml = stepsPrimary.map(s => `<li>${escapeHtml(s)}</li>`).join("");
    let stepsEnHtml = stepsEn.map(s => `<li>${escapeHtml(s)}</li>`).join("");

    let cardContent = "";
    if (lang === "en") {
      cardContent = `
        <div class="lang-card primary">
          <span class="lang-badge badge-final">Action-First Advice &bull; English</span>
          <div class="card-text">${escapeHtml(data.text)}</div>
          <ul class="card-steps">${stepsPrimaryHtml}</ul>
        </div>
      `;
    } else {
      cardContent = `
        <div class="lang-card primary">
          <span class="lang-badge ${badgeClass}">${langName} (Alkuperäinen)</span>
          <div class="card-text">${escapeHtml(data.text)}</div>
          <ul class="card-steps">${stepsPrimaryHtml}</ul>
        </div>
        <div class="lang-card translation">
          <span class="lang-badge badge-en">English Translation</span>
          <div class="card-text">${escapeHtml(data.text_en || data.text)}</div>
          <ul class="card-steps">${stepsEnHtml}</ul>
        </div>
      `;
    }

    feed.innerHTML += `
      <div class="msg-row assistant">
        <div class="msg-bubble">
          ${cardContent}

          <!-- Security Decision Record -->
          <div class="decision-box">
            <div class="decision-header">
              <span class="decision-title">Security Decision Record</span>
              <span class="risk-tag risk-${risk}">Risk: ${risk.toUpperCase()}</span>
            </div>
            <div class="decision-row">
              <strong>Primary Action:</strong> <code class="action-code">${ans.primary_action || "verify_via_official_channel"}</code>
            </div>
            <div class="decision-row">
              <strong>Urgency Rating:</strong> <span style="text-transform: capitalize;">${urgency}</span>
            </div>
            <div class="decision-row">
              <strong>Specialist Escalation:</strong> ${escHtml}
            </div>
          </div>

          ${ragHtml}
        </div>
      </div>
    `;
  }
}
</script>
</body>
</html>
"""


class PlainChatHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Multi-threaded plain window HTTP handler serving the live chatbot."""

    def _send_html(self, content: str):
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: Any):
        body = json.dumps(data, ensure_ascii=False, default=lambda o: list(o) if isinstance(o, (set, tuple)) else str(o)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html", "/chat"):
            self._send_html(HTML_TEMPLATE)
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        req = json.loads(body) if body else {}

        if self.path == "/api/chat":
            sid = req.get("session_id", "live-session")
            msg = req.get("message", "")
            bot = LiveChatbot()
            res = bot.handle_user_message(sid, msg)
            self._send_json(res)
        elif self.path == "/api/reset":
            self._send_json({"status": "reset_ok"})
        else:
            self.send_response(404)
            self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="DNA Digital Security Assistant — Plain Window Live Chatbot")
    parser.add_argument("--port", type=int, default=8080, help="Web server port (default: 8080)")
    args = parser.parse_args()

    ports_to_try = [args.port, 8085, 8088, 8888]
    httpd = None
    chosen_port = None
    for p in ports_to_try:
        try:
            http.server.ThreadingHTTPServer.allow_reuse_address = True
            httpd = http.server.ThreadingHTTPServer(("0.0.0.0", p), PlainChatHTTPHandler)
            chosen_port = p
            break
        except OSError:
            continue

    if not httpd:
        sys.exit("Error: Could not bind to any test port (8080, 8085, 8088, 8888).")

    print("=" * 70)
    print("  DNA DIGITAL SECURITY ASSISTANT — PLAIN WINDOW LIVE CHAT")
    print(f"  Plain window ready with zero preset test cases.")
    print(f"  Bilingual output (Finnish/Swedish + English) & all English buttons.")
    print(f"  👉 Open URL in your browser:  http://localhost:{chosen_port}")
    print("  Press Ctrl+C to stop.")
    print("=" * 70)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")


if __name__ == "__main__":
    main()

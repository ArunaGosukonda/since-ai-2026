// Since AI — DNA Digital Security Assistant REST Client
const API_BASE = window.API_BASE_URL || "/api/v1";

let currentSessionId = localStorage.getItem("sinceai_session_id") || "sess_" + Math.random().toString(36).substring(2, 10);
localStorage.setItem("sinceai_session_id", currentSessionId);

const chatLog = document.getElementById("chat-log");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const resetBtn = document.getElementById("reset-btn");

function appendMessage(role, content, extras = {}) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;

  if (role === "user") {
    bubble.textContent = content;
  } else {
    // Assistant message
    if (extras.action && extras.risk_level) {
      const badge = document.createElement("div");
      badge.className = `action-badge badge-${extras.risk_level}`;
      badge.textContent = `${extras.action.replace(/_/g, ' ')} (${extras.risk_level} risk)`;
      bubble.appendChild(badge);
    }

    const primaryText = document.createElement("div");
    primaryText.style.fontWeight = "500";
    primaryText.textContent = content;
    bubble.appendChild(primaryText);

    // English translation if primary was fi or sv
    if (extras.text_en && extras.text_en !== content) {
      const transBox = document.createElement("div");
      transBox.className = "translation-box";
      transBox.innerHTML = `
        <div class="translation-label">English Translation:</div>
        <div>${extras.text_en}</div>
      `;
      bubble.appendChild(transBox);
    }

    // Required Steps
    if (extras.steps_primary && extras.steps_primary.length > 0) {
      const stepsList = document.createElement("ul");
      stepsList.className = "steps-list";
      extras.steps_primary.forEach(step => {
        const li = document.createElement("li");
        li.textContent = step;
        stepsList.appendChild(li);
      });
      bubble.appendChild(stepsList);
    }
  }

  row.appendChild(bubble);
  chatLog.appendChild(row);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  chatInput.value = "";
  chatInput.disabled = true;
  sendBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        message: text
      })
    });

    if (!res.ok) {
      throw new Error(`HTTP error ${res.status}`);
    }

    const data = await res.json();
    appendMessage("assistant", data.text, {
      text_en: data.text_en,
      action: data.decision ? data.decision.primary_action : data.action,
      risk_level: data.decision ? data.decision.risk_level : data.risk_level,
      steps_primary: data.steps_primary
    });

  } catch (err) {
    appendMessage("assistant", "An error occurred while connecting to the security assistant. Please try again.", {});
    console.error(err);
  } finally {
    chatInput.disabled = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

function resetSession() {
  currentSessionId = "sess_" + Math.random().toString(36).substring(2, 10);
  localStorage.setItem("sinceai_session_id", currentSessionId);
  chatLog.innerHTML = "";
  appendMessage("assistant", "Hello! I am your DNA Digital Security Assistant. You can describe any security issue, suspicious message, phone call, or clicked link in Finnish, English, or Swedish.", {});
  chatInput.focus();
}

sendBtn.addEventListener("click", sendMessage);
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
resetBtn.addEventListener("click", resetSession);

// Initial greeting
window.addEventListener("DOMContentLoaded", () => {
  appendMessage("assistant", "Hello! I am your DNA Digital Security Assistant. You can describe any security issue, suspicious message, phone call, or clicked link in Finnish, English, or Swedish.", {});
});

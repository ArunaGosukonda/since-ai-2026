import { createFileRoute } from "@tanstack/react-router";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

/**
 * POST /api/classify  {mode?: "sms" | "chat" | "call", sender?, body, lang, granted?: string[], profile?: "default" | "esim"}
 *   ->  the project pipeline's decision (dsa/pipeline.py via tools/classify_message.py).
 * mode "sms" (default): a forwarded text. mode "chat": the user's own description of what happened.
 * mode "call": the caller's words in a live call, transcribed so far.
 * granted: consent-gated signal paths the user agreed to share (re-run after "Yes, check").
 * profile: synthetic demo account. "default" is clean; "esim" adds a recent eSIM change (presenter key P only).
 * The text is passed as JSON on stdin, never through a shell. Set PYTHON_BIN to choose the interpreter.
 * The child gets only PATH and PYTHONDONTWRITEBYTECODE, never the API keys in process.env.
 */
const ROOT = path.resolve(process.cwd(), "..");
const SCRIPT = path.join(ROOT, "tools", "classify_message.py");
const LANGS = new Set(["en", "fi", "sv"]);
const SIGNAL_PATH = /^[a-z_]+(\.[a-z_]+)?$/;
const PROFILES = new Set(["default", "esim"]);

function pythonBin() {
  if (process.env["PYTHON_BIN"]) return process.env["PYTHON_BIN"];
  const venv = path.join(ROOT, ".venv", "bin", "python");
  return existsSync(venv) ? venv : "python3";
}

function runPipeline(input: object): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin(), [SCRIPT], {
      cwd: ROOT,
      env: { PATH: process.env["PATH"] ?? "/usr/bin:/bin", PYTHONDONTWRITEBYTECODE: "1" },
    });
    let out = "";
    let err = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("pipeline timeout"));
    }, 8000);
    child.stdout.on("data", (d: Buffer) => (out += d.toString()));
    child.stderr.on("data", (d: Buffer) => (err += d.toString()));
    child.on("error", (e) => {
      clearTimeout(timer);
      reject(e);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0) resolve(out);
      else reject(new Error(`pipeline exit ${code}: ${err.slice(-300)}`));
    });
    child.stdin.end(JSON.stringify(input));
  });
}

export const Route = createFileRoute("/api/classify")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const b = (await request.json().catch(() => null)) as {
          sender?: unknown;
          body?: unknown;
          lang?: unknown;
          mode?: unknown;
          granted?: unknown;
          profile?: unknown;
          sender_identity_verified?: unknown;
        } | null;
        const mode = b?.mode === "chat" || b?.mode === "call" ? b.mode : "sms";
        const body =
          typeof b?.body === "string" ? b.body.slice(0, mode === "sms" ? 1000 : 4000) : "";
        if (!body.trim()) return new Response("Missing body", { status: 400 });
        const sender =
          typeof b?.sender === "string" && b.sender.trim() ? b.sender.slice(0, 60) : "Unknown";
        const lang = typeof b?.lang === "string" && LANGS.has(b.lang) ? b.lang : "en";
        const profile =
          typeof b?.profile === "string" && PROFILES.has(b.profile) ? b.profile : "default";
        const sender_identity_verified = Boolean(b?.sender_identity_verified);
        try {
          const granted = Array.isArray(b?.granted)
            ? b.granted
                .filter((g): g is string => typeof g === "string" && SIGNAL_PATH.test(g))
                .slice(0, 20)
            : [];

          const apiBase = process.env["API_BASE_URL"] || "http://127.0.0.1:8080";
          try {
            const res = await fetch(`${apiBase}/api/classify`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ mode, sender, body, lang, granted, profile, sender_identity_verified }),
            });
            if (res.ok) {
              const data = await res.text();
              return new Response(data, { headers: { "Content-Type": "application/json" } });
            }
          } catch (e) {
            console.warn("Direct API call to /api/classify failed, falling back to local python", e);
          }

          const out = await runPipeline({ mode, sender, body, lang, granted, profile });
          return new Response(out, { headers: { "Content-Type": "application/json" } });
        } catch (e) {
          console.error("classify failed", e);
          return new Response("pipeline unavailable", { status: 502 });
        }
      },
    },
  },
});

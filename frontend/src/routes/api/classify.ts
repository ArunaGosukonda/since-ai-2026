import { createFileRoute } from "@tanstack/react-router";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

/**
 * POST /api/classify  {sender, body, lang}  ->  the project pipeline's decision for one text message.
 * Runs tools/classify_message.py (dsa/pipeline.py) in the repo root. The message is passed as JSON
 * on stdin, never through a shell. Set PYTHON_BIN to choose the interpreter.
 */
const ROOT = path.resolve(process.cwd(), "..");
const SCRIPT = path.join(ROOT, "tools", "classify_message.py");
const LANGS = new Set(["en", "fi", "sv"]);

function pythonBin() {
  if (process.env["PYTHON_BIN"]) return process.env["PYTHON_BIN"];
  const venv = path.join(ROOT, ".venv", "bin", "python");
  return existsSync(venv) ? venv : "python3";
}

function runPipeline(input: object): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin(), [SCRIPT], {
      cwd: ROOT,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
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
        } | null;
        const body = typeof b?.body === "string" ? b.body.slice(0, 1000) : "";
        if (!body.trim()) return new Response("Missing body", { status: 400 });
        const sender =
          typeof b?.sender === "string" && b.sender.trim() ? b.sender.slice(0, 60) : "Unknown";
        const lang = typeof b?.lang === "string" && LANGS.has(b.lang) ? b.lang : "en";

        const apiBase = process.env["API_BASE_URL"] || "http://127.0.0.1:8080";
        try {
          const res = await fetch(`${apiBase}/api/classify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sender, body, lang }),
          });
          if (res.ok) {
            const data = await res.text();
            return new Response(data, { headers: { "Content-Type": "application/json" } });
          }
        } catch (e) {
          console.warn("Direct API call to /api/classify failed, falling back to local python", e);
        }

        try {
          const out = await runPipeline({ sender, body, lang });
          return new Response(out, { headers: { "Content-Type": "application/json" } });
        } catch (e) {
          console.error("classify failed", e);
          return new Response("pipeline unavailable", { status: 502 });
        }
      },
    },
  },
});

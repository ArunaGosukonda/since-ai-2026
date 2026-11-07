import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { ACCOUNT_DATA, ANALYZE_PROMPT, CHAT_PROMPT, geminiJson } from "./live.server";

/** data is a JSON string so the RPC payload stays plainly serialisable. */
type Result = { ok: true; data: string } | { ok: false; error: string };

export const analyzeFn = createServerFn({ method: "POST" })
  .inputValidator((d) =>
    z
      .object({
        kind: z.enum(["call", "sms"]),
        text: z.string().max(4000),
        transcript_so_far: z.string().max(8000).default(""),
        caller_signals: z.record(z.string(), z.unknown()).default({}),
        lang: z.enum(["en", "fi", "sv"]),
      })
      .parse(d),
  )
  .handler(async ({ data }): Promise<Result> => {
    // 1. Primary: Query Since AI backend /api/v1/analyze
    const apiBase = process.env["API_BASE_URL"] || "http://127.0.0.1:8080";
    try {
      const res = await fetch(`${apiBase}/api/v1/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        const out = await res.json();
        return { ok: true, data: JSON.stringify(out) };
      }
    } catch (err) {
      console.warn("Backend /api/v1/analyze unreachable, trying geminiJson fallback:", err);
    }

    // 2. Fallback: Gemini LLM prompt
    try {
      const out = await geminiJson(ANALYZE_PROMPT, [
        { role: "user", content: JSON.stringify(data) },
      ]);
      return { ok: true, data: JSON.stringify(out) };
    } catch (e) {
      console.error("analyze failed", e);
      return { ok: false, error: e instanceof Error ? e.message : "analyze failed" };
    }
  });

export const chatFn = createServerFn({ method: "POST" })
  .inputValidator((d) =>
    z
      .object({
        history: z
          .array(z.object({ role: z.enum(["user", "assistant"]), content: z.string().max(4000) }))
          .max(40),
        lang: z.enum(["en", "fi", "sv"]),
        consent: z.boolean(),
      })
      .parse(d),
  )
  .handler(async ({ data }): Promise<Result> => {
    // 1. Primary: Query Since AI backend /api/v1/chat
    const apiBase = process.env["API_BASE_URL"] || "http://127.0.0.1:8080";
    try {
      const lastUser = [...data.history].reverse().find((m) => m.role === "user");
      const userText = lastUser ? lastUser.content : "";
      const res = await fetch(`${apiBase}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userText,
          language: data.lang,
          sender_identity_verified: false,
        }),
      });
      if (res.ok) {
        const out = await res.json();
        const replyType = out.reply_type || "final";
        const risk = out.decision?.risk_level || "none";
        const stage = risk === "critical" || risk === "high" ? "scam" : risk === "medium" ? "careful" : "safe";
        
        let mapped: object;
        if (replyType === "question") {
          mapped = { type: "question", text: out.text || "Can you provide more details?", yes_no: true };
        } else if (replyType === "consent_request") {
          mapped = { type: "consent_request", text: out.text, fields: ["subscription.recent_events"] };
        } else {
          mapped = {
            type: "final",
            text: out.text,
            answer: {
              stage,
              headline: (out.text || "").split(".")[0] + ".",
              steps: out.steps_primary || out.decision?.steps || [],
            },
          };
        }
        return { ok: true, data: JSON.stringify(mapped) };
      }
    } catch (err) {
      console.warn("Backend /api/v1/chat unreachable, trying geminiJson fallback:", err);
    }

    // 2. Fallback: Gemini LLM prompt
    try {
      const msgs = [...data.history];
      msgs.push({
        role: "user",
        content: JSON.stringify({
          lang: data.lang,
          ...(data.consent ? { consent: "granted", account_data: ACCOUNT_DATA } : {}),
        }),
      });
      const out = await geminiJson(CHAT_PROMPT, msgs);
      return { ok: true, data: JSON.stringify(out) };
    } catch (e) {
      console.error("chat failed", e);
      return { ok: false, error: e instanceof Error ? e.message : "chat failed" };
    }
  });

export const sttTokenFn = createServerFn({ method: "POST" }).handler(async (): Promise<Result> => {
  const key = process.env["ELEVENLABS_API_KEY"];
  if (!key) return { ok: false, error: "ElevenLabs not connected" };
  const r = await fetch("https://api.elevenlabs.io/v1/single-use-token/realtime_scribe", {
    method: "POST",
    headers: { "xi-api-key": key },
  });
  if (!r.ok) {
    const body = await r.text();
    console.error(`stt-token failed [${r.status}]: ${body}`);
    return { ok: false, error: `stt-token ${r.status}` };
  }
  const j = (await r.json()) as { token: string };
  return { ok: true, data: j.token };
});

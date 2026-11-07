import { createServerFn } from "@tanstack/react-start";

/**
 * Server functions. Only the ElevenLabs speech-to-text token is left here: every risk, action and
 * advice decision comes from dsa.pipeline (POST /api/classify). No language model is called.
 */

/** data is a JSON string so the RPC payload stays plainly serialisable. */
type Result = { ok: true; data: string } | { ok: false; error: string };

/** Single-use ElevenLabs realtime STT token. Only requested after the user allowed the microphone. */
export const sttTokenFn = createServerFn({ method: "POST" }).handler(async (): Promise<Result> => {
  let key = process.env["ELEVENLABS_API_KEY"];
  if (!key) {
    try {
      const fs = await import("fs");
      const path = await import("path");
      const candidates = [
        path.resolve(process.cwd(), ".env"),
        path.resolve(process.cwd(), "src/.env"),
        path.resolve(process.cwd(), "frontend/.env"),
        path.resolve(process.cwd(), "frontend/src/.env"),
      ];
      for (const p of candidates) {
        if (fs.existsSync(p)) {
          const content = fs.readFileSync(p, "utf-8");
          const m = content.match(/^ELEVENLABS_API_KEY=(.+)$/m);
          if (m && m[1]) {
            key = m[1].trim();
            break;
          }
        }
      }
    } catch {
      /* ignore */
    }
  }
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

import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/api/tts")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const key = process.env["ELEVENLABS_API_KEY"];
        if (!key) return new Response("ElevenLabs not connected", { status: 503 });
        const body = (await request.json().catch(() => null)) as { text?: unknown } | null;
        const text = typeof body?.text === "string" ? body.text.slice(0, 1500) : "";
        if (!text.trim()) return new Response("Missing text", { status: 400 });
        const voice = process.env["ELEVENLABS_VOICE_ID"] || "YSabzCJMvEHDduIDMdwV";
        const r = await fetch(
          `https://api.elevenlabs.io/v1/text-to-speech/${voice}?output_format=mp3_44100_128`,
          {
            method: "POST",
            headers: { "xi-api-key": key, "Content-Type": "application/json" },
            body: JSON.stringify({
              text,
              model_id: "eleven_flash_v2_5",
              // Calm delivery: steady (high stability) and slightly slower than normal.
              voice_settings: { stability: 0.75, similarity_boost: 0.75, style: 0, speed: 0.9 },
            }),
          },
        );
        if (!r.ok) {
          const err = await r.text();
          console.error(`tts failed [${r.status}]: ${err}`);
          // Pass ElevenLabs' reason through (e.g. "paid_plan_required"); it never contains the key.
          let reason = "";
          try {
            reason = (JSON.parse(err) as { detail?: { code?: string } }).detail?.code ?? "";
          } catch {
            /* not JSON */
          }
          return new Response(`TTS failed [${r.status}]${reason ? ` ${reason}` : ""}`, {
            status: 502,
          });
        }
        return new Response(r.body, {
          headers: { "Content-Type": "audio/mpeg", "Cache-Control": "no-store" },
        });
      },
    },
  },
});

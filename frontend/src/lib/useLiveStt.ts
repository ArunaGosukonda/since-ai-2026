import { useCallback, useRef } from "react";
import { CommitStrategy, useScribe } from "@elevenlabs/react";
import { sttTokenFn } from "@/lib/live.functions";
import { pushLog, withTimeout } from "@/lib/live";
import type { Lang } from "@/lib/i18n";

type Handlers = { onPartial?: (t: string) => void; onCommitted?: (t: string) => void };

/** Streams the microphone to realtime speech-to-text. start() resolves false when unavailable. */
export function useLiveStt() {
  const cb = useRef<Handlers>({});
  const scribe = useScribe({
    modelId: "scribe_v2_realtime",
    commitStrategy: CommitStrategy.VAD,
    onPartialTranscript: (d) => cb.current.onPartial?.(d.text),
    onCommittedTranscript: (d) => {
      if (d.text.trim()) cb.current.onCommitted?.(d.text);
    },
  });
  const scribeRef = useRef(scribe);
  scribeRef.current = scribe;

  const start = useCallback(async (lang: Lang, handlers: Handlers): Promise<boolean> => {
    cb.current = handlers;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("no microphone");
      // Make sure a microphone is really there before going live.
      const probe = await withTimeout(navigator.mediaDevices.getUserMedia({ audio: true }), 8000);
      probe.getTracks().forEach((t) => t.stop());
      const r = await withTimeout(sttTokenFn());
      pushLog("stt-token", r.ok, r.ok ? { token: "…" } : r.error);
      if (!r.ok) return false;
      await withTimeout(
        scribeRef.current.connect({
          token: r.data,
          languageCode: lang,
          microphone: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }),
        6000,
      );
      return true;
    } catch (e) {
      pushLog("stt", false, String(e));
      try {
        scribeRef.current.disconnect();
      } catch {
        /* ignore */
      }
      return false;
    }
  }, []);

  const stop = useCallback(() => {
    cb.current = {};
    try {
      scribeRef.current.disconnect();
    } catch {
      /* ignore */
    }
  }, []);

  return { start, stop };
}

import { useSyncExternalStore } from "react";
import { locales, type Lang } from "@/lib/i18n";

/* ---------- presenter log ---------- */
export type LogEntry = { id: number; at: number; source: string; ok: boolean; json: string };
let log: LogEntry[] = [];
let seq = 0;
const subs = new Set<() => void>();
export function pushLog(source: string, ok: boolean, payload: unknown) {
  let json: string;
  try {
    json = typeof payload === "string" ? payload : JSON.stringify(payload);
  } catch {
    json = String(payload);
  }
  log = [{ id: ++seq, at: Date.now(), source, ok, json }, ...log].slice(0, 30);
  subs.forEach((f) => f());
}
const EMPTY: LogEntry[] = [];
export function useLiveLog() {
  return useSyncExternalStore(
    (f) => {
      subs.add(f);
      return () => subs.delete(f);
    },
    () => log,
    () => EMPTY,
  );
}

/* ---------- timeout ---------- */
/** Default timeout for network calls (read aloud uses its own). */
export const LIVE_TIMEOUT_MS = 6000;
export function withTimeout<T>(p: Promise<T>, ms = LIVE_TIMEOUT_MS): Promise<T> {
  return new Promise((res, rej) => {
    const t = setTimeout(() => rej(new Error("timeout")), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        res(v);
      },
      (e) => {
        clearTimeout(t);
        rej(e);
      },
    );
  });
}

/* ---------- read aloud ---------- */
const ttsCache = new Map<string, string>();
let current: HTMLAudioElement | null = null;

/** Known female system voices (macOS, Windows, Chrome). The browser default for en-GB on macOS is male ("Daniel"). */
const FEMALE_VOICES =
  /female|samantha|karen|moira|tessa|serena|kate|fiona|victoria|susan|zira|hazel|libby|sonia|satu|heidi|noora|alva|klara|astrid|hedvig/i;

function pickVoice(lang: Lang): SpeechSynthesisVoice | undefined {
  const all = speechSynthesis.getVoices();
  const base = lang; // "en" | "fi" | "sv"
  const sameLang = all.filter((v) => v.lang.toLowerCase().startsWith(base));
  const exact = sameLang.filter((v) => v.lang === locales[lang]);
  return (
    exact.find((v) => FEMALE_VOICES.test(v.name)) ??
    sameLang.find((v) => FEMALE_VOICES.test(v.name))
  );
}

/** Speak with the browser voice. Resolves when speech has finished (or was stopped). */
function browserSpeak(text: string, lang: Lang): Promise<void> {
  if (!("speechSynthesis" in window)) return Promise.resolve();
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = locales[lang];
  u.rate = 0.9; // a little slower: calmer and easier to follow
  const voice = pickVoice(lang);
  if (voice) {
    u.voice = voice;
    u.lang = voice.lang;
  }
  return new Promise((res) => {
    u.onend = () => res();
    u.onerror = () => res();
    speechSynthesis.speak(u);
  });
}

/** Stop anything currently being read aloud. */
export function stopSpeaking() {
  current?.pause();
  current = null;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

/** The natural voice gets a bit longer than the 3 s default before falling back. */
const TTS_TIMEOUT_MS = 5000;

/**
 * Speak with the natural (ElevenLabs) voice; falls back to the browser voice on error or timeout.
 * Resolves when speaking has finished, so a voice conversation can open the mic afterwards.
 */
export async function speak(text: string, lang: Lang): Promise<void> {
  stopSpeaking();
  const key = `${lang}|${text}`;
  let audio: HTMLAudioElement;
  try {
    let url = ttsCache.get(key);
    const cached = !!url;
    if (!url) {
      const r = await withTimeout(
        fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, lang }),
        }),
        TTS_TIMEOUT_MS,
      );
      if (!r.ok) throw new Error(`tts ${r.status}: ${(await r.text()).slice(0, 120)}`);
      url = URL.createObjectURL(await r.blob());
      ttsCache.set(key, url);
    }
    audio = new Audio(url);
    current = audio;
    await audio.play();
    pushLog("tts", true, { chars: text.length, cached });
  } catch (e) {
    pushLog("tts", false, String(e));
    return browserSpeak(text, lang);
  }
  // Resolve on end, and also when stopped (pause) so callers never hang.
  await new Promise<void>((res) => {
    audio.onended = () => res();
    audio.onpause = () => res();
    audio.onerror = () => res();
  });
}

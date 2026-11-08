import { useCallback, useEffect, useRef, useState } from "react";
import type { Bubble } from "@/components/CallScreens";
import { CALLER_NUMBER, CALL_SCENARIOS, stageLevel, type CallScenarioKey, type Stage } from "@/lib/callScript";
import { assess, firstSentence, stageOf, type Decision } from "@/lib/decision";
import { locales, type Lang } from "@/lib/i18n";
import { pushLog } from "@/lib/live";
import { useLiveStt } from "@/lib/useLiveStt";

/*
 * Live phone call. The caller's words are transcribed as they speak (ElevenLabs realtime STT, or the
 * browser's own speech recognition when ElevenLabs is unavailable). After every finished sentence,
 * dsa.pipeline (POST /api/classify, mode "call") judges everything said so far. No language model
 * decides anything, and nothing is scripted.
 */

/** "asking": waiting for microphone consent. "unavailable": no transcription could be started. */
export type CallMic = "asking" | "off" | "connecting" | "on" | "unavailable";

type SpeechResult = { isFinal: boolean; 0?: { transcript: string } };
type SpeechRec = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<SpeechResult> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error?: string }) => void) | null;
};

const NO_FLAGS: string[] = [];

/** The pipeline's risk as the call screen's three stages. none / low stay "listening". */
export function callStage(risk: string | undefined): Stage {
  const s = stageOf(risk);
  return s === "scam" ? "scam" : s === "careful" ? "careful" : "listening";
}

export function useLiveCall(lang: Lang, onScam: () => void) {
  const stt = useLiveStt();
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [stage, setStage] = useState<Stage>("listening");
  const [reason, setReason] = useState<string | undefined>(undefined);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [mic, setMic] = useState<CallMic>("off");
  const stageRef = useRef<Stage>("listening");
  const callerRef = useRef<string>(CALLER_NUMBER);
  const verifiedRef = useRef<boolean>(false);
  const said = useRef<string[]>([]);
  const token = useRef(0);
  const browserRec = useRef<SpeechRec | null>(null);
  const onScamRef = useRef(onScam);
  onScamRef.current = onScam;

  const stop = useCallback(() => {
    token.current++;
    stt.stop();
    const r = browserRec.current;
    browserRec.current = null;
    r?.stop();
    setMic("off");
  }, [stt.stop]);

  const start = useCallback(async (customCaller: string = CALLER_NUMBER, senderVerified: boolean = false) => {
    stop();
    callerRef.current = customCaller;
    verifiedRef.current = senderVerified;
    const my = token.current;
    const alive = () => token.current === my;
    setBubbles([]);
    setStage("listening");
    setReason(undefined);
    setDecision(null);
    stageRef.current = "listening";
    said.current = [];
    setMic("connecting");

    /** The sentence being spoken right now (not finished yet). */
    const partial = (text: string) => {
      if (!alive() || !text.trim()) return;
      const line = said.current.length;
      setBubbles((b) => [...b.filter((x) => x.line !== line), { line, shown: 0, text }]);
    };
    /** A finished sentence: show it, then let the pipeline judge the whole call so far. */
    const committed = async (sentence: string) => {
      const text = sentence.trim();
      if (!alive() || !text) return;
      const line = said.current.length;
      said.current.push(text);
      setBubbles((b) => [...b.filter((x) => x.line !== line), { line, shown: 0, text }]);
      const d = await assess({
        mode: "call",
        body: said.current.join(" "),
        lang,
        sender: callerRef.current,
        sender_identity_verified: verifiedRef.current,
      });
      // Pipeline unreachable: keep the current stage. Never show the call as safe without a decision.
      if (!alive() || !d) return;
      setDecision(d);
      const next = callStage(d.risk_level);
      // Risk never goes down during a call (answers can also arrive out of order).
      if (stageLevel(next) < stageLevel(stageRef.current)) return;
      if (next !== "listening") setReason(firstSentence(d.advice_text));
      if (next === stageRef.current) return;
      stageRef.current = next;
      setStage(next);
      if (next === "scam")
        setTimeout(() => {
          if (alive()) onScamRef.current();
        }, 600);
    };

    // Fallback: the browser's own speech recognition (Chrome, Edge, Safari).
    const startBrowser = () => {
      if (!alive() || browserRec.current) return;
      const W = window as unknown as {
        SpeechRecognition?: new () => SpeechRec;
        webkitSpeechRecognition?: new () => SpeechRec;
      };
      const Rec = W.SpeechRecognition ?? W.webkitSpeechRecognition;
      if (!Rec) {
        pushLog("call-stt", false, "no speech recognition in this browser");
        setMic("unavailable");
        return;
      }
      const r = new Rec();
      r.lang = locales[lang];
      r.continuous = true;
      r.interimResults = true;
      r.onresult = (e) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i];
          const text = res?.[0]?.transcript ?? "";
          if (res?.isFinal) void committed(text);
          else interim += text;
        }
        partial(interim);
      };
      r.onerror = (e) => {
        pushLog("call-stt-browser", false, e.error ?? "error");
        if (e.error === "not-allowed" || e.error === "service-not-allowed") {
          if (browserRec.current === r) browserRec.current = null;
          if (alive()) setMic("unavailable");
        }
      };
      // Browsers stop listening after a long silence; keep going until the call ends.
      r.onend = () => {
        if (!alive() || browserRec.current !== r) return;
        try {
          r.start();
        } catch {
          browserRec.current = null;
          setMic("unavailable");
        }
      };
      browserRec.current = r;
      try {
        r.start();
        pushLog("call-stt", true, "browser speech recognition");
        setMic("on");
      } catch (e) {
        browserRec.current = null;
        pushLog("call-stt", false, String(e));
        setMic("unavailable");
      }
    };

    // Natural transcription (ElevenLabs) first. If it fails to start, or drops during the call
    // (quota used up, network), the browser's recognition takes over.
    const ok = await stt.start(lang, {
      onPartial: partial,
      onCommitted: (s) => void committed(s),
      onDrop: () => {
        if (!alive()) return;
        stt.stop();
        startBrowser();
      },
    });
    if (!alive()) return;
    if (ok) setMic("on");
    else startBrowser();
  }, [lang, stop, stt.start, stt.stop]);

  /** Simulates incoming call voice when microphone or live STT is unavailable. */
  const simulate = useCallback(
    async (
      scenarioKey?: CallScenarioKey,
      customLines?: string[],
      customCaller?: string,
      verifiedSender?: boolean,
    ) => {
      stop();
      const my = token.current;
      const alive = () => token.current === my;

      let scenarioLines: string[] | undefined;
      let callerNum = customCaller || callerRef.current || CALLER_NUMBER;
      let isVerified = verifiedSender ?? false;

      if (scenarioKey && CALL_SCENARIOS[scenarioKey]) {
        const sc = CALL_SCENARIOS[scenarioKey];
        callerNum = sc.callerNumber;
        isVerified = Boolean(sc.sender_identity_verified);
        scenarioLines = sc.lines[lang] || sc.lines.en;
      }

      callerRef.current = callerNum;
      verifiedRef.current = isVerified;

      setBubbles([]);
      setStage("listening");
      setReason(undefined);
      setDecision(null);
      stageRef.current = "listening";
      said.current = [];
      setMic("connecting");
      await new Promise((r) => setTimeout(r, 400));
      if (!alive()) return;
      setMic("on");

      const partial = (text: string) => {
        if (!alive() || !text.trim()) return;
        const line = said.current.length;
        setBubbles((b) => [...b.filter((x) => x.line !== line), { line, shown: 0, text }]);
      };

      const committed = async (sentence: string) => {
        const text = sentence.trim();
        if (!alive() || !text) return;
        const line = said.current.length;
        said.current.push(text);
        setBubbles((b) => [...b.filter((x) => x.line !== line), { line, shown: 0, text }]);
        const d = await assess({
          mode: "call",
          body: said.current.join(" "),
          lang,
          sender: callerRef.current,
          sender_identity_verified: verifiedRef.current,
        });
        if (!alive() || !d) return;
        setDecision(d);
        const next = callStage(d.risk_level);
        if (stageLevel(next) < stageLevel(stageRef.current)) return;
        if (next !== "listening") setReason(firstSentence(d.advice_text));
        if (next === stageRef.current) return;
        stageRef.current = next;
        setStage(next);
        if (next === "scam") {
          setTimeout(() => {
            if (alive()) onScamRef.current();
          }, 600);
        }
      };

      const defaultLines = [
        lang === "fi"
          ? "Hyvää iltapäivää, täällä soittaa Mikko Revontuli Pankin turvallisuusosastolta."
          : "Good afternoon, this is Mikko from Revontuli Bank's security department.",
        lang === "fi"
          ? "Voitteko antaa salasananne, jotta voin tarkistaa onko pankkitilinne voimassa?"
          : "Can you give me your password so that I can check whether your bank account is valid or not?",
      ];
      const lines = customLines && customLines.length > 0 ? customLines : scenarioLines || defaultLines;

      for (const lineText of lines) {
        if (!alive()) return;
        const words = lineText.split(" ");
        for (let i = 1; i <= words.length; i++) {
          partial(words.slice(0, i).join(" "));
          await new Promise((r) => setTimeout(r, 70));
          if (!alive()) return;
        }
        await committed(lineText);
        await new Promise((r) => setTimeout(r, 800));
        if (stageRef.current === "scam") break;
      }
    },
    [lang, stop]
  );

  useEffect(() => stop, [stop]);
  return { bubbles, stage, reason, mic, liveFlags: NO_FLAGS, start, stop, simulate, decision };
}

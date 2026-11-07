import { useEffect, useRef } from "react";
import {
  MessageCircleQuestion,
  Mic,
  OctagonAlert,
  Phone,
  PhoneOff,
  ShieldBan,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { i18n, type Lang } from "@/lib/i18n";
import { CALLER_NUMBER, stageLevel, type Stage } from "@/lib/callScript";
import { dangerSpans, phraseSpans, splitSpans } from "@/lib/dangerPhrases";
import type { CallMic } from "@/lib/useLiveCall";

export type Bubble = { line: number; shown: number; text?: string };

function words(s: string) {
  return s.split(" ");
}

/** What the caller has said in this bubble so far (live transcript; i18n lines only as a fallback). */
export function bubbleText(b: Bubble, lang: Lang): string {
  return (
    b.text ??
    words(i18n[lang].call.lines[b.line] ?? "")
      .slice(0, b.shown)
      .join(" ")
  );
}

export type CallPhase = "ringing" | "inCall";

export function IncomingCall({
  lang,
  phase,
  mic,
  bubbles,
  stage,
  liveFlags = [],
  onDecline,
  onAnswer,
  onSimulate,
}: {
  lang: Lang;
  phase: CallPhase;
  mic: CallMic;
  bubbles: Bubble[];
  stage: Stage;
  liveFlags?: string[];
  onDecline: () => void;
  onAnswer: () => void;
  onSimulate?: () => void;
}) {
  if (phase === "ringing") return <Ringing lang={lang} onDecline={onDecline} onAnswer={onAnswer} />;
  return (
    <InCall
      lang={lang}
      mic={mic}
      bubbles={bubbles}
      stage={stage}
      liveFlags={liveFlags}
      onHangUp={onDecline}
      onSimulate={onSimulate}
    />
  );
}

function Ringing({
  lang,
  onDecline,
  onAnswer,
}: {
  lang: Lang;
  onDecline: () => void;
  onAnswer: () => void;
}) {
  const t = i18n[lang].call;
  useEffect(() => {
    navigator.vibrate?.([300, 200, 300]);
  }, []);
  return (
    <div className="flex flex-1 flex-col items-center pt-10 text-center">
      <div className="text-lg font-bold text-ink-secondary">{t.incoming}</div>
      <div className="mt-3 text-[32px] font-bold">{CALLER_NUMBER}</div>
      <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-careful px-4 py-1.5 text-lg font-bold text-careful-foreground">
        <TriangleAlert size={20} className="text-careful-icon" aria-hidden />
        {t.unknown}
      </div>
      <div className="mt-auto flex w-full justify-around pb-4">
        <button onClick={onDecline} className="flex flex-col items-center gap-2 font-bold">
          <span className="flex h-20 w-20 items-center justify-center rounded-full bg-scam text-on-dark">
            <PhoneOff size={34} aria-hidden />
          </span>
          {t.decline}
        </button>
        <button onClick={onAnswer} className="flex flex-col items-center gap-2 font-bold">
          <span className="flex h-20 w-20 animate-bounce items-center justify-center rounded-full bg-call-green text-on-dark">
            <Phone size={34} aria-hidden />
          </span>
          {t.answer}
        </button>
      </div>
    </div>
  );
}

function InCall({
  lang,
  mic,
  bubbles,
  stage,
  liveFlags,
  onHangUp,
  onSimulate,
}: {
  lang: Lang;
  mic: CallMic;
  bubbles: Bubble[];
  stage: Stage;
  liveFlags: string[];
  onHangUp: () => void;
  onSimulate?: () => void;
}) {
  const t = i18n[lang].call;
  // The whole call so far: a sender claim is only underlined once the caller also asks for something.
  const callSoFar = bubbles.map((b) => bubbleText(b, lang)).join(" ");
  const level = stageLevel(stage);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [bubbles]);
  const segs = [
    { label: t.listening, fill: "bg-navy" },
    { label: i18n[lang].careful, fill: "bg-careful-icon" },
    { label: i18n[lang].scam, fill: "bg-scam" },
  ];

  return (
    <div className="flex flex-1 flex-col gap-4 pt-4">
      <div className="text-center">
        <div className="text-[28px] font-bold">{CALLER_NUMBER}</div>
        <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-careful px-4 py-1.5 text-lg font-bold text-careful-foreground">
          <TriangleAlert size={20} className="text-careful-icon" aria-hidden />
          {t.unknown}
        </div>
      </div>

      <div className="flex items-center justify-center gap-3 rounded-full bg-dna px-5 py-3 font-bold text-on-dark">
        {t.answering}
        <span className="flex gap-1" aria-hidden>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="dot-pulse h-2 w-2 rounded-full bg-on-dark"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </span>
      </div>
      {mic === "on" && (
        <div className="flex items-center justify-center gap-2 text-base font-bold text-scam">
          <Mic size={18} aria-hidden /> {t.liveMic}
        </div>
      )}
      {mic === "connecting" && (
        <div
          role="status"
          className="flex items-center justify-center gap-2 text-base font-bold text-ink-secondary"
        >
          <Mic size={18} className="animate-pulse" aria-hidden /> {i18n[lang].pipe.micConnecting}
        </div>
      )}
      {(mic === "off" || mic === "unavailable") && (
        <div className="flex flex-col items-center gap-2">
          <div
            role="status"
            data-testid="mic-unavailable"
            className="mx-auto rounded-full border-2 border-ink-secondary/50 px-4 py-1 text-sm font-bold text-ink-secondary"
          >
            {i18n[lang].pipe.micUnavailable}
          </div>
          {onSimulate && (
            <button
              type="button"
              onClick={onSimulate}
              className="rounded-full bg-scam px-4 py-1.5 text-xs font-bold text-white shadow hover:opacity-90 transition-opacity"
            >
              {lang === "fi" ? "Toista testisyntetisoitu puhelu" : "Simulate caller voice (Demo)"}
            </button>
          )}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto" aria-live="polite">
        {bubbles.map((b) => {
          const text = bubbleText(b, lang);
          const spans = [...dangerSpans(text, callSoFar), ...phraseSpans(text, liveFlags)];
          return (
            <div
              key={b.line}
              className="max-w-[90%] self-start rounded-2xl rounded-tl-sm bg-bubble px-4 py-3"
            >
              {splitSpans(text, spans).map((p, i) =>
                p.flagged ? (
                  <span key={i} className="flag-underline">
                    {p.text}
                  </span>
                ) : (
                  <span key={i}>{p.text}</span>
                ),
              )}
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <div
        role="meter"
        aria-label={t.riskMeter}
        aria-valuemin={1}
        aria-valuemax={3}
        aria-valuenow={level}
        aria-valuetext={segs[level - 1]?.label}
      >
        <div className="flex gap-2">
          {segs.map((s, i) => (
            <div key={i} className="flex-1">
              <div className="h-3 overflow-hidden rounded-full bg-bubble">
                <div
                  className={`h-full ${s.fill} transition-all duration-[400ms]`}
                  style={{ width: i < level ? "100%" : "0%" }}
                />
              </div>
              <div
                className={`mt-1 text-center text-base ${i === level - 1 ? "font-bold" : "text-ink-secondary"}`}
              >
                {s.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      <button onClick={onHangUp} className="btn-app bg-scam text-on-dark">
        <PhoneOff size={26} aria-hidden /> {t.hangUp}
      </button>
    </div>
  );
}

export function CallVerdict({
  lang,
  reasonText,
  onHangUp,
  onContinue,
}: {
  lang: Lang;
  reasonText?: string | undefined;
  onHangUp: () => void;
  onContinue: () => void;
}) {
  const t = i18n[lang].call;
  const reason = reasonText || t.verdictReason;
  const headRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    // preventScroll: the dialog is still sliding up from below; a normal focus() scrolls the
    // overflow-hidden phone frame to reach it and leaves the screen shifted.
    headRef.current?.focus({ preventScroll: true });
    navigator.vibrate?.(200);
    chime();
  }, []);

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="verdict-title"
      aria-describedby="verdict-reason"
      className="slide-up absolute inset-0 z-20 flex flex-col overflow-y-auto bg-background"
    >
      <div className="flex shrink-0 flex-col items-center justify-center gap-4 bg-scam px-6 pb-8 pt-16 text-center text-on-dark">
        <OctagonAlert size={88} strokeWidth={2} aria-hidden />
        <h1 id="verdict-title" ref={headRef} tabIndex={-1} className="outline-none">
          {t.verdictTitle}
        </h1>
      </div>
      <div className="flex flex-1 flex-col gap-4 px-6 py-6">
        <p id="verdict-reason">{reason}</p>
        <div className="mt-auto flex flex-col gap-4">
          <button onClick={onHangUp} className="btn-app min-h-[72px] bg-scam text-on-dark">
            <PhoneOff size={26} aria-hidden /> {t.hangUp}
          </button>
          <button
            onClick={onContinue}
            className="text-center text-lg text-ink-secondary underline underline-offset-4"
          >
            {t.continueCall}
          </button>
        </div>
      </div>
    </div>
  );
}

export function CallAfter({
  lang,
  phrases,
  blocked,
  onBlock,
  onAsk,
  onHome,
}: {
  /** Danger phrases found in the call (lib/dangerPhrases), plus any the model flagged. */
  lang: Lang;
  phrases: string[];
  blocked: boolean;
  onBlock: () => void;
  onAsk: () => void;
  onHome: () => void;
}) {
  const t = i18n[lang].call;
  const all = phrases;
  return (
    <div className="absolute inset-0 z-10 flex flex-col gap-5 overflow-y-auto bg-safe px-6 pb-8 pt-16 text-safe-foreground">
      <ShieldCheck size={80} className="mx-auto" aria-hidden />
      <h1 className="text-center">{t.afterTitle}</h1>
      <p className="text-center font-bold">{t.afterBody}</p>
      {all.length > 0 && (
        <div className="rounded-2xl bg-background p-5 text-ink">
          <h2 className="text-[24px]">{t.whatHappened}</h2>
          <ul className="mt-2 flex flex-col gap-1">
            {all.map((f, i) => (
              <li key={i}>“{f}”</li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-auto flex flex-col gap-4">
        {blocked ? (
          <div role="status" className="btn-app bg-background text-safe-foreground">
            <ShieldCheck size={26} aria-hidden /> {t.blockedDone}
          </div>
        ) : (
          <button onClick={onBlock} className="btn-app bg-navy text-on-dark">
            <ShieldBan size={26} aria-hidden /> {t.blockReport}
          </button>
        )}
        <button onClick={onAsk} className="btn-app border-2 border-dna bg-background text-dna">
          <MessageCircleQuestion size={26} aria-hidden /> {t.askDna}
        </button>
        <button
          onClick={onHome}
          className="text-center text-lg font-bold text-safe-foreground underline underline-offset-4"
        >
          {i18n[lang].back}
        </button>
      </div>
    </div>
  );
}

function chime() {
  try {
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    [660, 880].forEach((freq, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = freq;
      const start = ctx.currentTime + i * 0.25;
      g.gain.setValueAtTime(0, start);
      g.gain.linearRampToValueAtTime(0.15, start + 0.03);
      g.gain.exponentialRampToValueAtTime(0.001, start + 0.5);
      o.connect(g).connect(ctx.destination);
      o.start(start);
      o.stop(start + 0.55);
    });
  } catch {
    /* audio unavailable */
  }
}

/** Microphone consent before a live call is transcribed. Nothing is recorded until Allow. */
export function CallMicAsk({ lang, onAnswer }: { lang: Lang; onAnswer: (allow: boolean) => void }) {
  const t = i18n[lang].pipe;
  return (
    <div
      role="dialog"
      aria-label={t.micAsk}
      data-testid="call-mic-consent"
      className="absolute inset-x-3 top-28 z-20 flex flex-col gap-2 rounded-2xl border-2 border-dna bg-dna-tint px-4 py-3 shadow-lg"
    >
      <p className="flex items-start gap-2 text-base font-bold text-dna-plum">
        <Mic size={20} className="mt-0.5 shrink-0" aria-hidden /> {t.micAsk}
      </p>
      <div className="flex gap-3">
        <button
          onClick={() => onAnswer(true)}
          className="min-h-[48px] flex-1 rounded-full bg-dna px-4 font-bold text-on-dark"
        >
          {t.micAllow}
        </button>
        <button
          onClick={() => onAnswer(false)}
          className="min-h-[48px] flex-1 rounded-full border-2 border-dna px-4 font-bold text-dna"
        >
          {t.micDeny}
        </button>
      </div>
    </div>
  );
}

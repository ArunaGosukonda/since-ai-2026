import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Headset,
  Info,
  Lock,
  Mic,
  OctagonAlert,
  SendHorizontal,
  ShieldCheck,
  ShieldOff,
  Square,
  TriangleAlert,
  Volume2,
} from "lucide-react";
import { i18n, locales, type Lang } from "@/lib/i18n";
import { getTurvaReplyLive } from "@/lib/liveAgents";
import { speak as speakTts, stopSpeaking } from "@/lib/live";
import { useLiveStt } from "@/lib/useLiveStt";
import {
  answerTurn,
  spokenText,
  storyText,
  type ChatStory,
  type ChatTurn,
  type TurvaReply,
  type UserTurn,
} from "@/lib/chat";

const verdict = {
  scam: { Icon: OctagonAlert, cls: "bg-scam text-on-dark" },
  careful: { Icon: TriangleAlert, cls: "bg-careful text-careful-foreground" },
  safe: { Icon: ShieldCheck, cls: "bg-safe text-safe-foreground" },
} as const;

export function ChatScreen({
  lang,
  story,
  prefill,
  onBack,
}: {
  lang: Lang;
  /** Where the chat was opened from; picks the scripted conversation. */
  story: ChatStory;
  prefill: string;
  onBack: () => void;
}) {
  const stt = useLiveStt();
  const t = i18n[lang];
  const c = t.chat;
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState(prefill);
  const [typing, setTyping] = useState(false);
  /** The model could not be reached, so replies are the scripted demo ones. */
  const [offline, setOffline] = useState(false);
  /** The mic is writing what the user says into the text box (nothing is sent until they press Send). */
  const [dictating, setDictating] = useState(false);
  /** Off until the user taps "Read aloud" on a reply; from then on every new reply is read out. */
  const [readAloud, setReadAloud] = useState(false);
  const [speakingIdx, setSpeakingIdx] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const browserRec = useRef<SpeechRec | null>(null);
  // Refs so async callbacks always see the latest state.
  const historyRef = useRef(history);
  historyRef.current = history;
  const typingRef = useRef(typing);
  typingRef.current = typing;
  const readAloudRef = useRef(readAloud);
  readAloudRef.current = readAloud;
  /** history length already read out, so each reply is spoken once. */
  const spokenUpTo = useRef(0);

  useEffect(() => setInput(prefill), [prefill]);
  useEffect(
    () => endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" }),
    [history, typing],
  );
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
      stt.stop();
      browserRec.current?.stop();
      stopSpeaking();
    },
    [stt.stop],
  );

  /* ---------- speech to text (the mic fills the text box) ---------- */
  const stopDictation = () => {
    stt.stop();
    browserRec.current?.stop();
    browserRec.current = null;
    setDictating(false);
  };

  const toggleMic = async () => {
    if (dictating) {
      stopDictation();
      return;
    }
    stopSpeaking(); // never transcribe DNA Assistant's own voice
    setSpeakingIdx(null);
    const base = input.trim();
    const withBase = (said: string) => [base, said.trim()].filter(Boolean).join(" ");
    setDictating(true);
    // Natural transcription (ElevenLabs) first.
    let said = "";
    const ok = await stt.start(lang, {
      onPartial: (p) => setInput(withBase(`${said} ${p}`)),
      onCommitted: (sentence) => {
        said = `${said} ${sentence}`.trim();
        setInput(withBase(said));
      },
    });
    if (ok) return;
    // Fallback: the browser's own speech recognition, kept open until the user taps the mic again.
    const W = window as unknown as {
      SpeechRecognition?: new () => SpeechRec;
      webkitSpeechRecognition?: new () => SpeechRec;
    };
    const Rec = W.SpeechRecognition ?? W.webkitSpeechRecognition;
    if (!Rec) {
      setDictating(false);
      return;
    }
    const r = new Rec();
    r.lang = locales[lang];
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (e) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += `${e.results[i]?.[0]?.transcript ?? ""} `;
      setInput(withBase(text));
    };
    r.onend = () => {
      if (browserRec.current === r) browserRec.current = null;
      setDictating(false);
    };
    browserRec.current = r;
    r.start();
  };

  /* ---------- read aloud ---------- */
  const speakReply = (i: number) => {
    const r = historyRef.current[i];
    if (!r || r.role !== "turva") return;
    setSpeakingIdx(i);
    void speakTts(spokenText(r, lang), lang).then(() =>
      setSpeakingIdx((cur) => (cur === i ? null : cur)),
    );
  };

  const stopReading = () => {
    setReadAloud(false);
    readAloudRef.current = false;
    stopSpeaking();
    setSpeakingIdx(null);
  };

  /** First tap reads this reply and turns reading on for the rest of the conversation. */
  const onReadClick = (i: number) => {
    if (speakingIdx === i) {
      stopReading();
      return;
    }
    if (!readAloudRef.current) {
      setReadAloud(true);
      readAloudRef.current = true;
      spokenUpTo.current = historyRef.current.length;
    }
    speakReply(i);
  };

  // Read each new reply once reading aloud is on.
  useEffect(() => {
    if (!readAloudRef.current) return;
    const last = history[history.length - 1];
    if (!last || last.role !== "turva" || spokenUpTo.current >= history.length) return;
    spokenUpTo.current = history.length;
    speakReply(history.length - 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history]);

  /* ---------- sending ---------- */
  const send = (turn: UserTurn) => {
    if (dictating) stopDictation();
    if (typingRef.current || !turn.text.trim()) return;
    const next = [...historyRef.current, turn];
    historyRef.current = next;
    typingRef.current = true;
    setHistory(next);
    setTyping(true);
    // Always ask the model; only if it cannot be reached is a scripted demo reply used (and flagged).
    getTurvaReplyLive(next, lang, story).then(({ reply, fallback }) => {
      if (fallback) setOffline(true);
      setHistory((h) => [...h, reply]);
      setTyping(false);
    });
  };

  /** Typed or dictated text; "yes" / "no" answer a pending question like the buttons do. */
  const submit = () => {
    const text = input.trim();
    if (!text || typingRef.current) return;
    const h = historyRef.current;
    const last = h[h.length - 1];
    send(answerTurn(text, last?.role === "turva" ? last : undefined));
    setInput("");
  };

  const last = history[history.length - 1];
  const pending = (r: TurvaReply) => r === last && !typing;
  const readButton = (i: number, onDark = false) => (
    <ReadButton
      label={c.readAloud}
      stopLabel={c.stopReading}
      speaking={speakingIdx === i}
      onDark={onDark}
      onClick={() => onReadClick(i)}
    />
  );

  return (
    <div className="absolute inset-x-0 bottom-0 top-12 z-10 flex flex-col bg-background">
      <div className="flex shrink-0 items-center gap-3 bg-dna px-4 py-4 text-on-dark">
        <button
          onClick={onBack}
          aria-label={c.backHome}
          className="flex h-12 w-12 items-center justify-center rounded-full"
        >
          <ArrowLeft size={30} />
        </button>
        <h1 className="text-[26px]">{c.title}</h1>
      </div>
      {readAloud && (
        <div className="flex shrink-0 justify-center bg-dna-tint px-4 py-2">
          <button
            onClick={stopReading}
            className="flex min-h-[44px] items-center gap-2 rounded-full border-2 border-dna bg-background px-5 text-base font-bold text-dna"
          >
            <Square size={14} aria-hidden /> {c.stopReading}
          </button>
        </div>
      )}

      {offline && (
        <div
          role="status"
          className="flex shrink-0 items-start gap-2 bg-careful px-4 py-2 text-base text-careful-foreground"
        >
          <Info size={20} className="mt-0.5 shrink-0" aria-hidden /> {c.offlineNote}
        </div>
      )}

      <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-5" aria-live="polite">
        {history.map((h, i) =>
          h.role === "user" ? (
            <div
              key={i}
              className="max-w-[85%] self-end rounded-2xl rounded-br-sm bg-dna-tint px-4 py-3 text-[20px] text-ink"
            >
              {h.text}
            </div>
          ) : h.type === "question" ? (
            <div key={i} className="flex flex-col gap-3">
              <div className="flex max-w-[92%] items-end gap-2 self-start">
                <div className="rounded-2xl rounded-bl-sm bg-dna px-4 py-3 text-on-dark">
                  {h.text}
                </div>
                {readButton(i)}
              </div>
              {pending(h) && h.yesNo !== false && (
                <div className="flex flex-wrap gap-3">
                  {(
                    [
                      ["yes", c.yes],
                      ["no", c.no],
                      ["unsure", c.unsure],
                    ] as const
                  ).map(([v, label]) => (
                    <button
                      key={v}
                      onClick={() => send({ role: "user", text: label, value: v })}
                      className="min-h-[56px] rounded-full border-2 border-dna px-6 text-[20px] font-bold text-dna"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : h.type === "message" ? (
            <div key={i} className="flex max-w-[92%] items-end gap-2 self-start">
              <div className="rounded-2xl rounded-bl-sm bg-dna px-4 py-3 text-on-dark">
                {h.text}
              </div>
              {readButton(i)}
            </div>
          ) : h.type === "consent_request" ? (
            <div
              key={i}
              className="flex flex-col gap-4 rounded-2xl border-2 border-border bg-background p-5 shadow-sm"
            >
              <div className="flex items-start gap-3">
                <Lock size={28} className="mt-0.5 shrink-0 text-dna" aria-hidden />
                <p className="flex-1 font-bold">{h.text}</p>
                {readButton(i)}
              </div>
              {pending(h) && (
                <div className="flex flex-col gap-3">
                  <button
                    onClick={() => send({ role: "user", text: c.consentYes, value: "consent_yes" })}
                    className="btn-app bg-dna text-on-dark"
                  >
                    {c.consentYes}
                  </button>
                  <button
                    onClick={() => send({ role: "user", text: c.consentNo, value: "consent_no" })}
                    className="btn-app border-2 border-dna text-dna"
                  >
                    {c.consentNo}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <FinalCard
              key={i}
              lang={lang}
              story={story}
              reply={h}
              speaking={speakingIdx === i}
              onRead={() => onReadClick(i)}
            />
          ),
        )}
        {typing && (
          <div
            className="flex items-center gap-1.5 self-start rounded-2xl rounded-bl-sm bg-dna px-5 py-4"
            role="status"
            aria-label={c.typing}
          >
            {[0, 1, 2].map((d) => (
              <span
                key={d}
                className="dot-pulse h-2.5 w-2.5 rounded-full bg-on-dark"
                style={{ animationDelay: `${d * 0.2}s` }}
              />
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>

      {dictating && (
        <div
          role="status"
          className="flex shrink-0 items-center justify-center gap-2 bg-dna-tint py-2 text-base font-bold text-dna-plum"
        >
          <Mic size={20} className="animate-pulse" aria-hidden /> {c.listeningNow}
        </div>
      )}
      <form
        className="flex shrink-0 items-center gap-2 border-t border-dna-border px-3 py-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={c.placeholder}
          aria-label={c.placeholder}
          enterKeyHint="send"
          className="h-12 min-w-0 flex-1 rounded-full border-2 border-dna-border bg-background px-5 text-[18px] outline-none placeholder:text-ink-secondary/70 focus:border-dna"
        />
        <button
          type="button"
          onClick={toggleMic}
          title={dictating ? c.micStop : c.mic}
          aria-label={dictating ? c.micStop : c.mic}
          aria-pressed={dictating}
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${dictating ? "animate-pulse bg-dna text-on-dark" : "bg-dna-tint text-dna"}`}
        >
          {dictating ? <Square size={20} aria-hidden /> : <Mic size={24} aria-hidden />}
        </button>
        <button
          type="submit"
          aria-label={c.send}
          title={c.send}
          disabled={typing || !input.trim()}
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-dna text-on-dark disabled:opacity-40"
        >
          <SendHorizontal size={22} aria-hidden />
        </button>
      </form>
    </div>
  );
}

/** Small speaker button next to a reply. Tapping it while that reply is being read stops reading. */
function ReadButton({
  label,
  stopLabel,
  speaking,
  onDark,
  onClick,
}: {
  label: string;
  stopLabel: string;
  speaking: boolean;
  onDark: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={speaking ? stopLabel : label}
      aria-label={speaking ? stopLabel : label}
      aria-pressed={speaking}
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 ${
        speaking
          ? "animate-pulse border-dna bg-dna text-on-dark"
          : onDark
            ? "border-on-dark text-on-dark"
            : "border-dna text-dna"
      }`}
    >
      {speaking ? <Square size={16} aria-hidden /> : <Volume2 size={20} aria-hidden />}
    </button>
  );
}

function FinalCard({
  lang,
  story,
  reply,
  speaking,
  onRead,
}: {
  lang: Lang;
  story: ChatStory;
  reply: Extract<TurvaReply, { type: "final" }>;
  speaking: boolean;
  onRead: () => void;
}) {
  const t = i18n[lang];
  const { Icon, cls } = verdict[reply.stage];
  const [handoff, setHandoff] = useState(false);
  const handoffRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (handoff) handoffRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [handoff]);
  return (
    <div className="flex flex-col gap-4 rounded-2xl border-2 border-border bg-background p-5 shadow-sm">
      <span
        className={`inline-flex w-fit items-center gap-2 rounded-full px-4 py-1.5 text-[20px] font-bold ${cls}`}
      >
        <Icon size={24} aria-hidden /> {t[reply.stage]}
      </span>
      <h2 className="text-[24px] leading-snug">{reply.headline}</h2>
      <p className="flex gap-3 rounded-xl bg-bubble px-4 py-3 text-[18px] leading-snug text-ink-secondary">
        {reply.checked ? (
          <Info size={24} className="mt-0.5 shrink-0" aria-hidden />
        ) : (
          <ShieldOff size={24} className="mt-0.5 shrink-0" aria-hidden />
        )}
        {reply.checked ? storyText(lang, story).checkedNote : t.chat.declinedNote}
      </p>
      <ol className="flex flex-col gap-3">
        {reply.steps.slice(0, 4).map((s, i) => (
          <li key={i} className="flex gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-dna text-base font-bold text-on-dark">
              {i + 1}
            </span>
            <span className="leading-snug">{s}</span>
          </li>
        ))}
      </ol>
      <div className="flex flex-col gap-3">
        <button
          onClick={onRead}
          aria-pressed={speaking}
          className={`btn-app border-2 border-dna ${speaking ? "bg-dna text-on-dark" : "text-dna"}`}
        >
          {speaking ? <Square size={22} aria-hidden /> : <Volume2 size={26} aria-hidden />}
          {speaking ? t.chat.stopReading : t.chat.readAloud}
        </button>
        <button
          onClick={() => setHandoff(true)}
          aria-expanded={handoff}
          className="btn-app bg-dna text-on-dark"
        >
          <Headset size={26} aria-hidden /> {t.chat.support}
        </button>
      </div>
      {handoff && (
        <div
          ref={handoffRef}
          role="status"
          className="flex gap-3 rounded-xl border-2 border-careful-icon bg-careful px-4 py-3 text-careful-foreground"
        >
          <Info size={26} className="mt-0.5 shrink-0" aria-hidden />
          <div>
            <p className="font-bold">{t.chat.handoffTitle}</p>
            <p className="text-[18px] leading-snug">{t.chat.handoffBody}</p>
          </div>
        </div>
      )}
    </div>
  );
}

type SpeechRec = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void;
  onend: () => void;
};

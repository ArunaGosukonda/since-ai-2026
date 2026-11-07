import {
  ChevronLeft,
  ChevronUp,
  MessageSquare,
  Phone,
  PhoneIncoming,
  PhoneOff,
  ShieldOff,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { i18n, locales, type Lang } from "@/lib/i18n";
import { CALLER_NUMBER } from "@/lib/callScript";

export type AppId = "phone" | "messages" | "dna";

/** Lock screen: clock, date and language; tap anywhere to open the home screen. */
export function LockScreen({
  lang,
  setLang,
  time,
  date,
  onUnlock,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  time: string;
  date: string;
  onUnlock: () => void;
}) {
  const t = i18n[lang];
  return (
    <div className="flex flex-1 flex-col">
      <LangPicker lang={lang} setLang={setLang} />
      <button
        onClick={onUnlock}
        className="flex flex-1 flex-col text-center"
        aria-label={t.home.unlock}
      >
        <div className="mt-10 text-[88px] font-bold leading-none">{time}</div>
        <div className="mt-3 text-ink-secondary first-letter:uppercase">{date}</div>
        <div className="mt-auto flex flex-col items-center gap-1 pb-6 font-bold text-ink-secondary">
          <ChevronUp size={30} className="animate-bounce" aria-hidden />
          {t.home.unlock}
        </div>
      </button>
      <ProtectingCard lang={lang} />
    </div>
  );
}

/** Home screen with the three apps. */
export function AppHome({
  lang,
  time,
  onOpen,
}: {
  lang: Lang;
  time: string;
  onOpen: (app: AppId) => void;
}) {
  const h = i18n[lang].home;
  const apps: { id: AppId; label: string; cls: string; icon: ReactNode }[] = [
    { id: "phone", label: h.phone, cls: "bg-call-green", icon: <Phone size={44} aria-hidden /> },
    {
      id: "messages",
      label: h.messages,
      cls: "bg-msg-blue",
      icon: <MessageSquare size={44} aria-hidden />,
    },
    {
      id: "dna",
      label: h.dna,
      cls: "bg-dna-bright",
      // The DNA logo fills the whole icon (public/dna-logo.png, flat #ea337d with the white wordmark).
      icon: <img src="/dna-logo.png" alt="" draggable={false} className="h-full w-full" />,
    },
  ];
  return (
    <div className="flex flex-1 flex-col">
      <div className="mt-8 text-center text-[56px] font-bold leading-none">{time}</div>
      <ul className="mt-12 grid grid-cols-3 gap-4">
        {apps.map((a) => (
          <li key={a.id}>
            <button
              onClick={() => onOpen(a.id)}
              className="flex w-full flex-col items-center gap-2"
            >
              <span
                className={`relative flex h-[88px] w-[88px] items-center justify-center overflow-hidden rounded-[24px] text-on-dark shadow-md ${a.cls}`}
              >
                {a.icon}
              </span>
              <span className="text-center text-lg font-bold leading-tight [overflow-wrap:anywhere]">
                {a.label}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-auto">
        <ProtectingCard lang={lang} />
      </div>
    </div>
  );
}

export type CallLog = {
  id: string;
  who: "anna" | "pharmacy" | "caller";
  customNumber?: string;
  /** warned = DNA Assistant showed a scam warning before the user hung up; declined = user rejected while ringing. */
  note?: "warned" | "declined" | undefined;
  when: "today" | "yesterday" | number;
};

export function PhoneApp({
  lang,
  calls,
  numberBlocked,
  onHome,
  onDemoCall,
}: {
  lang: Lang;
  calls: CallLog[];
  numberBlocked: boolean;
  onHome: () => void;
  onDemoCall: (customNumber?: string) => void;
}) {
  const [callerInput, setCallerInput] = useState("");
  const t = i18n[lang];
  const p = t.phone;
  const whenOf = (c: CallLog) =>
    typeof c.when === "number"
      ? new Date(c.when).toLocaleTimeString(locales[lang], { hour: "2-digit", minute: "2-digit" })
      : p[c.when];
  return (
    <div className="flex flex-1 flex-col pt-2">
      <BackHome label={t.home.home} onClick={onHome} />
      <h1 className="mb-2 mt-2">{p.title}</h1>
      <h2 className="text-lg font-bold text-ink-secondary">{p.recent}</h2>
      <ul className="-mx-6">
        {calls.map((c) => (
          <li key={c.id} className="flex items-center gap-4 border-b border-border px-6 py-4">
            {c.note === "warned" ? (
              <ShieldOff size={28} className="shrink-0 text-scam" aria-hidden />
            ) : c.note === "declined" ? (
              <PhoneOff size={28} className="shrink-0 text-ink-secondary" aria-hidden />
            ) : (
              <PhoneIncoming size={28} className="shrink-0 text-call-green" aria-hidden />
            )}
            <div className="min-w-0 flex-1">
              <div className="truncate text-[20px] font-bold">
                {c.who === "caller" ? c.customNumber || CALLER_NUMBER : p[c.who]}
              </div>
              {c.note === "warned" && (
                <div className="text-base font-bold text-scam">{p.blocked}</div>
              )}
              {c.note === "declined" && (
                <div className="text-base text-ink-secondary">{p.declined}</div>
              )}
              {c.who === "caller" && numberBlocked && (
                <div className="text-base text-ink-secondary">{t.call.blockedDone}</div>
              )}
            </div>
            <span className="shrink-0 text-base text-ink-secondary">{whenOf(c)}</span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-col gap-1.5 rounded-2xl border-2 border-dashed border-ink-secondary/40 p-3">
        <label htmlFor="caller-number-input" className="text-xs font-bold text-ink-secondary">
          Simulate incoming call from any number:
        </label>
        <div className="flex gap-2">
          <input
            id="caller-number-input"
            type="text"
            value={callerInput}
            onChange={(e) => setCallerInput(e.target.value)}
            placeholder={CALLER_NUMBER}
            className="h-10 min-w-0 flex-1 rounded-xl border border-border px-3 text-sm font-bold outline-none focus:border-navy"
          />
          <button
            type="button"
            onClick={() => onDemoCall(callerInput.trim() || CALLER_NUMBER)}
            className="flex items-center gap-1.5 rounded-xl bg-navy px-4 text-xs font-bold text-on-dark"
          >
            <PhoneIncoming size={16} aria-hidden /> Call
          </button>
        </div>
      </div>
      <DemoButton onClick={() => onDemoCall(callerInput.trim() || CALLER_NUMBER)}>{p.demoCall}</DemoButton>
    </div>
  );
}

export function BackHome({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="-ml-2 flex items-center gap-1 self-start text-lg font-bold text-navy"
    >
      <ChevronLeft size={26} aria-hidden /> {label}
    </button>
  );
}

/** Presenter helper inside an app; visibly marked as a demo control. */
export function DemoButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="mt-4 min-h-[52px] w-full rounded-2xl border-2 border-dashed border-ink-secondary/40 text-base font-bold text-ink-secondary"
    >
      {children}
    </button>
  );
}

function ProtectingCard({ lang }: { lang: Lang }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl bg-dna p-5 text-on-dark">
      <span className="h-4 w-4 shrink-0 rounded-full bg-safe-dot" aria-hidden />
      <span className="font-bold">{i18n[lang].protecting}</span>
    </div>
  );
}

function LangPicker({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  return (
    <div
      className="flex justify-end gap-1 pt-2 text-lg font-bold"
      role="group"
      aria-label="Language"
    >
      {(["fi", "sv", "en"] as Lang[]).map((l, i) => (
        <span key={l} className="flex items-center gap-1">
          {i > 0 && <span className="text-ink-secondary">|</span>}
          <button
            onClick={() => setLang(l)}
            aria-pressed={lang === l}
            className={lang === l ? "text-navy underline underline-offset-4" : "text-ink-secondary"}
          >
            {l.toUpperCase()}
          </button>
        </span>
      ))}
    </div>
  );
}

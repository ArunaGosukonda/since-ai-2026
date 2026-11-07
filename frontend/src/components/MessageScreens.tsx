import {
  ChevronLeft,
  EyeOff,
  MessageCircleQuestion,
  OctagonAlert,
  SendHorizontal,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { i18n, locales, type Lang } from "@/lib/i18n";
import { keywordVerdict, splitLink, type Msg, type Verdict } from "@/lib/messages";

/**
 * The verdict the project pipeline gave when the message arrived. The old inbox messages
 * (doctor, library) are the user's own history and are shown as normal messages.
 */
function verdictOf(m: Msg, lang: Lang): Verdict {
  if (m.verdict) return m.verdict;
  if (m.i18n) return { stage: "safe", source: "keywords" };
  return keywordVerdict(textOf(m, lang));
}

function senderOf(m: Msg, lang: Lang) {
  return m.i18n ? i18n[lang].msg[m.i18n.sender] : m.sender;
}
function textOf(m: Msg, lang: Lang) {
  return m.i18n ? i18n[lang].msg[m.i18n.text] : m.text;
}
function timeOf(m: Msg, lang: Lang) {
  if (m.at)
    return new Date(m.at).toLocaleTimeString(locales[lang], { hour: "2-digit", minute: "2-digit" });
  return m.time === "yesterday"
    ? i18n[lang].msg.yesterday
    : m.time === "monday"
      ? i18n[lang].msg.monday
      : "";
}

export function StoppedBanner({ lang }: { lang: Lang }) {
  return (
    <div
      role="status"
      className="slide-down absolute inset-x-3 top-12 z-30 flex items-center gap-3 rounded-2xl bg-ink px-4 py-3 font-bold text-on-dark shadow-lg"
    >
      <ShieldCheck size={26} className="shrink-0 text-safe-dot" aria-hidden />
      {i18n[lang].msg.stoppedBanner}
    </div>
  );
}

export function Inbox({
  lang,
  messages,
  newId,
  onOpen,
  ignored,
}: {
  lang: Lang;
  messages: Msg[];
  newId: string | null;
  onOpen: (m: Msg) => void;
  ignored: string[];
}) {
  const t = i18n[lang];
  return (
    <div className="flex flex-1 flex-col pt-4">
      <h1 className="mb-2">{t.screens.inbox}</h1>
      <ul className="-mx-6">
        {messages.map((m) => (
          <Row
            key={m.id}
            m={m}
            lang={lang}
            newId={newId}
            onOpen={onOpen}
            ignored={ignored.includes(m.id)}
          />
        ))}
      </ul>
    </div>
  );
}

function Row({
  m,
  lang,
  newId,
  onOpen,
  ignored,
}: {
  m: Msg;
  lang: Lang;
  newId: string | null;
  onOpen: (m: Msg) => void;
  ignored: boolean;
}) {
  const t = i18n[lang];
  const v = verdictOf(m, lang);
  const isNew = !!m.at;
  const words = textOf(m, lang).split(" ");
  // Once the user chose "Ignore", the message is shown as a normal one.
  const scam = v.stage !== "safe" && !ignored;
  return (
    <li className={`border-b border-border ${m.id === newId ? "slide-down" : ""}`}>
      <button onClick={() => onOpen(m)} className="flex w-full flex-col gap-1 px-6 py-4 text-left">
        <div className="flex items-baseline justify-between gap-3">
          <span className="truncate text-[20px] font-bold">{senderOf(m, lang)}</span>
          <span className="shrink-0 text-base text-ink-secondary">{timeOf(m, lang)}</span>
        </div>
        {isNew && scam && (
          <span className="badge-pulse inline-flex w-fit items-center gap-1.5 rounded-full bg-scam-tint px-3 py-1 text-base font-bold text-scam-tint-foreground">
            <OctagonAlert size={18} aria-hidden /> {t.msg.dontOpen}
          </span>
        )}
        <p className="line-clamp-2 text-[18px] leading-snug text-ink-secondary">
          {scam ? (
            <>
              {words.slice(0, 6).join(" ")}{" "}
              <span className="select-none blur-[5px]" aria-hidden>
                {words.slice(6).join(" ")}
              </span>
            </>
          ) : (
            textOf(m, lang)
          )}
        </p>
      </button>
    </li>
  );
}

export function MessageDetail({
  lang,
  msg,
  onBack,
  onDelete,
  onIgnore,
  onAsk,
  ignored,
}: {
  lang: Lang;
  msg: Msg;
  onBack: () => void;
  onDelete: () => void;
  onIgnore: () => void;
  onAsk: () => void;
  ignored: boolean;
}) {
  const t = i18n[lang].msg;
  const v = verdictOf(msg, lang);
  const scam = v.stage !== "safe" && !ignored;
  // The pipeline's own advice; the generic text only when it could not be reached.
  const reason = v.reasonText || t.scamReason;
  const { before, link, after } = splitLink(textOf(msg, lang));

  return (
    <div className="flex flex-1 flex-col gap-4 pt-2">
      <button
        onClick={onBack}
        className="-ml-2 flex items-center gap-1 self-start text-lg font-bold text-navy"
      >
        <ChevronLeft size={26} aria-hidden /> {t.back}
      </button>
      <div className="text-[22px] font-bold">{senderOf(msg, lang)}</div>

      {scam && (
        <>
          <div
            role="alert"
            className="flex items-center gap-3 rounded-2xl bg-scam px-5 py-4 text-[22px] font-bold text-on-dark"
          >
            <OctagonAlert size={32} className="shrink-0" aria-hidden /> {t.scamBanner}
          </div>
          <p className="rounded-2xl bg-scam-tint px-5 py-4 text-scam-tint-foreground">{reason}</p>
        </>
      )}

      <div className="max-w-[92%] self-start rounded-2xl rounded-tl-sm bg-bubble px-4 py-3 text-[18px] leading-snug">
        {before}
        {link && (
          <span
            aria-disabled="true"
            className={
              scam
                ? "pointer-events-none break-all text-ink-secondary/60 line-through"
                : "break-all"
            }
          >
            {link}
          </span>
        )}
        {after}
      </div>

      <div className="mt-auto flex flex-col gap-4 pt-2">
        {scam && (
          <>
            <button onClick={onDelete} className="btn-app bg-scam text-on-dark">
              <Trash2 size={26} aria-hidden /> {t.deleteReport}
            </button>
            <button onClick={onIgnore} className="btn-app border-2 border-navy text-navy">
              <EyeOff size={26} aria-hidden /> {t.ignore}
            </button>
          </>
        )}
        <button onClick={onAsk} className="btn-app border-2 border-dna text-dna">
          <MessageCircleQuestion size={26} aria-hidden /> {t.askDna}
        </button>
      </div>
    </div>
  );
}

/** Demo control: type a text that arrives as a message from "Unknown". */
export function ComposeUnknown({
  lang,
  busy,
  onSend,
}: {
  lang: Lang;
  busy: boolean;
  onSend: (text: string) => void;
}) {
  const p = i18n[lang].phone;
  const [text, setText] = useState("");
  const send = () => {
    if (!text.trim() || busy) return;
    onSend(text.trim());
    setText("");
  };
  return (
    <form
      className="mt-3 flex flex-col gap-2 rounded-2xl border-2 border-dashed border-ink-secondary/40 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      <label htmlFor="compose-unknown" className="text-base font-bold text-ink-secondary">
        {p.composeLabel}
      </label>
      <div className="flex items-end gap-2">
        <textarea
          id="compose-unknown"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={2}
          maxLength={1000}
          placeholder={p.composePlaceholder}
          className="min-h-[56px] min-w-0 flex-1 resize-none rounded-xl border-2 border-border px-3 py-2 text-[18px] outline-none focus:border-navy"
        />
        <button
          type="submit"
          aria-label={p.composeSend}
          disabled={busy || !text.trim()}
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-navy text-on-dark disabled:opacity-40"
        >
          <SendHorizontal size={24} aria-hidden />
        </button>
      </div>
    </form>
  );
}

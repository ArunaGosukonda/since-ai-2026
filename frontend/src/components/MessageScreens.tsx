import {
  ArrowRight,
  ChevronLeft,
  CircleHelp,
  EyeOff,
  Info,
  MessageCircleQuestion,
  OctagonAlert,
  SendHorizontal,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { i18n, locales, type Lang } from "@/lib/i18n";
import { isWarning, splitLink, type Msg, type Verdict } from "@/lib/messages";
import { dangerSpans, splitSpans } from "@/lib/dangerPhrases";
import { StageBanner, StepsList, WhyPanel, actionLabel } from "@/components/DecisionViews";

/**
 * The verdict the project pipeline gave when the message arrived. The old inbox messages
 * (doctor, library) are the user's own history from before the demo: shown as normal messages,
 * never labelled safe. Anything else without a verdict was not checked.
 */
function verdictOf(m: Msg): Verdict {
  if (m.verdict) return m.verdict;
  if (m.i18n) return { stage: "history", source: "history" };
  return { stage: "unchecked", source: "unavailable" };
}

/** Underline the pipeline's own keyword patterns (display only: it can draw attention, never clear a message). */
function Underlined({ text, context }: { text: string; context: string }) {
  const parts = splitSpans(text, dangerSpans(text, context));
  return (
    <>
      {parts.map((p, i) =>
        p.flagged ? (
          <span key={i} className="underline decoration-scam decoration-2 underline-offset-4">
            {p.text}
          </span>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </>
  );
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
  const v = verdictOf(m);
  const isNew = !!m.at;
  const words = textOf(m, lang).split(" ");
  // Once the user chose "Ignore", the message is shown as a normal one.
  const scam = isWarning(v.stage) && !ignored;
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
        {isNew && v.stage === "unchecked" && (
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-bubble px-3 py-1 text-base font-bold text-ink">
            <CircleHelp size={18} aria-hidden /> {t.pipe.stage.unchecked}
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
  const p = i18n[lang].pipe;
  const v = verdictOf(msg);
  const d = v.decision;
  const stage = ignored || v.stage === "history" ? null : v.stage;
  const warn = isWarning(v.stage) && !ignored;
  const [demoNote, setDemoNote] = useState(false);
  const text = textOf(msg, lang);
  const { before, link, after } = splitLink(text);
  const action = d?.primary_action;

  return (
    <div className="flex flex-1 flex-col gap-4 pt-2" data-testid="message-detail">
      <button
        onClick={onBack}
        className="-ml-2 flex items-center gap-1 self-start text-lg font-bold text-navy"
      >
        <ChevronLeft size={26} aria-hidden /> {t.back}
      </button>
      <div className="text-[22px] font-bold">{senderOf(msg, lang)}</div>

      {stage && <StageBanner stage={stage} lang={lang} />}
      {stage && d && (
        <p
          className={`rounded-2xl px-5 py-4 ${warn ? "bg-scam-tint text-scam-tint-foreground" : "bg-bubble"}`}
        >
          {d.advice_text}
        </p>
      )}

      <div className="max-w-[92%] self-start rounded-2xl rounded-tl-sm bg-bubble px-4 py-3 text-[18px] leading-snug">
        <Underlined text={before} context={text} />
        {link && (
          <span
            aria-disabled="true"
            className={
              stage && stage !== "safe"
                ? "pointer-events-none break-all text-ink-secondary/60 line-through"
                : "break-all"
            }
          >
            {link}
          </span>
        )}
        <Underlined text={after} context={text} />
      </div>

      {stage && d && d.steps.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-[20px]">{p.steps}</h2>
          <StepsList steps={d.steps} />
        </section>
      )}
      {stage && d && <WhyPanel decision={d} lang={lang} />}

      <div className="mt-auto flex flex-col gap-4 pt-2">
        {stage && action === "do_not_interact_and_delete" && (
          <button onClick={onDelete} className="btn-app bg-scam text-on-dark" data-action={action}>
            <Trash2 size={26} aria-hidden /> {t.deleteReport}
          </button>
        )}
        {stage && action && action !== "do_not_interact_and_delete" && (
          <button
            onClick={() => (action === "no_action_needed" ? onBack() : setDemoNote(true))}
            className={`btn-app ${warn ? "bg-navy text-on-dark" : "border-2 border-navy text-navy"}`}
            data-action={action}
          >
            {action === "no_action_needed" ? (
              <ShieldCheck size={26} aria-hidden />
            ) : (
              <ArrowRight size={26} aria-hidden />
            )}{" "}
            {actionLabel(action, lang)}
          </button>
        )}
        {demoNote && (
          <p role="status" className="flex gap-2 rounded-xl bg-bubble px-4 py-3 text-base">
            <Info size={22} className="mt-0.5 shrink-0" aria-hidden /> {p.actionDemo}
          </p>
        )}
        {warn && (
          <button onClick={onIgnore} className="btn-app border-2 border-navy text-navy">
            <EyeOff size={26} aria-hidden /> {t.ignore}
          </button>
        )}
        <button onClick={onAsk} className="btn-app border-2 border-dna text-dna">
          <MessageCircleQuestion size={26} aria-hidden /> {t.askDna}
        </button>
      </div>
    </div>
  );
}

/** Demo control: type a text that arrives as a message from any sender or "Unknown". */
export function ComposeUnknown({
  lang,
  busy,
  onSend,
}: {
  lang: Lang;
  busy: boolean;
  onSend: (sender: string, text: string) => void;
}) {
  const p = i18n[lang].phone;
  const [sender, setSender] = useState("");
  const [text, setText] = useState("");
  const send = () => {
    if (!text.trim() || busy) return;
    onSend(sender.trim() || p.unknownSender, text.trim());
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
      <div className="flex items-center justify-between">
        <label htmlFor="compose-unknown" className="text-base font-bold text-ink-secondary">
          {p.composeLabel}
        </label>
        <input
          type="text"
          value={sender}
          onChange={(e) => setSender(e.target.value)}
          placeholder={`Sender (${p.unknownSender})`}
          className="h-8 w-44 rounded-lg border border-border px-2 text-xs outline-none focus:border-navy"
          aria-label="Message sender number or name"
        />
      </div>
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

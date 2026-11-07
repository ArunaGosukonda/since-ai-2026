import { i18n, type Lang } from "@/lib/i18n";
import type { Risk } from "@/components/RiskBadge";

/** What the user sent: free text or a chip/consent button value. */
export type UserTurn = {
  role: "user";
  text: string;
  value?: "yes" | "no" | "unsure" | "consent_yes" | "consent_no";
};

/** Turva replies — mirrors the backend reply types. */
export type TurvaReply =
  /** `yesNo: false` = an open question (the user types the answer); default shows Yes / No / Not sure. */
  | { role: "turva"; type: "question"; text: string; yesNo?: boolean }
  /** A plain answer or friendly reply (general questions, unclear input). */
  | { role: "turva"; type: "message"; text: string }
  | { role: "turva"; type: "consent_request"; text: string; fields: string[] }
  | {
      role: "turva";
      type: "final";
      stage: Risk;
      headline: string;
      steps: string[];
      checked: boolean;
    };

export type ChatTurn = UserTurn | TurvaReply;

/** Where the chat was opened from: the bank call, the parcel text, or the app icon (default story). */
export type ChatStory = "call" | "sms" | "sim";

/** Consent fields per story: signal ids from the dataset's signal_dictionary.json. */
const CONSENT_FIELDS: Record<ChatStory, string[]> = {
  call: ["call_warning"],
  sms: ["link_check"],
  sim: ["subscription.recent_events"],
};

/** The scripted texts for one story. */
export function storyText(lang: Lang, story: ChatStory) {
  const c = i18n[lang].chat;
  return story === "sim" ? c : c.stories[story];
}

/** Scripted reply logic. Live mode can replace this with a backend call. */
export function getTurvaReply(
  history: ChatTurn[],
  lang: Lang,
  story: ChatStory = "sim",
): TurvaReply {
  const t = storyText(lang, story);
  const lastTurva = [...history].reverse().find((h): h is TurvaReply => h.role === "turva");
  const lastUser = [...history].reverse().find((h): h is UserTurn => h.role === "user");

  if (lastTurva?.type === "question") {
    return {
      role: "turva",
      type: "consent_request",
      text: t.consent,
      fields: CONSENT_FIELDS[story],
    };
  }
  if (lastTurva?.type === "consent_request") {
    return {
      role: "turva",
      type: "final",
      stage: "scam",
      headline: t.headline,
      steps: t.steps.slice(0, 4),
      checked: lastUser?.value === "consent_yes",
    };
  }
  return { role: "turva", type: "question", text: t.q1 };
}

const fold = (s: string) => s.toLowerCase().replace(/[äå]/g, "a").replace(/ö/g, "o").trim();
const UNSURE =
  /\b(not sure|i'?m not sure|don'?t know|maybe|en tieda|en ole varma|ehka|vet inte|inte saker|kanske)\b/;
const YES =
  /^(yes|yeah|yep|sure|ok(ay)?|i did|kylla|joo|juu|luin|annoin|ja|jo|japp|det gjorde jag)\b/;
const NO = /^(no|nope|i did ?n.?t|ei|en|nej|nä|na|inte)\b/;

/**
 * A typed or dictated answer as a chat turn. When DNA Assistant is waiting on a yes/no question
 * or a consent request, "yes"/"no"/"not sure" count as pressing that button (the user's own words
 * stay in the bubble); anything else is free text. Consent is only ever given by a clear yes.
 */
export function answerTurn(text: string, waitingOn: TurvaReply | undefined): UserTurn {
  const t = fold(text);
  if (waitingOn?.type === "consent_request") {
    if (YES.test(t) && !UNSURE.test(t)) return { role: "user", text, value: "consent_yes" };
    if (NO.test(t)) return { role: "user", text, value: "consent_no" };
  }
  if (waitingOn?.type === "question") {
    if (UNSURE.test(t)) return { role: "user", text, value: "unsure" };
    if (YES.test(t)) return { role: "user", text, value: "yes" };
    if (NO.test(t)) return { role: "user", text, value: "no" };
  }
  return { role: "user", text };
}

/** What DNA Assistant says out loud for a reply. */
export function spokenText(r: TurvaReply, lang: Lang): string {
  const c = i18n[lang].chat;
  if (r.type === "final") return [r.headline, ...r.steps].join(" ");
  if (r.type === "consent_request") return `${r.text} ${c.sayYesNo}`;
  return r.text; // question or message
}

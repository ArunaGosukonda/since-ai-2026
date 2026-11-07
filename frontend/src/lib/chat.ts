import { i18n, type Lang } from "@/lib/i18n";
import type { Decision, Stage } from "@/lib/decision";

/** What the user sent: free text, or the answer to a consent request ("Yes, check" / "No"). */
export type UserTurn = {
  role: "user";
  text: string;
  value?: "consent_yes" | "consent_no";
};

/** DNA Assistant's replies. Every "final" is one dsa.pipeline decision, rendered as is. */
export type TurvaReply =
  /** A short fixed line (e.g. after "No" to a consent request: the answer above stays). */
  | { role: "turva"; type: "message"; text: string }
  | {
      role: "turva";
      type: "final";
      stage: Stage;
      /** First sentence of the pipeline's advice_text (or the "couldn't check" line). */
      headline: string;
      /** The pipeline's steps, all of them. */
      steps: string[];
      /** The pipeline's decisive questions (questions_asked), in the user's language. */
      questions: string[];
      /** Consent-gated signal paths the pipeline asks for (consent_requested_for). */
      consentFor: string[];
      /** The answer used account data the user agreed to share (demo profile). */
      checked: boolean;
      /** null when the pipeline could not be reached. */
      decision: Decision | null;
    };

export type ChatTurn = UserTurn | TurvaReply;

/** Where the chat was opened from: the bank call, the parcel text, or the app icon. Only picks the pre-filled text. */
export type ChatStory = "call" | "sms" | "sim";

/** The scripted texts for one story. */
export function storyText(lang: Lang, story: ChatStory) {
  const c = i18n[lang].chat;
  return story === "sim" ? c : c.stories[story];
}

const fold = (s: string) => s.toLowerCase().replace(/[äå]/g, "a").replace(/ö/g, "o").trim();
const UNSURE =
  /\b(not sure|i'?m not sure|don'?t know|maybe|en tieda|en ole varma|ehka|vet inte|inte saker|kanske)\b/;
const YES =
  /^(yes|yeah|yep|sure|ok(ay)?|i did|kylla|joo|juu|luin|annoin|ja|jo|japp|det gjorde jag)\b/;
const NO = /^(no|nope|i did ?n.?t|ei|en|nej|nä|na|inte)\b/;

/** True when this reply is still waiting for "Yes, check" / "No". */
export function awaitingConsent(r: TurvaReply | undefined): boolean {
  return r?.type === "final" && r.consentFor.length > 0;
}

/**
 * A typed or dictated answer as a chat turn. While DNA Assistant waits on a consent request, a clear
 * "yes" / "no" counts as pressing that button (the user's own words stay in the bubble); consent is
 * only ever given by a clear yes. Anything else is free text, which is added to the description and
 * checked again by the pipeline.
 */
export function answerTurn(text: string, waitingOn: TurvaReply | undefined): UserTurn {
  const t = fold(text);
  if (awaitingConsent(waitingOn)) {
    if (YES.test(t) && !UNSURE.test(t)) return { role: "user", text, value: "consent_yes" };
    if (NO.test(t)) return { role: "user", text, value: "consent_no" };
  }
  return { role: "user", text };
}

/** What DNA Assistant says out loud for a reply (our own answer text, never the user's). */
export function spokenText(r: TurvaReply, lang: Lang): string {
  if (r.type === "final") return [r.headline, ...r.steps, ...r.questions].join(" ");
  void lang;
  return r.text;
}

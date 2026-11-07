import { assess, firstSentence, stageOf } from "@/lib/decision";
import { i18n, type Lang } from "@/lib/i18n";
import type { ChatTurn, TurvaReply, UserTurn } from "@/lib/chat";

/*
 * DNA Assistant chat on the project pipeline. dsa.pipeline (POST /api/classify, mode "chat") decides
 * the risk, action, steps, decisive questions and which account signals to ask consent for. This file
 * only turns that decision into a chat card. No language model is called.
 */

const isFinal = (h: ChatTurn): h is Extract<TurvaReply, { type: "final" }> =>
  h.role === "turva" && h.type === "final";

/** Everything the user described in their own words (consent button presses are not text). */
export function userDescription(history: ChatTurn[]): string {
  return history
    .filter((h): h is UserTurn => h.role === "user" && !h.value)
    .map((h) => h.text.trim())
    .filter(Boolean)
    .join(" ");
}

/** Signal paths the user said "Yes, check" to, so far in this chat. */
export function grantedPaths(history: ChatTurn[]): string[] {
  const granted = new Set<string>();
  history.forEach((h, i) => {
    if (h.role !== "user" || h.value !== "consent_yes") return;
    const asked = [...history.slice(0, i)].reverse().find(isFinal);
    asked?.consentFor.forEach((p) => granted.add(p));
  });
  return [...granted].sort();
}

/** DNA Assistant's reply to the conversation so far. */
export async function getTurvaReplyLive(history: ChatTurn[], lang: Lang): Promise<TurvaReply> {
  const last = history[history.length - 1];
  if (last?.role === "user" && last.value === "consent_no")
    return { role: "turva", type: "message", text: i18n[lang].pipe.consentDeclined };

  const granted = grantedPaths(history);
  const d = await assess({ mode: "chat", body: userDescription(history), lang, granted });
  if (!d)
    return {
      role: "turva",
      type: "final",
      stage: "unchecked",
      headline: i18n[lang].pipe.banner.unchecked,
      steps: [],
      questions: [],
      consentFor: [],
      checked: false,
      decision: null,
    };
  return {
    role: "turva",
    type: "final",
    stage: stageOf(d.risk_level),
    headline: firstSentence(d.advice_text),
    steps: d.steps,
    questions: d.questions_asked,
    consentFor: d.consent_requested_for,
    checked: d.trace.consent_granted.some((p) => granted.includes(p)),
    decision: d,
  };
}

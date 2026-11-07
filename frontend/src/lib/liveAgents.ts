import { analyzeFn, chatFn } from "@/lib/live.functions";
import { hasDangerAsk } from "@/lib/dangerPhrases";
import { maxStage, pushLog, safetyFloor, withTimeout, type LiveStage } from "@/lib/live";
import {
  getTurvaReply,
  type ChatStory,
  type ChatTurn,
  type TurvaReply,
  type UserTurn,
} from "@/lib/chat";
import type { Lang } from "@/lib/i18n";
import type { Risk } from "@/components/RiskBadge";
import { CALLER_NUMBER } from "@/lib/callScript";

type Analysis = {
  stage?: LiveStage;
  flagged_phrases?: string[];
  reason?: Partial<Record<Lang, string>>;
  action?: string;
};

const STAGES: LiveStage[] = ["listening", "careful", "scam", "safe"];
const asStage = (s: unknown): LiveStage =>
  STAGES.includes(s as LiveStage) ? (s as LiveStage) : "careful";

type AnalyzeInput = {
  kind: "call" | "sms";
  text: string;
  transcript_so_far: string;
  caller_signals: Record<string, unknown>;
  lang: Lang;
};
async function analyze(input: AnalyzeInput, source: string): Promise<Analysis | null> {
  try {
    const r = await withTimeout(analyzeFn({ data: input }));
    const parsed = r.ok ? (JSON.parse(r.data) as Analysis) : null;
    pushLog(source, r.ok, r.ok ? parsed : r.error);
    return parsed;
  } catch (e) {
    pushLog(source, false, String(e));
    return null;
  }
}

/* Text messages are checked by the project pipeline instead (lib/messages.ts, /api/classify). */

/* ---------- call ---------- */
export async function analyzeCallSentence(sentence: string, soFar: string, lang: Lang) {
  const a = await analyze(
    {
      kind: "call",
      text: sentence,
      transcript_so_far: soFar,
      caller_signals: { number: CALLER_NUMBER, in_contacts: false, claims_identity: true },
      lang,
    },
    "analyze·call",
  );
  const floor = safetyFloor(sentence, "listening");
  if (!a)
    return {
      stage: floor,
      flags: [] as string[],
      reason: undefined as string | undefined,
      fellBack: true,
    };
  const flags = (a.flagged_phrases ?? []).filter(
    (f) => typeof f === "string" && sentence.toLowerCase().includes(f.toLowerCase()),
  );
  return {
    stage: maxStage(safetyFloor(sentence, asStage(a.stage)), floor),
    flags,
    reason: a.reason?.[lang],
    fellBack: false,
  };
}

/* ---------- chat ---------- */
/** Chat replies sometimes take a few seconds longer than a call sentence; the typing dots show meanwhile. */
const CHAT_TIMEOUT_MS = 20000;

type ChatJson =
  | { type: "message"; text: string }
  | { type: "question"; text: string; yes_no?: boolean }
  | { type: "consent_request"; text: string; fields?: string[] }
  | {
      type: "final";
      text?: string;
      answer?: { stage?: string; headline?: string; steps?: string[] };
    };

/**
 * The model's reply to the conversation so far. `fallback` is true when the model could not be
 * reached and the scripted demo reply was used instead (the screen says so).
 */
export async function getTurvaReplyLive(
  history: ChatTurn[],
  lang: Lang,
  story: ChatStory = "sim",
): Promise<{ reply: TurvaReply; fallback: boolean }> {
  const consent = history.some((h) => h.role === "user" && (h as UserTurn).value === "consent_yes");
  const msgs = history.map((h) => ({
    role: h.role === "user" ? ("user" as const) : ("assistant" as const),
    content: h.role === "user" ? h.text : JSON.stringify(h),
  }));
  try {
    const r = await withTimeout(
      chatFn({ data: { history: msgs, lang, consent } }),
      CHAT_TIMEOUT_MS,
    );
    if (!r.ok) throw new Error(r.error);
    const j = JSON.parse(r.data) as ChatJson;
    pushLog("chat", true, j);
    const ok = (reply: TurvaReply) => ({ reply, fallback: false });
    if (j.type === "message" && j.text) return ok({ role: "turva", type: "message", text: j.text });
    if (j.type === "question" && j.text)
      return ok({ role: "turva", type: "question", text: j.text, yesNo: j.yes_no !== false });
    if (j.type === "consent_request" && j.text)
      return ok({ role: "turva", type: "consent_request", text: j.text, fields: j.fields ?? [] });
    if (j.type === "final" && j.answer?.headline) {
      const s = j.answer.stage;
      let stage: Risk = s === "safe" ? "safe" : s === "scam" ? "scam" : "careful";
      // Safety floor, like for calls: never call it safe when what the user described asks for a
      // code, a payment or a fee (the pipeline's own patterns, lib/dangerPhrases).
      const said = history.map((h) => (h.role === "user" ? h.text : "")).join(" ");
      if (stage === "safe" && hasDangerAsk(said)) stage = "careful";
      return ok({
        role: "turva",
        type: "final",
        stage,
        headline: j.answer.headline,
        steps: (j.answer.steps ?? []).slice(0, 4),
        checked: consent,
      });
    }
    throw new Error("unexpected reply shape");
  } catch (e) {
    pushLog("chat", false, String(e));
    return { reply: getTurvaReply(history, lang, story), fallback: true };
  }
}

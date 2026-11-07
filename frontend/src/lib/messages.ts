import data from "@/generated/smsExamples.json";
import { hasDangerAsk } from "@/lib/dangerPhrases";
import { pushLog, withTimeout } from "@/lib/live";
import type { Lang } from "@/lib/i18n";

/** The project pipeline's verdict on one message (or the keyword fallback when it is unreachable). */
export type Verdict = {
  stage: "scam" | "safe";
  /** The pipeline's advice for the user, in the message language. */
  reasonText?: string | undefined;
  riskLevel?: string | undefined;
  situationId?: string | undefined;
  source: "pipeline" | "keywords";
};

export type Msg = {
  id: string;
  /** Literal sender, or an i18n msg key when `i18n` is set. */
  sender: string;
  text: string;
  time: string;
  /** Set for messages that arrived during the demo. */
  at?: number;
  /** Checked when it arrived (dataset example or typed message). */
  verdict?: Verdict;
  /** Where it came from: a dataset case id, or "typed". */
  origin?: string;
  i18n?: { sender: "doctor" | "library"; text: "doctorText" | "libraryText" };
};

/** Text messages from the dev dataset (tools/export_sms_examples.py). Only what a phone shows. */
export type SmsExample = { case_id: string; sender: string; body: string; lang: string };
export const SMS_EXAMPLES = data.examples as SmsExample[];

/** A random dataset message, in the user's language when there is one; never the same one twice in a row. */
export function pickExample(
  lang: Lang,
  lastId: string | null,
  rand: () => number = Math.random,
): SmsExample {
  const same = SMS_EXAMPLES.filter((e) => e.lang === lang);
  const pool = (same.length ? same : SMS_EXAMPLES).filter((e) => e.case_id !== lastId);
  return pool[Math.floor(rand() * pool.length)] ?? SMS_EXAMPLES[0]!;
}

export const OLD_MESSAGES: Msg[] = [
  {
    id: "doctor",
    sender: "",
    text: "",
    time: "yesterday",
    i18n: { sender: "doctor", text: "doctorText" },
  },
  {
    id: "library",
    sender: "",
    text: "",
    time: "monday",
    i18n: { sender: "library", text: "libraryText" },
  },
];

/** Pipeline risk levels that get a warning. none / low are shown as a normal message. */
const WARN = new Set(["medium", "high", "critical"]);

/** Fallback: the pipeline's own keyword patterns, run in the browser (lib/dangerPhrases). */
export function keywordVerdict(text: string): Verdict {
  return { stage: hasDangerAsk(text) ? "scam" : "safe", source: "keywords" };
}

/** Ask the project pipeline (dsa/, via /api/classify) whether a message is a scam. */
export async function classifySms(sender: string, body: string, lang: string): Promise<Verdict> {
  try {
    const r = await withTimeout(
      fetch("/api/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender, body, lang }),
      }),
    );
    if (!r.ok) throw new Error(`classify ${r.status}`);
    const d = (await r.json()) as { risk_level: string; advice_text: string; situation_id: string };
    pushLog("pipeline·sms", true, { risk: d.risk_level, situation: d.situation_id });
    return {
      stage: WARN.has(d.risk_level) ? "scam" : "safe",
      reasonText: d.advice_text,
      riskLevel: d.risk_level,
      situationId: d.situation_id,
      source: "pipeline",
    };
  } catch (e) {
    pushLog("pipeline·sms", false, String(e));
    return keywordVerdict(body);
  }
}

const URL_RE = /https?:\/\/\S+/i;

export function splitLink(text: string) {
  const m = text.match(URL_RE);
  if (!m || m.index === undefined) return { before: text, link: "", after: "" };
  return { before: text.slice(0, m.index), link: m[0], after: text.slice(m.index + m[0].length) };
}

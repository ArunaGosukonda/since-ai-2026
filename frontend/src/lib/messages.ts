import data from "@/generated/smsExamples.json";
import { assess, stageOf, type Decision, type Stage } from "@/lib/decision";
import type { Lang } from "@/lib/i18n";

/**
 * The project pipeline's verdict on one message. `decision` is the pipeline's whole answer
 * (risk, action, advice, steps, trace); `stage` is derived from its risk_level only.
 * source "unavailable": the pipeline could not be reached, stage "unchecked" (never "safe").
 * source "history": the user's own old messages, which arrived before the demo and were not checked.
 */
export type Verdict = {
  stage: Stage | "history";
  decision?: Decision | undefined;
  source: "pipeline" | "unavailable" | "history";
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

/** Ask the project pipeline (dsa/, via /api/classify) about a message. Fails closed. */
export async function classifySms(sender: string, body: string, lang: string): Promise<Verdict> {
  const d = await assess({ mode: "sms", sender, body, lang });
  if (!d) return { stage: "unchecked", source: "unavailable" };
  return { stage: stageOf(d.risk_level), decision: d, source: "pipeline" };
}

/** Warning stages: the inbox blurs the text and the link is struck through. */
export const isWarning = (s: Verdict["stage"]) => s === "careful" || s === "scam";

const URL_RE = /https?:\/\/\S+/i;

export function splitLink(text: string) {
  const m = text.match(URL_RE);
  if (!m || m.index === undefined) return { before: text, link: "", after: "" };
  return { before: text.slice(0, m.index), link: m[0], after: text.slice(m.index + m[0].length) };
}

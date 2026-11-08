import { useSyncExternalStore } from "react";
import { pushLog, withTimeout } from "@/lib/live";

/**
 * The project pipeline's decision (dsa.pipeline via POST /api/classify, tools/classify_message.py).
 * Field names are contracts/decision.schema.json's. The UI only renders this; it never decides.
 */
export type Decision = {
  risk_level: "none" | "low" | "medium" | "high" | "critical";
  urgency: string;
  primary_action: string;
  advice_text: string;
  situation_id: string;
  steps: string[];
  questions_asked: string[];
  question_topics: string[];
  consent_requested_for: string[];
  escalation_required: boolean;
  escalation_target: string | null;
  citations: string[];
  signals_used: string[];
  confidence: number;
  trace: {
    situation_id: string;
    facts_used: string[];
    rule_ids: string[];
    model: string | null;
    signals_used: string[];
    consent_requested: string[];
    consent_granted: string[];
  };
  /** contracts/facts.schema.json records for trace.facts_used. */
  facts: Record<string, { value: unknown; source: string; evidence: string; signal_path?: string }>;
};

/**
 * What the screen shows. From the pipeline's risk_level only:
 * none -> safe, low -> neutral ("check it yourself"), medium -> careful, high / critical -> scam.
 * "unchecked": the pipeline could not be reached. Never shown as safe.
 */
export type Stage = "safe" | "neutral" | "careful" | "scam" | "unchecked";

export function stageOf(risk: string | undefined): Stage {
  if (risk === "none") return "safe";
  if (risk === "low") return "neutral";
  if (risk === "medium") return "careful";
  if (risk === "high" || risk === "critical") return "scam";
  return "unchecked";
}

/** The pipeline spawns Python (about 0.5 s); the server gives up after 8 s. */
export const PIPELINE_TIMEOUT_MS = 9000;

export type AssessInput = {
  mode: "sms" | "chat" | "call";
  body: string;
  lang: string;
  sender?: string;
  sender_identity_verified?: boolean;
  /** Consent-gated signal paths the user agreed to share. */
  granted?: string[];
};

/**
 * Synthetic demo account the pipeline reads (tools/classify_message.py "profile").
 * "default": the clean user, no recent incidents. "esim": adds an eSIM change 35 minutes ago.
 * Only the presenter switches it (key P); the screen then shows a "Demo persona" label.
 */
export type DemoProfile = "default" | "esim";
let demoProfile: DemoProfile = "default";
const profileSubs = new Set<() => void>();
export function setDemoProfile(p: DemoProfile) {
  demoProfile = p;
  profileSubs.forEach((f) => f());
}
export function useDemoProfile(): DemoProfile {
  return useSyncExternalStore(
    (f) => {
      profileSubs.add(f);
      return () => profileSubs.delete(f);
    },
    () => demoProfile,
    () => "default",
  );
}

/** Ask the pipeline. null when it fails or times out (callers must then fail closed). */
export async function assess(input: AssessInput): Promise<Decision | null> {
  const source = `pipeline·${input.mode}`;
  try {
    const r = await withTimeout(
      fetch("/api/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...input, profile: demoProfile }),
      }),
      PIPELINE_TIMEOUT_MS,
    );
    if (!r.ok) throw new Error(`classify ${r.status}`);
    const d = (await r.json()) as Decision;
    if (!d || typeof d.risk_level !== "string" || typeof d.advice_text !== "string")
      throw new Error("unexpected reply shape");
    pushLog(source, true, {
      risk: d.risk_level,
      action: d.primary_action,
      situation: d.situation_id,
      consent: d.consent_requested_for,
      profile: demoProfile,
    });
    return d;
  } catch (e) {
    pushLog(source, false, String(e));
    return null;
  }
}

/** First sentence of the pipeline's advice (the chat headline). */
export function firstSentence(text: string): string {
  const m = text.match(/^.*?[.!?](?=\s|$)/s);
  return (m ? m[0] : text).trim();
}

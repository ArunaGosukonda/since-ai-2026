export type Stage = "listening" | "careful" | "scam";

export const CALLER_NUMBER = "+358 9 000 9811";
export const LINE_GAP_MS = 1500;
export const FALLBACK_MS_PER_WORD = 380;
/** Recording of the whole scripted call; its words must match i18n.en.call.lines. (call_4.mp3 is an alternative take.) */
export const CALL_AUDIO = "/audio/call_1.mp3";

/** Scripted risk stage after line index N completes. Underlines are not scripted: they come from lib/dangerPhrases. */
export const scriptedResults: Record<number, { stage: Stage }> = {
  0: { stage: "careful" },
  2: { stage: "scam" },
};

export const stageLevel = (s: Stage) => (s === "listening" ? 1 : s === "careful" ? 2 : 3);

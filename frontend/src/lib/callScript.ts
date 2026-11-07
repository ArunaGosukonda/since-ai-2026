export type Stage = "listening" | "careful" | "scam";

/** The demo caller's number. What they say is transcribed live (lib/useLiveCall); nothing is scripted. */
export const CALLER_NUMBER = "+358 9 000 9811";

export const stageLevel = (s: Stage) => (s === "listening" ? 1 : s === "careful" ? 2 : 3);

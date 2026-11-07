import data from "@/generated/dangerPatterns.json";

/**
 * Danger phrases = the pipeline's own scam-signal patterns (dsa/facts_keyword.py), exported by
 * tools/export_frontend_patterns.py. Nothing here is hand-written per scenario: what gets
 * underlined is whatever the pipeline would treat as a sender claim, a lure, a threat or a fee.
 */
export type DangerGroup = "sender" | "lure" | "threat" | "fee";
export type Span = { start: number; end: number; group: DangerGroup | "model"; kind: string };

type Pattern = { group: DangerGroup; kind: string; pattern: string; needs_link: boolean };
const PATTERNS = (data.patterns as Pattern[]).map((p) => ({
  ...p,
  re: new RegExp(p.pattern, "gi"),
}));
const LINK = new RegExp(data.link, "i");
const FOLD: Record<string, string> = {
  ...(data.fold as Record<string, string>),
  "’": "'",
  "‘": "'",
  " ": " ",
  "‐": "-",
  "‑": "-",
};

/**
 * Same folding as the pipeline (lower case, ä->a, ö->o, å->a, straight quotes), one character
 * for one character, so match positions map straight back onto the original text.
 */
export function fold(text: string): string {
  let out = "";
  for (const ch of text) {
    const lower = ch.toLowerCase();
    const mapped = FOLD[lower] ?? lower;
    // Keep 1:1 length (a few characters lower-case to two code units; leave those as-is).
    out += mapped.length === ch.length ? mapped : ch;
  }
  return out;
}

/** Sentence ranges, so a ".{0,40}" in a pattern never stretches an underline across sentences. */
function sentences(t: string): [number, number][] {
  const out: [number, number][] = [];
  const re = /[.!?]+(?=\s|$)|\n+/g;
  let from = 0;
  for (let m = re.exec(t); m; m = re.exec(t)) {
    out.push([from, m.index + m[0].length]);
    from = m.index + m[0].length;
  }
  if (from < t.length) out.push([from, t.length]);
  return out;
}

function rawSpans(t: string, hasLink: boolean): Span[] {
  const spans: Span[] = [];
  for (const [a, b] of sentences(t)) {
    const s = t.slice(a, b);
    for (const p of PATTERNS) {
      if (p.needs_link && !hasLink) continue; // pipeline rule: these lures only count with a link
      p.re.lastIndex = 0;
      for (let m = p.re.exec(s); m; m = p.re.exec(s)) {
        if (m[0].length === 0) {
          p.re.lastIndex++;
          continue;
        }
        spans.push({
          start: a + m.index,
          end: a + m.index + m[0].length,
          group: p.group,
          kind: p.kind,
        });
      }
    }
  }
  return spans;
}

const WORD = /[\p{L}\p{N}'-]/u;
/** Patterns often match a word stem ("pankk", "koodi"); underline the whole word. */
function toWordEdges(text: string, s: Span): Span {
  let { start, end } = s;
  while (start > 0 && WORD.test(text[start - 1]!) && WORD.test(text[start]!)) start--;
  while (end < text.length && WORD.test(text[end]!) && WORD.test(text[end - 1]!)) end++;
  return { ...s, start, end };
}

/** True when `text` asks for something, pressures, or charges a fee (not just a sender name). */
export function hasDangerAsk(text: string): boolean {
  const t = fold(text);
  return rawSpans(t, LINK.test(t)).some((s) => s.group !== "sender");
}

/**
 * Spans of `text` that match the pipeline's danger patterns, overlaps merged.
 * Lures, threats and fees are always underlined. A sender claim ("bank", "parcel") is only a
 * danger sign next to such an ask, so it is underlined only when `context` (the whole call or
 * message so far; defaults to `text`) contains one; a genuine parcel notice stays plain.
 */
export function dangerSpans(text: string, context: string = text): Span[] {
  const t = fold(text);
  const withAsk = context === text ? undefined : hasDangerAsk(context);
  const spans = rawSpans(t, LINK.test(fold(context)));
  const ask = withAsk ?? spans.some((s) => s.group !== "sender");
  return mergeSpans(
    spans.filter((s) => s.group !== "sender" || ask).map((s) => toWordEdges(text, s)),
  );
}

/** Spans for phrases a model flagged (case-insensitive substring match). */
export function phraseSpans(text: string, phrases: string[]): Span[] {
  const t = fold(text);
  const spans: Span[] = [];
  for (const ph of phrases) {
    const f = fold(ph.trim());
    if (!f) continue;
    for (let at = t.indexOf(f); at !== -1; at = t.indexOf(f, at + f.length)) {
      spans.push({ start: at, end: at + f.length, group: "model", kind: "model" });
    }
  }
  return spans;
}

export function mergeSpans(spans: Span[]): Span[] {
  const sorted = [...spans].sort((a, b) => a.start - b.start || b.end - a.end);
  const out: Span[] = [];
  for (const s of sorted) {
    const last = out[out.length - 1];
    if (last && s.start <= last.end) last.end = Math.max(last.end, s.end);
    else out.push({ ...s });
  }
  return out;
}

/** Split text into plain and underlined parts. */
export function splitSpans(text: string, spans: Span[]) {
  const parts: { text: string; flagged: boolean }[] = [];
  let i = 0;
  for (const s of mergeSpans(spans)) {
    if (s.start > i) parts.push({ text: text.slice(i, s.start), flagged: false });
    parts.push({ text: text.slice(s.start, s.end), flagged: true });
    i = s.end;
  }
  if (i < text.length) parts.push({ text: text.slice(i), flagged: false });
  return parts;
}

/** The matched phrases themselves (original casing), for the "What happened" summary. */
export function dangerPhrases(text: string, extra: string[] = []): string[] {
  const spans = mergeSpans([...dangerSpans(text), ...phraseSpans(text, extra)]);
  const seen = new Set<string>();
  return spans
    .map((s) => text.slice(s.start, s.end).trim())
    .filter((p) => p && !seen.has(p.toLowerCase()) && seen.add(p.toLowerCase()));
}

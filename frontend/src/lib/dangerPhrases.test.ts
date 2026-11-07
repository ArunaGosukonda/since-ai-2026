import { describe, expect, it } from "vitest";
import { i18n } from "@/lib/i18n";
import { dangerPhrases, dangerSpans, fold, splitSpans } from "@/lib/dangerPhrases";

const SCAM_TEXT =
  "PakettiPolku: Your parcel is held at customs. Pay the 1.49 EUR handling fee within 24 h: https://pakettipolku-tulli.test/maksu";
const GENUINE_TEXT =
  "Your parcel can be collected from the pickup point from tomorrow. The code is in the app.";

const flagged = (text: string, context?: string) =>
  splitSpans(text, dangerSpans(text, context))
    .filter((p) => p.flagged)
    .map((p) => p.text);

describe("danger phrases from the pipeline patterns", () => {
  it("folds 1:1 so positions map back onto the original text", () => {
    const s = "Läs upp KODERNA på Pankki’s";
    expect(fold(s)).toHaveLength(s.length);
    expect(fold(s)).toBe("las upp koderna pa pankki's");
  });

  it("underlines the code request in every language, as whole words", () => {
    expect(flagged(i18n.en.call.lines[2]!)).toContain("read the codes");
    expect(flagged(i18n.fi.call.lines[2]!)).toContain("lukea koodit");
    expect(flagged(i18n.sv.call.lines[2]!)).toContain("läsa upp koderna");
  });

  it("underlines a sender claim only when the call also asks for something", () => {
    const opening = i18n.en.call.lines[0]!;
    expect(flagged(opening)).toEqual([]);
    const call = i18n.en.call.lines.join(" ");
    expect(flagged(opening, call)).toEqual(["Bank's"]);
  });

  it("leaves a genuine message plain and flags the fee scam", () => {
    expect(flagged(GENUINE_TEXT)).toEqual([]);
    const scam = flagged(SCAM_TEXT);
    expect(scam).toContain("handling fee");
    expect(scam).toContain("24 h");
  });

  it("adds phrases a model flagged and de-duplicates the summary", () => {
    const text = "Please hurry. Read the codes to me. Read the codes to me.";
    expect(dangerPhrases(text, ["Please hurry"])).toEqual(["Please hurry", "Read the codes"]);
  });
});

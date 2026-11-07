import { describe, expect, it } from "vitest";
import { keywordVerdict, pickExample, SMS_EXAMPLES } from "./messages";

describe("text messages", () => {
  it("has dataset examples in every language, with only what a phone shows", () => {
    for (const lang of ["en", "fi", "sv"])
      expect(SMS_EXAMPLES.some((e) => e.lang === lang)).toBe(true);
    for (const e of SMS_EXAMPLES)
      expect(Object.keys(e).sort()).toEqual(["body", "case_id", "lang", "sender"]);
  });

  it("picks an example in the user's language and never the same one twice in a row", () => {
    const first = pickExample("sv", null, () => 0);
    expect(first.lang).toBe("sv");
    expect(pickExample("sv", first.case_id, () => 0).case_id).not.toBe(first.case_id);
  });

  it("falls back to the pipeline keyword patterns when the pipeline is unreachable", () => {
    expect(
      keywordVerdict("Pay the 1.49 EUR handling fee within 24 h: https://x.invalid").stage,
    ).toBe("scam");
    expect(keywordVerdict("Running 10 minutes late for dinner, see you soon!").stage).toBe("safe");
  });
});

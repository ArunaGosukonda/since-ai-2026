import { afterEach, describe, expect, it, vi } from "vitest";
import { classifySms, pickExample, SMS_EXAMPLES } from "./messages";
import { stageOf } from "./decision";

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

  it("maps the pipeline risk level to the screen, and nothing else", () => {
    expect(stageOf("none")).toBe("safe");
    expect(stageOf("low")).toBe("neutral");
    expect(stageOf("medium")).toBe("careful");
    expect(stageOf("high")).toBe("scam");
    expect(stageOf("critical")).toBe("scam");
    expect(stageOf(undefined)).toBe("unchecked");
  });
});

describe("pipeline unreachable: fail closed", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("never calls a message safe when /api/classify fails, even a harmless one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("pipeline unavailable", { status: 502 })),
    );
    const v = await classifySms("Anna", "Running 10 minutes late for dinner, see you soon!", "en");
    expect(v).toEqual({ stage: "unchecked", source: "unavailable" });
  });
  it("is unchecked when the request itself throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    expect((await classifySms("x", "Pay 1.49 EUR: https://x.invalid", "en")).stage).toBe(
      "unchecked",
    );
  });
});

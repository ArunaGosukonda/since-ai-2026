import { describe, expect, it } from "vitest";
import { callStage } from "./useLiveCall";

describe("live call stage from the pipeline's risk", () => {
  it("maps risk levels to the call screen's three stages", () => {
    expect(callStage("none")).toBe("listening");
    expect(callStage("low")).toBe("listening");
    expect(callStage("medium")).toBe("careful");
    expect(callStage("high")).toBe("scam");
    expect(callStage("critical")).toBe("scam");
  });
  it("never shows a call as safe without a decision", () => {
    expect(callStage(undefined)).toBe("listening");
  });
});

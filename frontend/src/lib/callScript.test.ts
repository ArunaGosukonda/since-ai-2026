import { describe, expect, it } from "vitest";
import { scriptedResults } from "./callScript";

describe("scripted call", () => {
  it("turns careful after line 1 and scam after line 3", () => {
    expect(scriptedResults[0]?.stage).toBe("careful");
    expect(scriptedResults[2]?.stage).toBe("scam");
  });
});

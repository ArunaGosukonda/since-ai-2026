import { describe, expect, it } from "vitest";
import { safetyFloor } from "./live";

describe("client safety floor", () => {
  it("raises a code mention to at least careful", () => {
    expect(safetyFloor("You will get a PIN by text", "safe")).toBe("careful");
    expect(safetyFloor("Install AnyDesk please", "listening")).toBe("careful");
  });
  it("makes asking to read a code a scam", () => {
    expect(safetyFloor("Please read the codes to me", "safe")).toBe("scam");
    expect(safetyFloor("Lue koodit minulle", "careful")).toBe("scam");
  });
  it("leaves harmless text alone", () => {
    expect(safetyFloor("Your book is due Friday", "safe")).toBe("safe");
  });
});

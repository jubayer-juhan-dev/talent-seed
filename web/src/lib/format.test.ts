import { describe, expect, it } from "vitest";
import { day, fmt, label } from "./format";

describe("format", () => {
  it("formats counts with thousands separators and dashes for missing values", () => {
    expect(fmt(3447543)).toBe("3,447,543");
    expect(fmt(0)).toBe("0");
    expect(fmt(null)).toBe("–");
  });
  it("cuts ISO timestamps to the date", () => {
    expect(day("2026-09-24T00:00:00+00:00")).toBe("2026-09-24");
    expect(day(undefined)).toBe("–");
  });
  it("labels segments and passes unknown values through", () => {
    expect(label("FULL_TIME")).toBe("Full-time");
    expect(label("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });
});

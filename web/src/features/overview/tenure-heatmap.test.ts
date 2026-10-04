import { describe, expect, it } from "vitest";
import { cohortOf } from "./tenure-heatmap";

// Mirrors [priority_cohort] in config/talent_seed_thresholds.toml (first matching rule wins).
describe("cohortOf", () => {
  it.each([
    ["ESTABLISHED", "FULL_TIME", "P1"],
    ["EMERGING", "FULL_TIME", "P1"],
    ["NEWCOMER", "FULL_TIME", "P2"],
    ["ESTABLISHED", "PART_TIME", "P2"],
    ["EMERGING", "PART_TIME", "P2"],
    ["NEWCOMER", "PART_TIME", "P3"],
    ["ESTABLISHED", "ONE_TIME", "P3"],
    ["NEWCOMER", "ONE_TIME", "P3"],
  ])("%s + %s → %s", (tenure, activity, cohort) => {
    expect(cohortOf(tenure, activity)).toBe(cohort);
  });
});

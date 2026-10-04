import { describe, expect, it } from "vitest";
import { apiQuery, joinList, listOf, validateExploreSearch } from "./search";

describe("explore search params", () => {
  it("reads first-viewer links unchanged", () => {
    const s = validateExploreSearch({
      cohort: "P1,P2,P3",
      eco: "Uniswap|Anza",
      country: "Germany,France",
      sort: "name",
    });
    expect(listOf(s, "eco")).toEqual(["Uniswap", "Anza"]);
    expect(listOf(s, "country")).toEqual(["Germany", "France"]);
    expect(apiQuery(s)).toMatchObject({
      cohort: "P1,P2,P3",
      eco: "Uniswap|Anza",
      sort: "name",
      dir: "asc",
      hide_flagged: "1",
    });
  });
  it("treats an empty cohort as all cohorts and drops defaults", () => {
    expect(validateExploreSearch({ cohort: "" }).cohort).toBe("all");
    expect(apiQuery(validateExploreSearch({ cohort: "" })).cohort).toBeUndefined();
    expect(validateExploreSearch({ cohort: "P1", sort: "active_days" })).toMatchObject({
      cohort: undefined,
      sort: undefined,
    });
  });
  it("ignores unknown sorts and coerces numbers", () => {
    expect(validateExploreSearch({ sort: "bogus", q: 123 })).toMatchObject({ sort: undefined, q: "123" });
  });
  it("shows flagged people only when asked", () => {
    expect(apiQuery(validateExploreSearch({ flagged: "show" })).hide_flagged).toBeUndefined();
    expect(joinList("eco", [])).toBeUndefined();
  });
  it("passes the AI-enriched filter through", () => {
    const s = validateExploreSearch({ ai_enriched: "yes" });
    expect(listOf(s, "ai_enriched")).toEqual(["yes"]);
    expect(apiQuery(s).ai_enriched).toBe("1");
    expect(apiQuery(validateExploreSearch({ ai_enriched: "no" })).ai_enriched).toBe("0");
    expect(apiQuery(validateExploreSearch({ ai_enriched: "yes,no" })).ai_enriched).toBeUndefined();
    expect(apiQuery(validateExploreSearch({})).ai_enriched).toBeUndefined();
  });
});

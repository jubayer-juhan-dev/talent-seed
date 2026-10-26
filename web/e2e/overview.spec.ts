import { expect, resultCount, test, withKey } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.goto(withKey("/"));
});

test("shows cohort cards, chain bars, heatmap and countries", async ({ page }) => {
  await expect(page.locator("[data-tour=cohort-cards] a")).toHaveCount(4);
  await expect(page.locator("[data-tour=chains] li")).toHaveCount(12);
  await page.getByRole("button", { name: "Show all 20 chains" }).click();
  await expect(page.locator("[data-tour=chains] li")).toHaveCount(20);
  await expect(page.locator("[data-tour=heatmap] td a")).toHaveCount(9);
  await expect(page.getByText("How to read this data")).toBeVisible();
});

test("a chain bar opens Explore with the same count", async ({ page }) => {
  const bar = page.locator("[data-tour=chains] li a").first();
  const shown = Number((await bar.locator("span").last().innerText()).replaceAll(",", ""));
  await bar.click();
  await expect(page).toHaveURL(/\/explore\?.*eco=/);
  expect(await resultCount(page)).toBe(shown);
});

test("a heatmap cell opens Explore with the same count", async ({ page }) => {
  const cell = page.getByRole("link", { name: /^Newcomer, Part-time/ });
  const shown = Number((await cell.getAttribute("aria-label"))?.match(/: ([\d,]+) people/)?.[1].replaceAll(",", ""));
  await cell.click();
  await expect(page).toHaveURL(/tenure=NEWCOMER/);
  expect(await resultCount(page)).toBe(shown);
});

test("a cohort card opens that cohort", async ({ page }) => {
  const card = page.locator("[data-tour=cohort-cards] a").nth(2);
  const shown = Number((await card.locator(".sr-only").innerText()).split(" ")[0].replaceAll(",", ""));
  await card.click();
  await expect(page).toHaveURL(/cohort=P3/);
  expect(await resultCount(page)).toBe(shown);
});

import { expect, resultCount, test, withKey } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.goto(withKey("/explore"));
  await expect(page.locator("[aria-label^='Open ']").first()).toBeVisible();
});

test("starts on P1, 50 cards, and loads more", async ({ page }) => {
  await expect(page.locator("[aria-label^='Open ']")).toHaveCount(50);
  await page.getByLabel("Table view").click();
  await page.getByRole("button", { name: /^Load \d+ more/ }).click();
  await expect(page.locator("tbody tr")).toHaveCount(100);
});

test("cohort switcher changes results and URL", async ({ page }) => {
  const p1 = await resultCount(page);
  await page.getByRole("button", { name: /^P2 / }).click();
  await expect(page).toHaveURL(/cohort=P2/);
  await expect.poll(() => resultCount(page)).not.toBe(p1);
});

test("filter by project via the menu, as a chip, kept on reload", async ({ page }) => {
  await page.getByRole("button", { name: "Filters" }).click();
  await page.getByText("Chain or project", { exact: true }).click();
  await page.keyboard.type("uniswap");
  await page.locator("[cmdk-item]", { hasText: "Uniswap" }).first().click();
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/eco=Uniswap/);
  const n = await resultCount(page);
  await expect(page.getByLabel("Remove Chain or project Uniswap")).toBeVisible();
  await page.reload();
  expect(await resultCount(page)).toBe(n);
});

test("search shows a chip and clearing it restores results", async ({ page }) => {
  const all = await resultCount(page);
  await page.locator("#explore-search").fill("zzzz-no-such-dev");
  await expect(page.getByText("No one matches these filters")).toBeVisible();
  await page.getByLabel(/^Remove Search/).click();
  expect(await resultCount(page)).toBe(all);
});

test("'/' focuses search from the overview", async ({ page }) => {
  await page.goto(withKey("/"));
  await page.locator("[data-tour=cohort-cards] a").first().waitFor();
  await page.keyboard.press("/");
  await expect(page).toHaveURL(/\/explore/);
  await expect(page.locator("#explore-search")).toBeFocused();
});

test("sort menu and table headers drive the URL", async ({ page }) => {
  await page.getByRole("button", { name: "Most active" }).click();
  await page.getByRole("menuitem", { name: /Name A–Z/ }).click();
  await expect(page).toHaveURL(/sort=name/);
  await page.getByLabel("Table view").click();
  await page.getByRole("button", { name: /^Active days/ }).click();
  await expect(page).not.toHaveURL(/sort=/);
});

test("hiding bots changes the HOLD count", async ({ page }) => {
  await page.getByRole("button", { name: /^HOLD/ }).click();
  const hidden = await resultCount(page);
  await page.locator("#hide-flagged").click();
  await expect(page).toHaveURL(/flagged=show/);
  await expect.poll(() => resultCount(page)).toBeGreaterThan(hidden);
});

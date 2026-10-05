import { expect, noHorizontalScroll, test, withKey } from "./helpers";

test("overview, explore and the profile sheet fit a phone screen", async ({ page }) => {
  await page.goto(withKey("/"));
  await expect(page.locator("[data-tour=cohort-cards] a")).toHaveCount(4);
  expect(await noHorizontalScroll(page)).toBe(true);

  await page.goto(withKey("/explore"));
  await expect(page.locator("[aria-label^='Open ']").first()).toBeVisible();
  expect(await noHorizontalScroll(page)).toBe(true);

  await page.locator("[aria-label^='Open ']").first().click();
  await expect(page.locator("[data-slot=sheet-content]")).toBeVisible();
  const tabs = await page.getByRole("tablist").boundingBox();
  expect(tabs?.height).toBeGreaterThan(28);
  expect(await noHorizontalScroll(page)).toBe(true);
});

test("dark mode is applied from the system setting", async ({ page }) => {
  await page.goto(withKey("/"));
  await expect(page.locator("html")).toHaveClass(/dark/);
});

import { expect, resultCount, test, withKey } from "./helpers";

test("first-viewer explore links redirect with their filters", async ({ page }) => {
  await page.goto(withKey("/?view=explore&eco=Uniswap&sort=name"));
  await expect(page).toHaveURL(/\/explore\?.*eco=Uniswap.*sort=name/);
  expect(await resultCount(page)).toBeGreaterThan(0);
});

test("first-viewer #p= profile links open the profile", async ({ page }) => {
  await page.goto(`${withKey("/")}#p=gh:1076145`);
  await expect(page).toHaveURL(/p=gh%3A1076145/);
  await expect(page.getByRole("dialog")).toBeVisible();
});

test("/next preview links redirect to the same page", async ({ page }) => {
  await page.goto(withKey("/next/explore?cohort=P3"));
  await expect(page).toHaveURL(/\/explore\?.*cohort=P3/);
});

test("the legacy viewer still loads", async ({ page }) => {
  await page.goto(withKey("/legacy"));
  await expect(page.locator(".cohort-card")).toHaveCount(4);
});

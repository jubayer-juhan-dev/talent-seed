import { test as base, expect } from "@playwright/test";
import { withKey } from "./helpers";

// Plain test (not the helper's): this one needs a first visit, with the tour not yet seen.
base("tour runs on first visit across both screens, then stays closed", async ({ page }) => {
  await page.goto(withKey("/"));
  const next = page.getByRole("button", { name: /^(Next|Done)$/ });
  const titles: string[] = [];
  for (let i = 0; i < 12; i++) {
    await expect(next).toBeVisible({ timeout: 10_000 });
    titles.push(await page.locator("[aria-modal=true] h3").innerText());
    await next.click();
  }
  expect(titles[0]).toBe("Welcome to Talent Seed");
  expect(titles[11]).toBe("Export for outreach");
  await expect(page).toHaveURL(/\/explore/);
  await expect(next).toHaveCount(0);
  await page.reload();
  await page.waitForTimeout(2000);
  await expect(next).toHaveCount(0);
  await page.getByRole("button", { name: "Take the tour" }).click();
  await expect(next).toBeVisible();
  await page.getByRole("button", { name: "Close the tour" }).click();
  await expect(next).toHaveCount(0);
});

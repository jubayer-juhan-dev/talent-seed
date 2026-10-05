import { test as base, expect, type Page } from "@playwright/test";

export const KEY = process.env.TALENT_SEED_KEY ?? "";
if (!KEY) throw new Error("Set TALENT_SEED_KEY (see playwright.config.ts).");

/** Path with the access key added. */
export const withKey = (path: string) => `${path}${path.includes("?") ? "&" : "?"}key=${encodeURIComponent(KEY)}`;

/** Pages start with the tour already seen, so it doesn't cover what a test clicks. */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript(() => localStorage.setItem("ts.tourSeen", '"1"'));
    await use(page);
  },
});
export { expect };

/** The "N people match" count on Explore, as a number. */
export async function resultCount(page: Page) {
  const status = page.locator("[data-testid=result-summary]");
  await expect(status).toContainText(/match/);
  return Number((await status.innerText()).split(" ")[0].replaceAll(",", ""));
}

export const noHorizontalScroll = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

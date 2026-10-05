import { expect, test, withKey } from "./helpers";

const name = (page: import("@playwright/test").Page) => page.locator("[role=dialog] h2:not(.sr-only)");

test("opens from a card, steps with arrows, closes with Esc and Back", async ({ page }) => {
  await page.goto(withKey("/explore"));
  const cards = page.locator("[aria-label^='Open ']");
  const second = (await cards.nth(1).getAttribute("aria-label"))?.replace("Open ", "") ?? "";
  await cards.first().click();
  await expect(page).toHaveURL(/p=/);
  await expect(page.getByText(/^Why P/)).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(name(page)).toContainText(second);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page).not.toHaveURL(/p=/);

  await cards.first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("tabs show contact, repos and details", async ({ page }) => {
  await page.goto(withKey("/explore?p=gh:19890894"));
  await page.getByRole("tab", { name: /Contact/ }).click();
  await expect(page.getByText("Unverified emails")).toBeVisible();
  await page.getByRole("tab", { name: /Repos/ }).click();
  await expect(page.locator("[role=dialog] tbody tr").first()).toBeVisible();
  await page.getByRole("tab", { name: /Data details/ }).click();
  await expect(page.locator("[role=dialog] dt", { hasText: "AI enriched" })).toBeVisible();
});

test("an unknown person shows an error, not a blank dialog", async ({ page }) => {
  await page.goto(withKey("/explore?p=gh:0"));
  await expect(page.getByText("Couldn't load this person")).toBeVisible();
});

import { expect, KEY, test, withKey } from "./helpers";

test("without the key, pages and API are locked", async ({ page, request }) => {
  await page.goto("/explore");
  await expect(page.getByText("This page needs its access link")).toBeVisible();
  expect((await request.get("/api/meta")).status()).toBe(401);
});

test("the key works as a header, and built assets are public", async ({ request }) => {
  expect((await request.get("/api/meta", { headers: { "X-Access-Key": KEY } })).status()).toBe(200);
  expect((await request.get("/favicon.svg")).status()).toBe(200);
  const unknown = await request.get(withKey("/api/nope"));
  expect(unknown.status()).toBe(404);
  expect(await unknown.json()).toEqual({ error: "not found" });
});

test("works when the browser drops cookies, including after a reload", async ({ page, context }) => {
  await page.route("**/*", async (route) => {
    await context.clearCookies();
    await route.continue();
  });
  await page.goto(withKey("/explore"));
  await expect(page.locator("[data-testid=result-summary]")).toContainText(/match/);
  await page.reload();
  await expect(page.locator("[data-testid=result-summary]")).toContainText(/match/);
  expect(page.url()).toContain("key=");
});

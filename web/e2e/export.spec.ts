import { readFile } from "node:fs/promises";
import { expect, resultCount, test, withKey } from "./helpers";

const csvRows = async (path: string) => (await readFile(path, "utf8")).replace(/^﻿/, "").trim().split("\n");

test("exports the current filter and the shortlist with caveat columns", async ({ page }) => {
  await page.goto(withKey("/explore?eco=Uniswap"));
  const n = await resultCount(page);
  await page.getByLabel("Add to shortlist").first().click();
  await expect(page.getByRole("button", { name: "Shortlist, 1 person" })).toBeVisible();

  await page.locator("[data-tour=export]").click();
  const filterDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download CSV" }).click();
  const filtered = await filterDownload;
  expect(filtered.suggestedFilename()).toBe("talent_seed_export.csv");
  const rows = await csvRows(await filtered.path());
  for (const col of ["email_status", "cohort_status", "attribution", "ai_enriched"]) expect(rows[0]).toContain(col);
  expect(rows.length - 1).toBe(Math.min(n, 5000));

  await page.getByRole("button", { name: /^Shortlist/ }).click();
  await page.getByRole("button", { name: "Export CSV" }).click();
  await expect(page.locator("#export-shortlist")).toHaveAttribute("data-state", "checked");
  const listDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download CSV" }).click();
  const list = await listDownload;
  expect(list.suggestedFilename()).toBe("talent_seed_shortlist.csv");
  expect((await csvRows(await list.path())).length - 1).toBe(1);
});

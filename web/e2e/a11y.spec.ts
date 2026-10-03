import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// a real scan of docs/demo/canned-goods.jpg, recorded from the API
const fixture = (name: string) => fileURLToPath(new URL(`fixtures/${name}`, import.meta.url));
const scan = JSON.parse(readFileSync(fixture("scan.json"), "utf8"));
const photo = fileURLToPath(new URL("../../docs/demo/canned-goods.jpg", import.meta.url));

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function mockApi(page: Page) {
  await page.route("http://api.test/images", (route) =>
    route.fulfill({ status: 201, json: { id: scan.image_id } }),
  );
  await page.route("http://api.test/detect", (route) => route.fulfill({ status: 201, json: scan }));
  await page.route(`http://api.test/results/${scan.id}/overlay`, (route) =>
    route.fulfill({ path: fixture("overlay.jpg"), contentType: "image/jpeg" }),
  );
}

async function expectAccessible(page: Page) {
  // runs every WCAG 2.2 AA rule, including color contrast in a real browser
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(", ")}`)).toEqual([]);
}

test("upload page meets WCAG 2.2 AA", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Lacuna" })).toBeVisible();
  await expectAccessible(page);
});

test("keyboard user can scan a shelf and land on the results", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeInViewport();

  await page.getByLabel("Shelf photo").setInputFiles(photo);
  await page.getByLabel("Shelf code (optional)").fill("aisle4-bay2");
  await page.getByLabel("Shelf code (optional)").press("Tab");
  await expect(page.getByRole("button", { name: "Scan shelf" })).toBeFocused();
  await page.keyboard.press("Enter");

  const results = page.getByRole("heading", { name: "Results" });
  await expect(results).toBeFocused();
  await expect(page.getByText("89%")).toBeVisible();
  await expect(page.getByRole("table", { name: /Gaps by shelf row/ }).getByRole("row")).toHaveCount(3);
  await expect(page.getByRole("img", { name: /40 products/ })).toBeVisible();
  await expectAccessible(page);

  if (process.env.SCREENSHOT) {
    await page.setViewportSize({ width: 1100, height: 1500 });
    await page.screenshot({ path: process.env.SCREENSHOT, fullPage: true });
  }
});

test("API errors are announced", async ({ page }) => {
  await page.route("http://api.test/images", (route) =>
    route.fulfill({ status: 413, json: { detail: "file is over the 10 MB limit" } }),
  );
  await page.goto("/");
  await page.getByLabel("Shelf photo").setInputFiles(photo);
  await page.getByRole("button", { name: "Scan shelf" }).click();
  await expect(page.getByRole("alert")).toHaveText("file is over the 10 MB limit");
});

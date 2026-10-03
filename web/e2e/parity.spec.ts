import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The browser pipeline (TypeScript pre/post-processing, ONNX Runtime Web) has to
// find the same gaps as the Python one, on the same shelves, within the same 25 px.
const docs = (path: string) => fileURLToPath(new URL(`../../docs/${path}`, import.meta.url));
const expected: Record<string, { gaps: Array<[number, number, number]> }> = JSON.parse(
  readFileSync(docs("expected_gaps.json"), "utf8"),
);
const TOLERANCE = 25;

for (const [name, { gaps }] of Object.entries(expected)) {
  test(`browser finds the same gaps as Python: ${name}`, async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Shelf photo").setInputFiles(docs(`${name}.jpg`));
    await page.getByRole("button", { name: "Scan shelf" }).click();
    await expect(page.getByRole("heading", { name: "Results" })).toBeFocused({ timeout: 60_000 });

    // the gaps table: row (1-based), from x, to x, width
    const rows = await page
      .getByRole("table", { name: /Gaps by shelf row/ })
      .locator("tbody tr")
      .evaluateAll((trs) => trs.map((tr) => [...tr.querySelectorAll("td")].map((td) => Number(td.textContent))));
    const found = rows.map(([row, x1, x2]) => [row - 1, x1, x2]);

    expect(found.length, JSON.stringify(found)).toBe(gaps.length);
    gaps.forEach(([row, x1, x2], i) => {
      expect(found[i][0]).toBe(row);
      expect(Math.abs(found[i][1] - x1), `gap ${i} start`).toBeLessThanOrEqual(TOLERANCE);
      expect(Math.abs(found[i][2] - x2), `gap ${i} end`).toBeLessThanOrEqual(TOLERANCE);
    });
  });
}

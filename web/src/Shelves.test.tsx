import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { HistoryPoint, Missing, ShelfSummary } from "./api";
import { axisLabel, change } from "./format";
import { plot } from "./OccupancyChart";
import { parseRoute } from "./route";

const shelves: ShelfSummary[] = [
  {
    shelf: "aisle4-bay2",
    scan_count: 3,
    avg_occupancy: 0.7,
    latest_occupancy: 0.48,
    latest_gap_count: 6,
    last_scanned_at: "2026-10-04T15:00:00Z",
  },
  {
    shelf: "cooler 1",
    scan_count: 1,
    avg_occupancy: 0.95,
    latest_occupancy: 0.95,
    latest_gap_count: 0,
    last_scanned_at: "2026-10-03T15:00:00Z",
  },
];

const point = (id: string, day: number, occupancy: number | null, change: number | null): HistoryPoint => ({
  scan_id: id,
  created_at: `2026-10-0${day}T12:00:00Z`,
  occupancy,
  gap_count: occupancy === null ? 0 : Math.round((1 - occupancy) * 10),
  occupancy_change: change,
});

// newest first, as the API sends them
const history = {
  shelf: "aisle4-bay2",
  baseline_scan_id: null as string | null,
  scans: [point("s3", 4, 0.48, -0.42), point("s2", 3, 0.9, 0.18), point("s1", 2, 0.72, null)],
};

async function expectNoA11yViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

function mockApi(...responses: Array<{ status: number; body: unknown }>) {
  const fetchMock = vi.fn();
  for (const { status, body } of responses) {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(body), { status }));
  }
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function goTo(hash: string) {
  act(() => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.location.hash = "";
});

describe("routes", () => {
  it("parses pages and shelf codes", () => {
    expect(parseRoute("")).toEqual({ page: "scan" });
    expect(parseRoute("#/")).toEqual({ page: "scan" });
    expect(parseRoute("#/shelves")).toEqual({ page: "shelves" });
    expect(parseRoute("#/shelves/")).toEqual({ page: "shelves" });
    expect(parseRoute("#/shelves/cooler%201")).toEqual({ page: "shelf", shelf: "cooler 1" });
    expect(parseRoute("#/shelves/%E0%A4%A")).toEqual({ page: "scan" }); // bad escape
    expect(parseRoute("#/nope")).toEqual({ page: "scan" });
  });

  it("keeps the page when the skip link changes the hash", async () => {
    mockApi({ status: 200, body: shelves });
    window.location.hash = "#/shelves";
    render(<App />);
    await screen.findByRole("table");
    goTo("#main");
    expect(screen.getByRole("heading", { name: "Shelf history" })).toBeInTheDocument();
  });
});

describe("chart", () => {
  it("plots oldest first, skips unknown occupancy, and puts 100% at the top", () => {
    const points = plot([point("b", 3, 0, null), point("x", 3, null, null), point("a", 2, 1, null)]);
    expect(points.map((p) => p.point.scan_id)).toEqual(["a", "b"]);
    expect(points[0].x).toBeLessThan(points[1].x);
    expect(points[0].y).toBeLessThan(points[1].y);
  });

  it("centers a single scan", () => {
    const [only] = plot([point("a", 2, 0.5, null)]);
    expect(only.x).toBeCloseTo(48 + (640 - 48 - 20) / 2);
  });

  it("labels the axis with times when every scan is on one day", () => {
    const sameDay = axisLabel("2026-10-05T12:00:00Z", "2026-10-05T12:30:00Z");
    const days = axisLabel("2026-10-02T12:00:00Z", "2026-10-05T12:00:00Z");
    expect(sameDay("2026-10-05T12:30:00Z")).toMatch(/\d:30/);
    expect(days("2026-10-05T12:00:00Z")).toMatch(/Oct/);
    const sameMinute = axisLabel("2026-10-05T12:00:05Z", "2026-10-05T12:00:50Z");
    expect(sameMinute("2026-10-05T12:00:50Z")).toMatch(/:00:50/);
  });

  it("formats changes in points", () => {
    expect(change(null)).toBe("First scan");
    expect(change(0.001)).toBe("No change");
    expect(change(0.18)).toBe("+18 pts");
    expect(change(-0.42)).toBe("\u221242 pts");
  });
});

describe("shelves page", () => {
  it("lists shelves emptiest first, linked to their history", async () => {
    const fetchMock = mockApi({ status: 200, body: shelves });
    window.location.hash = "#/shelves";
    const { container } = render(<App />);

    const table = await screen.findByRole("table", { name: /emptiest first/ });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByRole("link", { name: "aisle4-bay2" })).toHaveAttribute(
      "href",
      "#/shelves/aisle4-bay2",
    );
    expect(within(rows[2]).getByRole("link", { name: "cooler 1" })).toHaveAttribute("href", "#/shelves/cooler%201");
    expect(within(rows[1]).getByText("48%")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/reports\/worst-shelves\?limit=50$/);
    expect(screen.getByRole("link", { name: "Shelf history" })).toHaveAttribute("aria-current", "page");
    await expectNoA11yViolations(container);
  });

  it("explains how to get a shelf onto the list", async () => {
    mockApi({ status: 200, body: [] });
    window.location.hash = "#/shelves";
    render(<App />);
    const empty = await screen.findByText(/No shelves yet/);
    expect(within(empty).getByRole("link", { name: "Scan a shelf" })).toHaveAttribute("href", "#/");
  });

  it("announces a server that can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    window.location.hash = "#/shelves";
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/Can't reach the Lacuna API/);
  });
});

describe("shelf page", () => {
  it("shows the trend, the chart, and every scan", async () => {
    const fetchMock = mockApi({ status: 200, body: history });
    window.location.hash = "#/shelves/aisle4-bay2";
    const { container } = render(<App />);

    const table = await screen.findByRole("table", { name: "Every scan, newest first" });
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(within(table).getByText("First scan")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/shelves\/aisle4-bay2\/history\?limit=200$/);

    const sinceLast = screen.getByText("Since last scan").parentElement as HTMLElement;
    expect(within(sinceLast).getByText("\u221242 pts")).toBeInTheDocument();
    const chart = screen.getByRole("img", { name: "Occupancy over time for aisle4-bay2" });
    expect(chart).toHaveAccessibleDescription(/3 scans .* Latest 48%, lowest 48%, highest 90%\./);
    expect(within(table).getAllByRole("link", { name: /View photo from/ })[0]).toHaveAttribute(
      "href",
      expect.stringMatching(/\/results\/s3\/overlay$/),
    );
    expect(screen.getByRole("link", { name: "Shelf history" })).toHaveAttribute("aria-current", "true");
    await expectNoA11yViolations(container);
  });

  it("says so when a shelf has no saved scans", async () => {
    mockApi({ status: 404, body: { detail: "Shelf not found" } });
    window.location.hash = "#/shelves/nope";
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No scans saved for shelf nope yet.");
  });

  it("moves focus to the shelf heading when you open one", async () => {
    mockApi({ status: 200, body: shelves }, { status: 200, body: history });
    window.location.hash = "#/shelves";
    render(<App />);
    await screen.findByRole("table");
    goTo("#/shelves/aisle4-bay2");
    expect(screen.getByRole("heading", { name: "Shelf aisle4-bay2" })).toHaveFocus();
    await screen.findByRole("table", { name: "Every scan, newest first" });
  });
});

const product = (id: number, x1: number) => ({ id, x1, y1: 20, x2: x1 + 50, y2: 140, score: 0.9 });
const missing: Missing = {
  scan_id: "s3",
  baseline_scan_id: "s1",
  aligned: true,
  gaps: [
    { gap: { row: 0, x1: 240, y1: 20, x2: 370, y2: 140, width_ratio: 2.2 }, products: [product(7, 250), product(8, 310)] },
    { gap: { row: 1, x1: 10, y1: 200, x2: 90, y2: 320, width_ratio: 1.1 }, products: [] },
  ],
};

describe("baseline compare", () => {
  it("shows what sold out of each gap since the baseline", async () => {
    const fetchMock = mockApi({ status: 200, body: { ...history, baseline_scan_id: "s1" } }, { status: 200, body: missing });
    window.location.hash = "#/shelves/aisle4-bay2";
    const { container } = render(<App />);

    const section = await screen.findByRole("region", { name: /What sold out since the baseline/ });
    expect(await within(section).findByText(/Gap 1, shelf row 1: 2 products sold out/)).toBeInTheDocument();
    expect(within(section).getByText(/Gap 2, shelf row 2: nothing in the baseline sat here/)).toBeInTheDocument();
    const crops = within(section).getAllByRole("img");
    expect(crops).toHaveLength(2);
    expect(crops[0]).toHaveAttribute("src", expect.stringMatching(/\/results\/s1\/products\/7\/crop$/));
    expect(crops[0]).toHaveAccessibleName("Product 1 of 2 that was in gap 1 in the baseline photo");
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/results\/s3\/missing$/);

    const pressed = screen.getAllByRole("button", { name: /Baseline scan from/, pressed: true });
    expect(pressed).toHaveLength(1);
    await expectNoA11yViolations(container);
  });

  it("sets a baseline in place, keeps focus, and announces it", async () => {
    const fetchMock = mockApi(
      { status: 200, body: history },
      { status: 200, body: { scan_id: "s1" } },
      { status: 200, body: missing },
    );
    const user = userEvent.setup();
    window.location.hash = "#/shelves/aisle4-bay2";
    render(<App />);

    await screen.findByText(/Press Baseline on a scan taken when the shelf was full/);
    const buttons = screen.getAllByRole("button", { name: /Baseline scan from/ });
    expect(buttons.every((b) => b.getAttribute("aria-pressed") === "false")).toBe(true);
    await user.click(buttons[2]); // oldest scan

    expect(await screen.findByText(/is now the baseline\./)).toBeInTheDocument();
    expect(buttons[2]).toHaveAttribute("aria-pressed", "true");
    expect(buttons[2]).toHaveFocus();
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toMatch(/\/shelves\/aisle4-bay2\/baseline$/);
    expect(JSON.parse(init.body)).toEqual({ scan_id: "s1" });
    expect(await screen.findByRole("region", { name: /What sold out/ })).toBeInTheDocument();
  });

  it("says when the photos can't be lined up", async () => {
    mockApi(
      { status: 200, body: { ...history, baseline_scan_id: "s1" } },
      { status: 200, body: { ...missing, aligned: false, gaps: [] } },
    );
    window.location.hash = "#/shelves/aisle4-bay2";
    render(<App />);
    expect(await screen.findByText(/don't line up well enough to compare/)).toBeInTheDocument();
  });

  it("announces a failed baseline change", async () => {
    mockApi({ status: 200, body: history }, { status: 422, body: { detail: "scan s1 is not a scan of shelf aisle4-bay2" } });
    const user = userEvent.setup();
    window.location.hash = "#/shelves/aisle4-bay2";
    render(<App />);
    const buttons = await screen.findAllByRole("button", { name: /Baseline scan from/ });
    await user.click(buttons[0]);
    expect(await screen.findByRole("alert")).toHaveTextContent("not a scan of shelf");
    expect(buttons[0]).toHaveAttribute("aria-pressed", "false");
  });
});

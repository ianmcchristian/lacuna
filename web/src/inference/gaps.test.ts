// Same cases as tests/test_gaps.py, so the port can't drift from the Python.
import { describe, expect, it } from "vitest";
import { Box, analyzeShelf, coveredFraction } from "./gaps";

// 10 slots, 60 px apart, as in tests/conftest.py
const FULL_ROW = Array.from({ length: 10 }, (_, i) => 10 + i * 60);
const GAPPY_ROW = FULL_ROW.filter((_, i) => i !== 4 && i !== 5);
const shelfRow = (y: number, xs: number[]): Box[] => xs.map((x) => ({ x1: x, y1: y, x2: x + 50, y2: y + 120, score: 0.9 }));

const b = (x1: number, y1: number, x2: number, y2: number): Box => ({ x1, y1, x2, y2, score: 0.9 });

describe("analyzeShelf", () => {
  it("knows nothing about an empty photo", () => {
    expect(analyzeShelf([])).toEqual({ rows: [], gaps: [], occupancy: null });
  });

  it("finds no gaps in a full row", () => {
    const result = analyzeShelf(shelfRow(0, FULL_ROW));
    expect(result.gaps).toEqual([]);
    expect(result.occupancy).toBe(1);
  });

  it("finds missing products mid-row", () => {
    const result = analyzeShelf([...shelfRow(0, GAPPY_ROW), ...shelfRow(200, FULL_ROW)]);
    expect(result.gaps).toHaveLength(1);
    expect(result.gaps[0]).toMatchObject({ row: 0, x1: 240, x2: 370, width_ratio: 2.6 });
  });

  it("measures a short row against the whole shelf", () => {
    const result = analyzeShelf([...shelfRow(0, FULL_ROW.slice(0, 6)), ...shelfRow(200, FULL_ROW)]);
    expect(result.gaps.map((g) => [g.row, g.x1, g.x2])).toEqual([[0, 360, 600]]);
  });

  it("ignores normal spacing but catches one missing product", () => {
    const nudged = [...FULL_ROW.slice(0, 5), FULL_ROW[5] + 20, ...FULL_ROW.slice(6)];
    expect(analyzeShelf(shelfRow(0, nudged)).gaps).toEqual([]);
    const [gap] = analyzeShelf(shelfRow(0, FULL_ROW.filter((_, i) => i !== 4))).gaps;
    expect(gap.width_ratio).toBe(1.4);
  });

  it("skips a row cut off by the bottom of the photo", () => {
    const sliver = [0, 60, 500, 560].map((x) => ({ x1: x, y1: 380, x2: x + 50, y2: 400, score: 0.9 }));
    const boxes = [...shelfRow(50, FULL_ROW), ...sliver];
    expect(analyzeShelf(boxes).gaps).toHaveLength(1);
    expect(analyzeShelf(boxes, 400).gaps).toEqual([]);
  });

  it("skips rows with a single product", () => {
    const result = analyzeShelf([...shelfRow(0, FULL_ROW), { x1: 500, y1: 300, x2: 550, y2: 420, score: 0.9 }]);
    expect(result.rows).toHaveLength(2);
    expect(result.gaps).toEqual([]);
  });

  it("drops a gap that runs through another row's products", () => {
    const row = [b(0, 100, 50, 200), b(200, 110, 250, 210), b(300, 100, 350, 200)];
    const lowerBay = [b(55, 160, 125, 260), b(125, 160, 195, 260)];
    expect(analyzeShelf(row).gaps.map((g) => g.x1)).toEqual([50, 250]);
    expect(analyzeShelf([...row, ...lowerBay]).gaps.map((g) => g.x1)).toEqual([250]);
  });

  it("counts overlapping boxes once when measuring cover", () => {
    const gap = { row: 0, x1: 0, y1: 0, x2: 100, y2: 100, width_ratio: 1 };
    expect(coveredFraction(gap, [])).toBe(0);
    expect(coveredFraction(gap, [b(0, 0, 50, 100), b(25, 0, 50, 100)])).toBe(0.5);
    expect(coveredFraction(gap, [b(-10, -10, 110, 50), b(0, 40, 100, 200)])).toBe(1);
  });
});

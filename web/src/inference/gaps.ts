// Port of lacuna/vision/gaps.py for in-browser scans. Keep the two in step:
// e2e/parity.spec.ts checks both give the same gaps on the test shelves.

export interface Box {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  score: number;
}

export interface Gap {
  row: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width_ratio: number;
}

export interface ShelfAnalysis {
  rows: Box[][];
  gaps: Gap[];
  occupancy: number | null;
}

export const DEFAULT_MIN_GAP_RATIO = 0.8;
export const DEFAULT_MAX_COVERED = 0.2;
const EDGE_MARGIN = 0.01;

const median = (values: number[]) => {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
};
const round = (value: number, places: number) => Math.round(value * 10 ** places) / 10 ** places;
const cy = (b: Box) => (b.y1 + b.y2) / 2;

export function groupRows(boxes: Box[], minOverlap = 0.5): Box[][] {
  const rows: Box[][] = [];
  const bands: Array<[number, number]> = [];

  for (const box of [...boxes].sort((a, b) => cy(a) - cy(b))) {
    if (rows.length) {
      const [top, bottom] = bands[bands.length - 1];
      const overlap = Math.min(bottom, box.y2) - Math.max(top, box.y1);
      if (overlap >= minOverlap * Math.min(box.y2 - box.y1, bottom - top)) {
        const row = rows[rows.length - 1];
        row.push(box);
        const n = row.length;
        bands[bands.length - 1] = [top + (box.y1 - top) / n, bottom + (box.y2 - bottom) / n];
        continue;
      }
    }
    rows.push([box]);
    bands.push([box.y1, box.y2]);
  }
  return rows.map((row) => row.sort((a, b) => a.x1 - b.x1));
}

function rowGaps(row: Box[], index: number, left: number, right: number, minGapRatio: number): Gap[] {
  const productWidth = median(row.map((b) => b.x2 - b.x1));
  const top = median(row.map((b) => b.y1));
  const bottom = median(row.map((b) => b.y2));
  const minWidth = minGapRatio * productWidth;

  const gaps: Gap[] = [];
  let cursor = left;
  for (const box of [...row, { x1: right, y1: top, x2: right, y2: bottom, score: 0 }]) {
    if (box.x1 - cursor >= minWidth) {
      const ratio = (box.x1 - cursor) / productWidth;
      gaps.push({ row: index, x1: cursor, y1: top, x2: box.x1, y2: bottom, width_ratio: round(ratio, 2) });
    }
    cursor = Math.max(cursor, box.x2);
  }
  return gaps;
}

function unionLength(spans: Array<[number, number]>): number {
  let total = 0;
  let reach = -Infinity;
  for (const [start, hi] of [...spans].sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
    const lo = Math.max(start, reach);
    if (hi > lo) {
      total += hi - lo;
      reach = hi;
    }
  }
  return total;
}

// Share of the gap covered by product boxes; see covered_fraction in gaps.py.
export function coveredFraction(gap: Gap, boxes: Box[]): number {
  const area = (gap.x2 - gap.x1) * (gap.y2 - gap.y1);
  if (area <= 0) return 1;
  const clipped = boxes
    .map((b) => [Math.max(b.x1, gap.x1), Math.max(b.y1, gap.y1), Math.min(b.x2, gap.x2), Math.min(b.y2, gap.y2)])
    .filter(([x1, y1, x2, y2]) => x1 < x2 && y1 < y2);
  const edges = [...new Set(clipped.flatMap((c) => [c[0], c[2]]))].sort((a, b) => a - b);
  let covered = 0;
  for (let i = 0; i + 1 < edges.length; i++) {
    const [left, right] = [edges[i], edges[i + 1]];
    const spans = clipped.filter((c) => c[0] <= left && c[2] >= right).map((c): [number, number] => [c[1], c[3]]);
    covered += (right - left) * unionLength(spans);
  }
  return covered / area;
}

function isCutOff(row: Box[], imageHeight: number): boolean {
  const margin = EDGE_MARGIN * imageHeight;
  const clipped = row.filter((b) => b.y1 <= margin || b.y2 >= imageHeight - margin).length;
  return clipped > row.length / 2;
}

export function analyzeShelf(
  boxes: Box[],
  imageHeight: number | null = null,
  minGapRatio = DEFAULT_MIN_GAP_RATIO,
  minRowSize = 2,
  maxCovered = DEFAULT_MAX_COVERED,
): ShelfAnalysis {
  if (!boxes.length) return { rows: [], gaps: [], occupancy: null };

  const left = Math.min(...boxes.map((b) => b.x1));
  const right = Math.max(...boxes.map((b) => b.x2));
  const rows = groupRows(boxes);

  const gaps: Gap[] = [];
  let checkedRows = 0;
  rows.forEach((row, index) => {
    if (row.length < minRowSize) return;
    if (imageHeight !== null && isCutOff(row, imageHeight)) return;
    checkedRows += 1;
    const found = rowGaps(row, index, left, right, minGapRatio);
    gaps.push(...found.filter((g) => coveredFraction(g, boxes) <= maxCovered));
  });

  if (!checkedRows || right <= left) return { rows, gaps, occupancy: null };
  const empty = gaps.reduce((sum, g) => sum + (g.x2 - g.x1), 0);
  return { rows, gaps, occupancy: round(1 - empty / ((right - left) * checkedRows), 4) };
}

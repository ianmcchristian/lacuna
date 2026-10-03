// One result shape for both places a scan can run.

import { overlayUrl, scanShelf } from "./api";
import type { Gap } from "./inference/gaps";

export type Where = "browser" | "server";

export interface Result {
  key: string; // new for every scan
  where: Where;
  model: string;
  product_count: number;
  gap_count: number;
  occupancy: number | null;
  latency_ms: number;
  gaps: Gap[];
  overlay: string; // image URL
}

/** WASM plus OffscreenCanvas: every current browser, not some older Safari versions. */
export const browserSupported = () =>
  typeof WebAssembly === "object" && typeof OffscreenCanvas !== "undefined" && typeof createImageBitmap === "function";

let browserScans = 0;

export async function runScan(where: Where, file: File, shelf: string): Promise<Result> {
  if (where === "browser") {
    // loaded on first use so the page itself stays small
    const { scanInBrowser } = await import("./inference/browserScan");
    const { overlay, ...scan } = await scanInBrowser(file);
    browserScans += 1;
    return { ...scan, key: `browser-${browserScans}`, where, overlay: URL.createObjectURL(overlay) };
  }

  const scan = await scanShelf(file, shelf);
  return {
    key: scan.id,
    where,
    model: scan.model,
    product_count: scan.product_count,
    gap_count: scan.gap_count,
    occupancy: scan.occupancy,
    latency_ms: scan.latency_ms,
    gaps: scan.gaps,
    overlay: overlayUrl(scan.id),
  };
}

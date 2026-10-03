// Whole scan in the browser: detect, find gaps, draw the overlay. Nothing is uploaded.

import { MODEL_FILE, detect } from "./detector";
import { Box, Gap, analyzeShelf } from "./gaps";

export interface BrowserScan {
  model: string;
  product_count: number;
  gap_count: number;
  occupancy: number | null;
  latency_ms: number;
  gaps: Gap[];
  overlay: Blob;
}

// same colors and weights as lacuna/vision/draw.py
const PRODUCT = "rgb(60, 200, 80)";
const GAP = "rgb(230, 40, 40)";

async function drawOverlay(image: ImageBitmap, boxes: Box[], gaps: Gap[]): Promise<Blob> {
  const canvas = new OffscreenCanvas(image.width, image.height);
  const ctx = canvas.getContext("2d")!;
  const thickness = Math.max(1, Math.round(Math.min(image.width, image.height) / 400));
  const rect = (r: { x1: number; y1: number; x2: number; y2: number }) => [r.x1, r.y1, r.x2 - r.x1, r.y2 - r.y1] as const;

  ctx.drawImage(image, 0, 0);
  ctx.strokeStyle = PRODUCT;
  ctx.lineWidth = thickness;
  for (const b of boxes) ctx.strokeRect(...rect(b));

  ctx.fillStyle = GAP;
  ctx.strokeStyle = GAP;
  ctx.lineWidth = thickness * 2;
  for (const g of gaps) {
    ctx.globalAlpha = 0.35;
    ctx.fillRect(...rect(g));
    ctx.globalAlpha = 1;
    ctx.strokeRect(...rect(g));
  }
  return canvas.convertToBlob({ type: "image/jpeg", quality: 0.85 });
}

export async function scanInBrowser(file: Blob): Promise<BrowserScan> {
  const image = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    const start = performance.now();
    const boxes = await detect(image);
    const latency = performance.now() - start;
    const { gaps, occupancy } = analyzeShelf(boxes, image.height);
    return {
      model: MODEL_FILE.replace(/\.onnx$/, ""),
      product_count: boxes.length,
      gap_count: gaps.length,
      occupancy,
      latency_ms: latency,
      gaps,
      overlay: await drawOverlay(image, boxes, gaps),
    };
  } finally {
    image.close();
  }
}

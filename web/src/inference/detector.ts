// Runs the INT8 model in the browser with ONNX Runtime Web (WASM).
// Pre/post-processing mirrors lacuna/vision/detector.py.

import type { InferenceSession } from "onnxruntime-web";
import type { Box } from "./gaps";

export const MODEL_FILE = "sku110k-yolo11-s640-int8.onnx";
const SIZE = 640;
const PAD = 114; // same gray Ultralytics pads with
const CONF = 0.25;
const IOU = 0.45;
const MAX_DET = 1000;

type Ort = typeof import("onnxruntime-web/wasm");
let loading: Promise<{ ort: Ort; session: InferenceSession }> | null = null;

/** Load the runtime and model once, on first use. ~10 MB model plus ~12 MB of WASM. */
export function loadModel() {
  loading ??= (async () => {
    const ort = await import("onnxruntime-web/wasm");
    // threads need cross-origin isolation headers, which GitHub Pages can't send
    ort.env.wasm.numThreads = 1;
    const session = await ort.InferenceSession.create(`${import.meta.env.BASE_URL}model/${MODEL_FILE}`, {
      executionProviders: ["wasm"],
    });
    return { ort, session };
  })();
  loading.catch(() => (loading = null)); // let a retry start over
  return loading;
}

interface Letterbox {
  scale: number;
  padX: number;
  padY: number;
}

/** Resize keeping aspect ratio, pad to a square, return an NCHW RGB float tensor. */
function letterbox(image: ImageBitmap): { data: Float32Array; lb: Letterbox } {
  const scale = Math.min(SIZE / image.height, SIZE / image.width);
  const w = Math.round(image.width * scale);
  const h = Math.round(image.height * scale);
  const padX = (SIZE - w) >> 1;
  const padY = (SIZE - h) >> 1;

  const canvas = new OffscreenCanvas(SIZE, SIZE);
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  ctx.fillStyle = `rgb(${PAD}, ${PAD}, ${PAD})`;
  ctx.fillRect(0, 0, SIZE, SIZE);
  ctx.imageSmoothingQuality = "low"; // bilinear, closest to cv2.INTER_LINEAR
  ctx.drawImage(image, padX, padY, w, h);

  const rgba = ctx.getImageData(0, 0, SIZE, SIZE).data;
  const plane = SIZE * SIZE;
  const data = new Float32Array(3 * plane);
  for (let i = 0; i < plane; i++) {
    data[i] = rgba[i * 4] / 255;
    data[plane + i] = rgba[i * 4 + 1] / 255;
    data[2 * plane + i] = rgba[i * 4 + 2] / 255;
  }
  return { data, lb: { scale, padX, padY } };
}

const area = (b: Box) => (b.x2 - b.x1) * (b.y2 - b.y1);

/** Greedy non-max suppression, best score first. */
export function nms(boxes: Box[], iou = IOU): Box[] {
  const keep: Box[] = [];
  for (const box of [...boxes].sort((a, b) => b.score - a.score)) {
    const overlaps = keep.some((k) => {
      const ix = Math.max(0, Math.min(k.x2, box.x2) - Math.max(k.x1, box.x1));
      const iy = Math.max(0, Math.min(k.y2, box.y2) - Math.max(k.y1, box.y1));
      const inter = ix * iy;
      return inter / (area(k) + area(box) - inter + 1e-9) > iou;
    });
    if (!overlaps) keep.push(box);
  }
  return keep;
}

/** Model output [1, 5, N] (cx, cy, w, h, score) to boxes in original image pixels. */
export function decode(output: Float32Array, n: number, lb: Letterbox, width: number, height: number): Box[] {
  const clip = (v: number, max: number) => Math.min(Math.max(v, 0), max);
  const candidates: Box[] = [];
  for (let i = 0; i < n; i++) {
    const score = output[4 * n + i];
    if (score < CONF) continue;
    const cx = output[i], cy = output[n + i], w = output[2 * n + i], h = output[3 * n + i];
    candidates.push({
      x1: clip((cx - w / 2 - lb.padX) / lb.scale, width),
      y1: clip((cy - h / 2 - lb.padY) / lb.scale, height),
      x2: clip((cx + w / 2 - lb.padX) / lb.scale, width),
      y2: clip((cy + h / 2 - lb.padY) / lb.scale, height),
      score,
    });
  }
  return nms(candidates).slice(0, MAX_DET);
}

export async function detect(image: ImageBitmap): Promise<Box[]> {
  const { ort, session } = await loadModel();
  const { data, lb } = letterbox(image);
  const input = new ort.Tensor("float32", data, [1, 3, SIZE, SIZE]);
  const results = await session.run({ [session.inputNames[0]]: input });
  const output = results[session.outputNames[0]];
  return decode(output.data as Float32Array, output.dims[2], lb, image.width, image.height);
}

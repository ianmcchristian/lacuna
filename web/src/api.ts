// Thin client for the Lacuna API.

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_BYTES = 10 * 1024 * 1024;
export const SHELF_CODE = /^[A-Za-z0-9._-]{1,64}$/;

export interface Gap {
  row: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width_ratio: number;
}

export interface Scan {
  id: string;
  image_id: string;
  model: string;
  product_count: number;
  gap_count: number;
  occupancy: number | null;
  latency_ms: number;
  created_at: string;
  gaps: Gap[];
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(0, "Can't reach the Lacuna API. It may be waking up, try again in a moment.");
  }
  if (!resp.ok) {
    let detail = resp.statusText || "Request failed";
    try {
      const body = (await resp.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // not json, keep the status text
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

/** Upload a photo, then run detection on it. */
export async function scanShelf(file: File, shelf: string): Promise<Scan> {
  const form = new FormData();
  form.append("file", file);
  if (shelf) form.append("shelf", shelf);

  const image = await request<{ id: string }>("/images", { method: "POST", body: form });
  return request<Scan>("/detect", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ image_id: image.id }),
  });
}

export const overlayUrl = (scanId: string) => `${API_URL}/results/${scanId}/overlay`;

/** Client-side checks that mirror the API, so people get errors before uploading. */
export function validateFile(file: File | undefined): string | null {
  if (!file) return "Choose a shelf photo.";
  if (!ALLOWED_TYPES.includes(file.type)) return "Use a JPEG, PNG, or WebP image.";
  if (file.size > MAX_BYTES) return "That photo is over 10 MB.";
  return null;
}

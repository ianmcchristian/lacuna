// Occupancy over time as a plain SVG line. No chart library: one line and two
// axes don't need 50 KB. The data table under it is the accessible version.

import { useId } from "react";
import type { HistoryPoint } from "./api";
import { day, percent } from "./format";

const WIDTH = 640;
const HEIGHT = 240;
const PAD = { top: 16, right: 20, bottom: 32, left: 48 };
const Y_TICKS = [0, 0.25, 0.5, 0.75, 1];

export interface Plotted {
  x: number;
  y: number;
  point: HistoryPoint;
}

/** Points in SVG coords, oldest first. Scans with unknown occupancy are left out. */
export function plot(scans: HistoryPoint[]): Plotted[] {
  const known = scans
    .filter((s) => s.occupancy !== null)
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  if (!known.length) return [];

  const first = Date.parse(known[0].created_at);
  const span = Date.parse(known[known.length - 1].created_at) - first;
  const plotWidth = WIDTH - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;

  return known.map((point) => ({
    // one scan, or all at the same moment: center them
    x: PAD.left + (span ? ((Date.parse(point.created_at) - first) / span) * plotWidth : plotWidth / 2),
    y: PAD.top + (1 - (point.occupancy ?? 0)) * plotHeight,
    point,
  }));
}

export function describe(shelf: string, points: Plotted[]) {
  if (!points.length) return `No scans of ${shelf} could be measured.`;
  const values = points.map((p) => p.point.occupancy ?? 0);
  const first = points[0].point;
  const last = points[points.length - 1].point;
  const scans = points.length === 1 ? "1 scan" : `${points.length} scans`;
  return (
    `${scans} from ${day(first.created_at)} to ${day(last.created_at)}. ` +
    `Latest ${percent(last.occupancy)}, lowest ${percent(Math.min(...values))}, highest ${percent(Math.max(...values))}.`
  );
}

export function OccupancyChart({ shelf, scans }: { shelf: string; scans: HistoryPoint[] }) {
  const id = useId();
  const points = plot(scans);
  const line = points.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const xLabels = points.length > 1 ? [points[0], points[points.length - 1]] : points;

  return (
    <svg
      className="chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-desc`}
    >
      <title id={`${id}-title`}>Occupancy over time for {shelf}</title>
      <desc id={`${id}-desc`}>{describe(shelf, points)}</desc>

      {Y_TICKS.map((tick) => {
        const y = PAD.top + (1 - tick) * (HEIGHT - PAD.top - PAD.bottom);
        return (
          <g key={tick} aria-hidden="true">
            <line className="grid" x1={PAD.left} x2={WIDTH - PAD.right} y1={y} y2={y} />
            <text className="tick" x={PAD.left - 8} y={y} textAnchor="end" dominantBaseline="middle">
              {tick * 100}%
            </text>
          </g>
        );
      })}

      {xLabels.map((p, i) => (
        <text
          key={p.point.scan_id}
          className="tick"
          aria-hidden="true"
          x={p.x}
          y={HEIGHT - 8}
          textAnchor={xLabels.length === 1 ? "middle" : i === 0 ? "start" : "end"}
        >
          {day(p.point.created_at)}
        </text>
      ))}

      {points.length > 1 && <path className="line" d={line} aria-hidden="true" />}
      {points.map((p) => (
        <circle key={p.point.scan_id} className="dot" cx={p.x} cy={p.y} r={5} aria-hidden="true" />
      ))}
    </svg>
  );
}

// Display helpers shared by the scan and shelf pages.

export const percent = (value: number | null) => (value === null ? "Unknown" : `${Math.round(value * 100)}%`);

/** Signed change in percentage points, e.g. "+12 pts". */
export function change(value: number | null) {
  if (value === null) return "First scan";
  const points = Math.round(value * 100);
  if (points === 0) return "No change";
  return `${points > 0 ? "+" : "\u2212"}${Math.abs(points)} pts`;
}

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

export const when = (iso: string) => dateTime.format(new Date(iso));
export const day = (iso: string) => dateOnly.format(new Date(iso));

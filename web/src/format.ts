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
const timeOnly = new Intl.DateTimeFormat(undefined, { timeStyle: "short" });

export const when = (iso: string) => dateTime.format(new Date(iso));

/** Short label for a point in a series: the day, or the time if the series fits in one day. */
export function axisLabel(first: string, last: string) {
  const sameDay = dateOnly.format(new Date(first)) === dateOnly.format(new Date(last));
  return (iso: string) => (sameDay ? timeOnly : dateOnly).format(new Date(iso));
}

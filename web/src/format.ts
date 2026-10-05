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
const timeSeconds = new Intl.DateTimeFormat(undefined, { timeStyle: "medium" });

const dateTimeSeconds = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" });

export const when = (iso: string) => dateTime.format(new Date(iso));
// scans of one shelf can be seconds apart, so the scan log keeps the seconds
export const whenExact = (iso: string) => dateTimeSeconds.format(new Date(iso));

/** Label for points in a series: the coarsest of day, time, or seconds that tells first and last apart. */
export function axisLabel(first: string, last: string) {
  const formats = [dateOnly, timeOnly, timeSeconds];
  const fmt = formats.find((f) => f.format(new Date(first)) !== f.format(new Date(last))) ?? timeSeconds;
  return (iso: string) => fmt.format(new Date(iso));
}

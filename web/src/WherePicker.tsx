import type { Where } from "./runScan";

interface Props {
  where: Where;
  browserOk: boolean;
  busy: boolean;
  onChange: (where: Where) => void;
}

const CHOICES: Array<{ value: Where; label: string; hint: string }> = [
  {
    value: "browser",
    label: "In this browser",
    hint: "Fastest, and the photo never leaves your device. The first scan downloads the model (about 25 MB).",
  },
  {
    value: "server",
    label: "On the server",
    hint: "Saves the scan to the database, so a shelf can be tracked over time. The free server can take a minute to wake up.",
  },
];

export function WherePicker({ where, browserOk, busy, onChange }: Props) {
  return (
    <fieldset className="where" disabled={busy}>
      <legend>Run the model</legend>
      {CHOICES.map(({ value, label, hint }) => {
        const unavailable = value === "browser" && !browserOk;
        return (
          <div className="choice" key={value}>
            <input
              type="radio"
              id={`where-${value}`}
              name="where"
              value={value}
              checked={where === value}
              disabled={unavailable}
              onChange={() => onChange(value)}
              aria-describedby={`where-${value}-hint`}
            />
            <label htmlFor={`where-${value}`}>{label}</label>
            <p id={`where-${value}-hint`} className="hint">
              {unavailable ? "Not supported in this browser." : hint}
            </p>
          </div>
        );
      })}
    </fieldset>
  );
}

// One shelf over time: a chart, then every scan as a table.

import { useState } from "react";
import { ApiError, WAKING, getShelfHistory, overlayUrl, setBaseline } from "./api";
import { change, percent, whenExact } from "./format";
import { MissingSince } from "./MissingSince";
import { OccupancyChart } from "./OccupancyChart";
import { PageHeading } from "./PageHeading";
import { href } from "./route";
import { useLoad } from "./useLoad";

export function ShelfPage({ shelf, focus }: { shelf: string; focus: boolean }) {
  const history = useLoad(shelf, () => getShelfHistory(shelf));
  const scans = history.kind === "done" ? history.data.scans : [];
  const latest = scans[0]; // newest first

  // the choice is kept here rather than refetched, so the table (and focus) stays put
  const [chosen, setChosen] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const baselineId = chosen ?? (history.kind === "done" ? history.data.baseline_scan_id : null);
  const baselineAt = scans.find((s) => s.scan_id === baselineId)?.created_at;

  async function chooseBaseline(scanId: string, at: string) {
    if (saving || scanId === baselineId) return;
    setSaving(true);
    try {
      await setBaseline(shelf, scanId);
      setChosen(scanId);
      setNote({ ok: true, text: `The scan from ${whenExact(at)} is now the baseline.` });
    } catch (err) {
      setNote({ ok: false, text: err instanceof ApiError ? err.message : "Couldn't set the baseline. Try again." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby="shelf-heading">
      <p>
        <a href={href.shelves}>All shelves</a>
      </p>
      <PageHeading id="shelf-heading" focus={focus}>
        Shelf {shelf}
      </PageHeading>

      <p role="status" className="status">
        {history.kind === "loading" && WAKING}
      </p>
      {history.kind === "error" && (
        <p role="alert" className="error">
          {history.status === 404 ? `No scans saved for shelf ${shelf} yet.` : history.message}
        </p>
      )}

      {latest && (
        <>
          <dl className="summary">
            <div>
              <dt>Occupancy now</dt>
              <dd>{percent(latest.occupancy)}</dd>
            </div>
            <div>
              <dt>Since last scan</dt>
              <dd>{change(latest.occupancy_change)}</dd>
            </div>
            <div>
              <dt>Gaps now</dt>
              <dd>{latest.gap_count}</dd>
            </div>
            <div>
              <dt>Scans</dt>
              <dd>{scans.length}</dd>
            </div>
          </dl>

          <figure>
            <OccupancyChart shelf={shelf} scans={scans} />
            <figcaption>Share of the shelf with product on it, at each scan.</figcaption>
          </figure>

          {!baselineId && (
            <p className="hint">
              Press Baseline on a scan taken when the shelf was full. Gaps in later scans are then matched to the
              products that used to be there.
            </p>
          )}
          {baselineId && latest.scan_id !== baselineId && (
            <MissingSince scanId={latest.scan_id} baselineId={baselineId} baselineAt={baselineAt} />
          )}
          {baselineId && latest.scan_id === baselineId && (
            <p className="hint">The latest scan is the baseline. Scan the shelf again later to see what sold out.</p>
          )}

          <p role="status" className="status">
            {note?.ok && note.text}
          </p>
          {note && !note.ok && (
            <p role="alert" className="error">
              {note.text}
            </p>
          )}

          <div className="table-scroll">
            <table>
              <caption>Every scan, newest first</caption>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Occupancy</th>
                  <th scope="col">Change</th>
                  <th scope="col">Gaps</th>
                  <th scope="col">Photo</th>
                  <th scope="col">Compare to</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => (
                  <tr key={s.scan_id}>
                    <th scope="row">{whenExact(s.created_at)}</th>
                    <td>{percent(s.occupancy)}</td>
                    <td>{change(s.occupancy_change)}</td>
                    <td>{s.gap_count}</td>
                    <td>
                      <a href={overlayUrl(s.scan_id)} target="_blank" rel="noreferrer">
                        View<span className="visually-hidden"> photo from {whenExact(s.created_at)} (opens in a new tab)</span>
                      </a>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="toggle"
                        aria-pressed={s.scan_id === baselineId}
                        onClick={() => chooseBaseline(s.scan_id, s.created_at)}
                      >
                        Baseline<span className="visually-hidden"> scan from {whenExact(s.created_at)}</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

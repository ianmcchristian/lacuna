// One shelf over time: a chart, then every scan as a table.

import { WAKING, getShelfHistory, overlayUrl } from "./api";
import { change, percent, when } from "./format";
import { OccupancyChart } from "./OccupancyChart";
import { PageHeading } from "./PageHeading";
import { href } from "./route";
import { useLoad } from "./useLoad";

export function ShelfPage({ shelf, focus }: { shelf: string; focus: boolean }) {
  const history = useLoad(shelf, () => getShelfHistory(shelf));
  const scans = history.kind === "done" ? history.data.scans : [];
  const latest = scans[0]; // newest first

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
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => (
                  <tr key={s.scan_id}>
                    <th scope="row">{when(s.created_at)}</th>
                    <td>{percent(s.occupancy)}</td>
                    <td>{change(s.occupancy_change)}</td>
                    <td>{s.gap_count}</td>
                    <td>
                      <a href={overlayUrl(s.scan_id)} target="_blank" rel="noreferrer">
                        View<span className="visually-hidden"> photo from {when(s.created_at)} (opens in a new tab)</span>
                      </a>
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

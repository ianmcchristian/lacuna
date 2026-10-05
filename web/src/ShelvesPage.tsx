// Every saved shelf, emptiest first: where to send a restock.

import { WAKING, getWorstShelves } from "./api";
import { percent, when } from "./format";
import { PageHeading } from "./PageHeading";
import { href } from "./route";
import { useLoad } from "./useLoad";

export function ShelvesPage({ focus }: { focus: boolean }) {
  const shelves = useLoad("worst", () => getWorstShelves());

  return (
    <section aria-labelledby="shelves-heading">
      <PageHeading id="shelves-heading" focus={focus}>
        Shelf history
      </PageHeading>
      <p className="hint">
        Shelves scanned on the server with a shelf code, emptiest first. Pick one to see how it changed over time.
      </p>

      <p role="status" className="status">
        {shelves.kind === "loading" && WAKING}
      </p>
      {shelves.kind === "error" && (
        <p role="alert" className="error">
          {shelves.message}
        </p>
      )}

      {shelves.kind === "done" && shelves.data.length === 0 && (
        <p>
          No shelves yet. <a href={href.scan}>Scan a shelf</a> on the server with a shelf code, like aisle4-bay2, and
          it shows up here.
        </p>
      )}

      {shelves.kind === "done" && shelves.data.length > 0 && (
        <div className="table-scroll">
          <table>
            <caption>Shelves by latest occupancy, emptiest first</caption>
            <thead>
              <tr>
                <th scope="col">Shelf</th>
                <th scope="col">Latest occupancy</th>
                <th scope="col">Gaps now</th>
                <th scope="col">Average</th>
                <th scope="col">Scans</th>
                <th scope="col">Last scanned</th>
              </tr>
            </thead>
            <tbody>
              {shelves.data.map((s) => (
                <tr key={s.shelf}>
                  <th scope="row">
                    <a href={href.shelf(s.shelf)}>{s.shelf}</a>
                  </th>
                  <td>{percent(s.latest_occupancy)}</td>
                  <td>{s.latest_gap_count ?? "Unknown"}</td>
                  <td>{percent(s.avg_occupancy)}</td>
                  <td>{s.scan_count}</td>
                  <td>{when(s.last_scanned_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

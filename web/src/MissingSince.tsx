// What sold out: for each gap in the latest scan, the products the baseline had there.

import { cropUrl, getMissing } from "./api";
import { whenExact } from "./format";
import { useLoad } from "./useLoad";

interface Props {
  scanId: string; // the scan to explain, usually the latest
  baselineId: string;
  baselineAt: string | undefined; // undefined if the baseline is older than the history shown
}

export function MissingSince({ scanId, baselineId, baselineAt }: Props) {
  const missing = useLoad(`${scanId}:${baselineId}`, () => getMissing(scanId));
  const since = baselineAt ? ` (${whenExact(baselineAt)})` : "";

  return (
    <section aria-labelledby="missing-heading">
      <h3 id="missing-heading">What sold out since the baseline{since}</h3>
      <p role="status" className="status">
        {missing.kind === "loading" && "Lining the photos up with the baseline\u2026"}
      </p>
      {missing.kind === "error" && (
        <p role="alert" className="error">
          {missing.message}
        </p>
      )}
      {missing.kind === "done" && !missing.data.aligned && (
        <p>
          The latest photo and the baseline don't line up well enough to compare. Retake it from about the same spot.
        </p>
      )}
      {missing.kind === "done" && missing.data.aligned && missing.data.gaps.length === 0 && (
        <p>No gaps in the latest scan, so nothing has sold out.</p>
      )}
      {missing.kind === "done" && missing.data.aligned && missing.data.gaps.length > 0 && (
        <ol className="missing">
          {missing.data.gaps.map(({ gap, products }, i) => (
            <li key={i}>
              <p>
                Gap {i + 1}, shelf row {gap.row + 1}:{" "}
                {products.length === 0
                  ? "nothing in the baseline sat here."
                  : `${products.length} ${products.length === 1 ? "product" : "products"} sold out.`}
              </p>
              {products.length > 0 && (
                <ul className="crops">
                  {products.map((p, n) => (
                    <li key={p.id}>
                      <img
                        src={cropUrl(baselineId, p.id)}
                        alt={`Product ${n + 1} of ${products.length} that was in gap ${i + 1} in the baseline photo`}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

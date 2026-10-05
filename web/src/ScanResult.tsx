import { useEffect, useRef } from "react";
import { percent } from "./format";
import { href } from "./route";
import type { Result } from "./runScan";

function Verdict({ scan }: { scan: Result }) {
  // no occupancy means no row had enough products to measure, so don't call it full
  if (scan.occupancy === null) {
    return <p>Not enough products found to check for gaps. Try a clearer photo taken straight on.</p>;
  }
  if (scan.gaps.length === 0) return <p>No gaps found. This shelf looks fully stocked.</p>;
  return (
    <table>
      <caption>Gaps by shelf row, top row is 1</caption>
      <thead>
        <tr>
          <th scope="col">Row</th>
          <th scope="col">From x (px)</th>
          <th scope="col">To x (px)</th>
          <th scope="col">Width in products</th>
        </tr>
      </thead>
      <tbody>
        {scan.gaps.map((gap, i) => (
          <tr key={i}>
            <td>{gap.row + 1}</td>
            <td>{Math.round(gap.x1)}</td>
            <td>{Math.round(gap.x2)}</td>
            <td>{gap.width_ratio.toFixed(1)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ScanResult({ scan }: { scan: Result }) {
  const heading = useRef<HTMLHeadingElement>(null);

  // move focus to the new results so keyboard and screen reader users land on them
  useEffect(() => heading.current?.focus(), [scan.key]);

  // browser scans draw their overlay into a blob URL; free it when it's replaced
  useEffect(() => {
    const url = scan.overlay;
    return () => {
      if (url.startsWith("blob:")) URL.revokeObjectURL(url);
    };
  }, [scan.overlay]);

  const gapWord = scan.gap_count === 1 ? "gap" : "gaps";
  const alt = `Shelf photo with ${scan.product_count} products outlined in green and ${scan.gap_count} ${gapWord} shaded red.`;

  return (
    <section aria-labelledby="result-heading">
      <h2 id="result-heading" ref={heading} tabIndex={-1}>
        Results
      </h2>
      <p className="hint">
        {scan.where === "browser" ? "Ran in your browser" : "Ran on the server and saved"} with {scan.model}.
        {scan.shelf && (
          <>
            {" "}
            <a href={href.shelf(scan.shelf)}>See the history for shelf {scan.shelf}</a>.
          </>
        )}
      </p>

      <dl className="summary">
        <div>
          <dt>Gaps found</dt>
          <dd>{scan.gap_count}</dd>
        </div>
        <div>
          <dt>Products found</dt>
          <dd>{scan.product_count}</dd>
        </div>
        <div>
          <dt>Shelf occupancy</dt>
          <dd>{percent(scan.occupancy)}</dd>
        </div>
        <div>
          <dt>Inference time</dt>
          <dd>{Math.round(scan.latency_ms)} ms</dd>
        </div>
      </dl>

      <figure>
        <img src={scan.overlay} alt={alt} />
        <figcaption>Green outlines are products. Red shaded boxes are gaps.</figcaption>
      </figure>

      <Verdict scan={scan} />
    </section>
  );
}

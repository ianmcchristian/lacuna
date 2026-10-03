import { SAMPLES, Sample, samplePath } from "./samples";

interface Props {
  busy: boolean;
  onPick: (sample: Sample) => void;
}

export function SamplePicker({ busy, onPick }: Props) {
  return (
    <section aria-labelledby="samples-heading" className="samples">
      <h2 id="samples-heading">Or try a sample shelf</h2>
      <p className="hint">
        AI-generated photos, each testing one situation. The ones marked "hard case" are known
        failures, kept on purpose.
      </p>
      <ul className="sample-grid">
        {SAMPLES.map((sample) => (
          <li key={sample.name}>
            <button type="button" className="sample" disabled={busy} onClick={() => onPick(sample)}>
              {/* decorative: the button text says what the photo is */}
              <img src={`${import.meta.env.BASE_URL}${samplePath(sample, true)}`} alt="" loading="lazy" />
              <span className="sample-label">{sample.label}</span>
              <span className="sample-note">{sample.note}</span>
              {sample.hard && <span className="badge">Hard case</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

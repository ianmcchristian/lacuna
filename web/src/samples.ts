// Shelf photos anyone can scan without bringing their own. All AI-generated.
// The files live in the repo's docs/ folder (the README and model tests use them too);
// vite.config.ts serves them under samples/.

export interface Sample {
  name: string;
  dir: "demo" | "scenarios";
  label: string;
  note: string;
  hard?: boolean; // a known failure, kept on purpose
}

export const SAMPLES: Sample[] = [
  { name: "depleted", dir: "scenarios", label: "Depleted", note: "6 holes across 3 rows" },
  { name: "canned-goods", dir: "demo", label: "Canned goods", note: "One hole mid-row, one at the end" },
  { name: "cereal", dir: "demo", label: "Cereal", note: "A hole just one box wide" },
  { name: "bottles", dir: "demo", label: "Bottles", note: "A 4-bottle hole and a 1-bottle hole" },
  { name: "fully-stocked", dir: "scenarios", label: "Fully stocked", note: "Nothing missing" },
  { name: "mixed-sizes", dir: "scenarios", label: "Mixed sizes", note: "Cans next to 2 L bottles" },
  { name: "cooler-glare", dir: "scenarios", label: "Cooler glare", note: "Reflections on the glass" },
  { name: "low-light", dir: "scenarios", label: "Low light", note: "Dim aisle, grainy photo" },
  { name: "messy", dir: "scenarios", label: "Messy", note: "Knocked-over boxes read as a hole", hard: true },
  { name: "empty-row", dir: "scenarios", label: "Empty row", note: "A fully empty shelf isn't reported", hard: true },
  { name: "angled", dir: "scenarios", label: "Angled", note: "A steep angle breaks row grouping", hard: true },
];

export const samplePath = (sample: Sample, thumb = false) =>
  `samples/${thumb ? "thumbs/" : ""}${sample.name}.jpg`;

export async function loadSample(sample: Sample): Promise<File> {
  const resp = await fetch(`${import.meta.env.BASE_URL}${samplePath(sample)}`);
  if (!resp.ok) throw new Error(`couldn't load the ${sample.label} sample`);
  return new File([await resp.blob()], `${sample.name}.jpg`, { type: "image/jpeg" });
}

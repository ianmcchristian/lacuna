import { useState } from "react";
import { ApiError, Scan, scanShelf } from "./api";
import { SamplePicker } from "./SamplePicker";
import { ScanResult } from "./ScanResult";
import { UploadForm } from "./UploadForm";
import { Sample, loadSample } from "./samples";

type State =
  | { kind: "idle" }
  | { kind: "scanning"; what: string }
  | { kind: "done"; scan: Scan }
  | { kind: "error"; message: string };

export function App() {
  const [state, setState] = useState<State>({ kind: "idle" });

  async function run(what: string, getFile: () => Promise<File>, shelf = "") {
    setState({ kind: "scanning", what });
    try {
      setState({ kind: "done", scan: await scanShelf(await getFile(), shelf) });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Try again.";
      setState({ kind: "error", message });
    }
  }

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header>
        <h1>Lacuna</h1>
        <p>Upload a shelf photo to find where product is missing.</p>
      </header>
      <main id="main">
        <UploadForm
          busy={state.kind === "scanning"}
          onScan={(file, shelf) => run("your shelf photo", async () => file, shelf)}
        />
        <SamplePicker
          busy={state.kind === "scanning"}
          onPick={(sample: Sample) => run(`the ${sample.label} sample`, () => loadSample(sample))}
        />

        <p role="status" className="status">
          {state.kind === "scanning" && `Scanning ${state.what}…`}
        </p>
        {state.kind === "error" && (
          <p role="alert" className="error">
            {state.message}
          </p>
        )}

        {state.kind === "done" && <ScanResult scan={state.scan} />}
      </main>
      <footer>
        <p>
          Product detection by a YOLO11 model trained on SKU-110K.{" "}
          <a href="https://github.com/ianmcchristian/lacuna">Source on GitHub</a>
        </p>
      </footer>
    </>
  );
}

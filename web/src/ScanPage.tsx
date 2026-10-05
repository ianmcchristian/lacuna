// Upload or pick a shelf photo and scan it, in the browser or on the server.

import { useState } from "react";
import { ApiError } from "./api";
import { SamplePicker } from "./SamplePicker";
import { ScanResult } from "./ScanResult";
import { UploadForm } from "./UploadForm";
import { WherePicker } from "./WherePicker";
import { Result, Where, browserSupported, runScan } from "./runScan";
import { Sample, loadSample } from "./samples";

type State =
  | { kind: "idle" }
  | { kind: "scanning"; what: string }
  | { kind: "done"; result: Result }
  | { kind: "error"; message: string };

function errorMessage(err: unknown, where: Where) {
  if (err instanceof ApiError) return err.message;
  if (where === "browser") return "Couldn't run the model in this browser. Try running it on the server instead.";
  return "Something went wrong. Try again.";
}

export function ScanPage() {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [where, setWhere] = useState<Where>(browserSupported() ? "browser" : "server");
  const busy = state.kind === "scanning";

  async function run(what: string, getFile: () => Promise<File>, shelf = "") {
    const place = where === "browser" ? "in your browser" : "on the server";
    setState({ kind: "scanning", what: `${what} ${place}` });
    try {
      setState({ kind: "done", result: await runScan(where, await getFile(), shelf) });
    } catch (err) {
      setState({ kind: "error", message: errorMessage(err, where) });
    }
  }

  return (
    <>
      <WherePicker where={where} browserOk={browserSupported()} busy={busy} onChange={setWhere} />
      <UploadForm
        busy={busy}
        askShelf={where === "server"}
        onScan={(file, shelf) => run("your shelf photo", async () => file, shelf)}
      />
      <SamplePicker busy={busy} onPick={(sample: Sample) => run(`the ${sample.label} sample`, () => loadSample(sample))} />

      <p role="status" className="status">
        {state.kind === "scanning" && `Scanning ${state.what}…`}
      </p>
      {state.kind === "error" && (
        <p role="alert" className="error">
          {state.message}
        </p>
      )}

      {state.kind === "done" && <ScanResult scan={state.result} />}
    </>
  );
}

import { useState } from "react";
import { ApiError, Scan, scanShelf } from "./api";
import { ScanResult } from "./ScanResult";
import { UploadForm } from "./UploadForm";

type State =
  | { kind: "idle" }
  | { kind: "scanning" }
  | { kind: "done"; scan: Scan }
  | { kind: "error"; message: string };

export function App() {
  const [state, setState] = useState<State>({ kind: "idle" });

  async function handleScan(file: File, shelf: string) {
    setState({ kind: "scanning" });
    try {
      setState({ kind: "done", scan: await scanShelf(file, shelf) });
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
        <UploadForm busy={state.kind === "scanning"} onScan={handleScan} />

        <p role="status" className="status">
          {state.kind === "scanning" && "Scanning your shelf photo…"}
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

/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";
import { MODEL_FILE } from "./src/inference/detector";
import { SAMPLES, samplePath } from "./src/samples";

// Files from outside web/, kept in one place for the API, tests, and UI:
// sample photos from docs/, and the INT8 model from models/ (scripts/quantize.py).
// Served in dev and copied into the build.
function sharedFiles(): Plugin {
  const docs = resolve(__dirname, "../docs");
  const model = resolve(__dirname, "../models", MODEL_FILE);
  const files = new Map<string, string>([[`model/${MODEL_FILE}`, model]]);
  for (const sample of SAMPLES) {
    files.set(samplePath(sample), resolve(docs, sample.dir, `${sample.name}.jpg`));
    files.set(samplePath(sample, true), resolve(docs, "thumbs", `${sample.name}.jpg`));
  }
  let base = "/";

  return {
    name: "shared-files",
    configResolved(config) {
      base = config.base;
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = files.get((req.url ?? "").split("?")[0].slice(base.length));
        if (!path || !existsSync(path)) return next();
        res.setHeader("content-type", path.endsWith(".onnx") ? "application/octet-stream" : "image/jpeg");
        res.end(readFileSync(path));
      });
    },
    generateBundle() {
      if (!existsSync(model)) {
        this.error(`${model} is missing. Run scripts/download_weights.py s and scripts/quantize.py first.`);
      }
      for (const [fileName, path] of files) {
        this.emitFile({ type: "asset", fileName, source: readFileSync(path) });
      }
    },
  };
}

// GitHub Pages serves from /lacuna/, local dev from /
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react(), sharedFiles()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});

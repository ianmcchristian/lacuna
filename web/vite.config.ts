/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";
import { SAMPLES, samplePath } from "./src/samples";

// Sample photos stay in docs/ (one copy for the README, model tests, and the UI).
// Served in dev and copied into the build under samples/.
function samplePhotos(): Plugin {
  const docs = resolve(__dirname, "../docs");
  const files = new Map<string, string>();
  for (const sample of SAMPLES) {
    files.set(samplePath(sample), resolve(docs, sample.dir, `${sample.name}.jpg`));
    files.set(samplePath(sample, true), resolve(docs, "thumbs", `${sample.name}.jpg`));
  }
  let base = "/";

  return {
    name: "sample-photos",
    configResolved(config) {
      base = config.base;
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = files.get((req.url ?? "").split("?")[0].slice(base.length));
        if (!path) return next();
        res.setHeader("content-type", "image/jpeg");
        res.end(readFileSync(path));
      });
    },
    generateBundle() {
      for (const [fileName, path] of files) {
        this.emitFile({ type: "asset", fileName, source: readFileSync(path) });
      }
    },
  };
}

// GitHub Pages serves from /lacuna/, local dev from /
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react(), samplePhotos()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});

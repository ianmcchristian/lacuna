/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// GitHub Pages serves from /lacuna/, local dev from /
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
});

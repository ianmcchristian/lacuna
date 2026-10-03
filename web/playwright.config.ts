import { defineConfig, devices } from "@playwright/test";

// Real browser checks on the production build. The API is mocked in the tests,
// so this needs no backend.
export default defineConfig({
  testDir: "e2e",
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:4173",
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command: "npm run build && npm run preview -- --port 4173 --strictPort",
    env: { VITE_API_URL: "http://api.test" },
    url: "http://localhost:4173",
    reuseExistingServer: !process.env.CI,
  },
});

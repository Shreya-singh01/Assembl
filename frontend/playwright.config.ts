import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run against a real backend (in-memory MongoDB + demo seed)
// and the Vite dev server. Existing servers on these ports are reused.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  fullyParallel: false,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: true,
      timeout: 120_000,
      env: { SEED_DEMO: "1", MONGODB_URL: "memory://", CORS_ORIGINS: "http://localhost:5173" },
    },
    { command: "npx vite --port 5173 --strictPort", url: "http://localhost:5173", reuseExistingServer: true, timeout: 60_000 },
  ],
});

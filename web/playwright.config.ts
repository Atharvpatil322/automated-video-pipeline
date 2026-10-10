import { defineConfig, devices } from '@playwright/test'

// Runs against a docker-compose stack already brought up in OFFLINE mode
// (see README's "Running the UI" section) - no webServer here, since the
// target is the nginx-fronted `web` compose service, not `vite dev`.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5174',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})

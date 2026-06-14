import { defineConfig, devices } from '@playwright/test'

/**
 * Live E2E against the real stack: `fc26 serve` static-serves the built SPA AND
 * the API on one origin (:8026), so the specs drive the actual UI against the
 * real player DB. baseURL must be http://localhost:8026 (not 127.0.0.1) to match
 * the SPA's hardcoded API base — otherwise calls are cross-origin and CORS-blocked.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? 'list' : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:8026',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    // Run from the repo root so data/players.json, squads/ and web/dist resolve.
    command: 'cd .. && .venv/bin/fc26 serve --port 8026 --host 127.0.0.1',
    url: 'http://localhost:8026/',
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
})

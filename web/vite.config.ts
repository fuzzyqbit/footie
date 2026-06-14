import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    passWithNoTests: true,
    // Unit tests only — Playwright e2e specs live in e2e/ and run separately.
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      thresholds: { lines: 80, functions: 80, branches: 80 },
    },
  },
})

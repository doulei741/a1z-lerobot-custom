import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  webServer: [
    {
      command: '../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/system/health',
      env: { A1Z_WEB_MOCK: '1', A1Z_WEB_ALLOW_HARDWARE: '0' },
      reuseExistingServer: true,
    },
    { command: 'pnpm dev', url: 'http://127.0.0.1:5173', reuseExistingServer: true },
  ],
})

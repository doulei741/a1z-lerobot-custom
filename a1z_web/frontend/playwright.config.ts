import { defineConfig } from '@playwright/test'

const apiPort = process.env.A1Z_E2E_API_PORT ?? '18000'
const frontendPort = process.env.A1Z_E2E_FRONTEND_PORT ?? '15173'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: { baseURL: `http://127.0.0.1:${frontendPort}`, trace: 'retain-on-failure' },
  webServer: [
    {
      command: `../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port ${apiPort}`,
      url: `http://127.0.0.1:${apiPort}/api/system/health`,
      env: { A1Z_WEB_MOCK: '1', A1Z_WEB_ALLOW_HARDWARE: '0' },
      reuseExistingServer: false,
    },
    {
      command: `pnpm dev --host 127.0.0.1 --port ${frontendPort}`,
      url: `http://127.0.0.1:${frontendPort}`,
      env: { A1Z_WEB_BACKEND_URL: `http://127.0.0.1:${apiPort}` },
      reuseExistingServer: false,
    },
  ],
})

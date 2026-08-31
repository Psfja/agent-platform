import { defineConfig } from '@playwright/test'

// 浏览器端到端验收：
//   1. 启动后端（scripts/e2e.sh 或手动）:  cd backend && .venv/bin/uvicorn app.main:app --port 8000
//   2. npx playwright install chromium（首次）
//   3. npm run test:e2e
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --host 0.0.0.0 --port 4173',
    url: 'http://localhost:4173/login',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
